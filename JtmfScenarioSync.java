import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.regex.*;
import java.util.stream.Stream;

/**
 * Standalone Xray Server/Data Center migration tool (Java 17+, no dependencies).
 * Only this Java file is needed. It NEVER edits your .feature files or properties.
 * Run from IntelliJ's project directory. Paste Jira issue keys separated by "or" and/or commas.
 * Preview is read-only. Changes require typing UPDATE <count> in the console.
 * Prior to every PUT, the current Xray definition is backed up outside the project.
 */
public final class JtmfScenarioSync {
    private static final Pattern ID = Pattern.compile("(?i)(?<![a-z0-9_-])@?([a-z][a-z0-9]*-\\d+)(?![a-z0-9_-])");
    private static final Pattern TAG_LINE = Pattern.compile("^\\s*@[^#]+(?:\\s*#.*)?$");
    private static final Pattern SCENARIO = Pattern.compile("^\\s*(Scenario Outline|Scenario Template|Scenario):\\s*.*$", Pattern.CASE_INSENSITIVE);
    private static final Pattern EXAMPLES = Pattern.compile("^\\s*Examples\\s*:\\s*.*$", Pattern.CASE_INSENSITIVE);
    private static final Set<String> IGNORED = Set.of(".git", ".idea", "target", "build", "node_modules", ".gradle", "out", ".jtmf-scenario-sync");

    private record Match(String key, Path file, int line, String type, String body, String preview) {}
    private record Update(Match match, String fieldType, String fieldCucumberType, String fieldScenario,
                          String oldType, String oldSubType, String oldScenario, Object oldSteps, String summary, boolean unchanged) {}
    private record ApiResponse(int status, String body) {}

    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(12))
            .followRedirects(HttpClient.Redirect.NEVER).build();
    private URI base;
    private String auth;

    public static void main(String[] args) {
        try {
            new JtmfScenarioSync().run(args);
        } catch (Exception e) {
            System.err.println("ERROR: " + safeMessage(e));
            System.err.println("No further updates will be attempted. Check the messages above.");
        }
    }

    private void run(String[] args) throws Exception {
        Path project = Paths.get(System.getProperty("user.dir")).toAbsolutePath().normalize();
        boolean dryRunOnly = false;
        String input = null;
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--root") && i + 1 < args.length) project = Paths.get(args[++i]).toAbsolutePath().normalize();
            else if (args[i].equals("--dry-run")) dryRunOnly = true;
            else if (!args[i].startsWith("--")) input = (input == null ? "" : input + " ") + args[i];
            else throw new IllegalArgumentException("Unknown argument: " + args[i]);
        }
        BufferedReader console = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        if (input == null || input.isBlank()) {
            System.out.println("Enter selected Jira test IDs in one string, e.g. ABC-1 or ABC-2, DEF-3:");
            input = console.readLine();
        }
        List<String> ids = parseIds(input);
        if (ids.isEmpty()) throw new IllegalArgumentException("No Jira IDs found. Example: ABC-123 or ABC-456, DEF-78");
        if (ids.size() > 1000) throw new IllegalArgumentException("Too many IDs (limit 1000 per run).");
        System.out.printf("Selected %d unique tests. Looking for .feature files under %s%n", ids.size(), project);

        List<Path> features = findFiles(project, ".feature");
        if (features.isEmpty()) throw new IllegalStateException("No .feature files found. Use --root C:\\path\\to\\your\\project");
        Map<String, List<Match>> index = new LinkedHashMap<>();
        for (Path feature : features) {
            try { parseFeature(feature, index); }
            catch (IOException e) { System.err.println("Cannot read " + feature + ": " + safeMessage(e)); }
        }
        List<Match> selected = new ArrayList<>();
        List<String> problems = new ArrayList<>();
        for (String id : ids) {
            List<Match> matches = index.getOrDefault(id, List.of());
            if (matches.size() == 1) selected.add(matches.get(0));
            else if (matches.isEmpty()) problems.add(id + " - no matching active @tag/Examples found");
            else {
                StringJoiner locations = new StringJoiner(", ");
                for (Match m : matches) locations.add(project.relativize(m.file) + ":" + m.line);
                problems.add(id + " - ambiguous: " + matches.size() + " matches at " + locations);
            }
        }
        for (Match m : selected) System.out.printf("MATCH %-22s %s:%d (%s)%n", m.key, project.relativize(m.file), m.line, m.type);
        if (!problems.isEmpty()) {
            for (String s : problems) System.err.println("BLOCKED " + s);
            throw new IllegalStateException("Missing or ambiguous tags: nothing will be updated. Fix matching and rerun.");
        }
        System.out.println("Gherkin extraction validated for all selected tests.");

        Path propertyFile = findConfiguration(project);
        Properties config = new Properties();
        try (Reader r = Files.newBufferedReader(propertyFile, StandardCharsets.UTF_8)) { config.load(r); }
        String url = required(config.getProperty("baseURL"), "baseURL in " + propertyFile);
        base = URI.create(url.trim().replaceAll("/+$", ""));
        if (!"https".equalsIgnoreCase(base.getScheme()) || base.getHost() == null || base.getUserInfo() != null
                || base.getRawQuery() != null || base.getRawFragment() != null)
            throw new IllegalArgumentException("Jira baseURL must be a valid HTTPS URL without credentials or query parameters.");
        authenticate(config);
        System.out.println("Read-only Jira authentication successful.");

        List<Update> updates = new ArrayList<>();
        for (Match match : selected) {
            try { updates.add(preflight(match)); }
            catch (Exception e) { problems.add(match.key + " - " + safeMessage(e)); }
        }
        if (!problems.isEmpty()) {
            for (String s : problems) System.err.println("BLOCKED " + s);
            throw new IllegalStateException("Jira preflight failed; no test cases were changed.");
        }
        long unchanged = updates.stream().filter(Update::unchanged).count();
        System.out.printf("PREVIEW: %d to update, %d already in sync, %d total.%n", updates.size() - unchanged, unchanged, ids.size());
        for (Update u : updates) System.out.printf("%-22s %-13s -> %-16s %s%n", u.match.key,
                u.oldType.isBlank() ? "(unset)" : u.oldType, u.unchanged ? "ALREADY SYNCED" : "Cucumber", u.summary);
        if (dryRunOnly || updates.size() == unchanged) {
            System.out.println("Read-only preview complete. No changes made.");
            return;
        }
        System.out.printf("%nChanges may delete old Manual steps. Local backups will be saved BEFORE each update.%n");
        System.out.printf("To update %d tests, type exactly UPDATE %d, or press Enter to cancel: ", updates.size() - unchanged, updates.size() - unchanged);
        String confirm = console.readLine();
        if (!Objects.equals(confirm == null ? "" : confirm.trim(), "UPDATE " + (updates.size() - unchanged))) {
            System.out.println("Cancelled: no changes made.");
            return;
        }
        Path backupDir = Paths.get(System.getProperty("user.home"), ".jtmf-scenario-sync", "backups",
                LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss")));
        Files.createDirectories(backupDir);
        int success = 0, failed = 0;
        for (Update u : updates) {
            if (u.unchanged) continue;
            try {
                writeBackup(backupDir, u);
                Map<String, Object> changed = new LinkedHashMap<>();
                changed.put(u.fieldType, Map.of("value", "Cucumber"));
                changed.put(u.fieldCucumberType, Map.of("value", u.match.type));
                changed.put(u.fieldScenario, u.match.body);
                ApiResponse response = request("PUT", "/rest/api/2/issue/" + u.match.key,
                        Json.stringify(Map.of("fields", changed)));
                if (response.status != 204 && response.status != 200)
                    throw new IllegalStateException("HTTP " + response.status + ": " + shorten(response.body));
                // Read back after the PUT; never claim success solely from 204.
                ApiResponse check = request("GET", "/rest/api/2/issue/" + u.match.key + "?fields="
                        + u.fieldType + "," + u.fieldCucumberType + "," + u.fieldScenario, null);
                ensureOk(check, "Verify " + u.match.key);
                Map<String, Object> fields = object(object(Json.parse(check.body)).get("fields"));
                if (!"Cucumber".equalsIgnoreCase(optionName(fields.get(u.fieldType))) ||
                        !u.match.type.equalsIgnoreCase(optionName(fields.get(u.fieldCucumberType))) ||
                        !normalize(u.match.body).equals(normalize(string(fields.get(u.fieldScenario)))))
                    throw new IllegalStateException("Jira returned different field values after update. Check this issue manually.");
                System.out.println("SUCCESS " + u.match.key);
                success++;
            } catch (Exception e) {
                System.err.println("FAILED " + u.match.key + ": " + safeMessage(e));
                failed++;
            }
        }
        System.out.printf("Done: %d verified, %d failed, %d unchanged. Backups: %s%n", success, failed, unchanged, backupDir);
    }

    private static String normalize(String text) { return text == null ? "" : text.replace("\r\n", "\n").strip(); }
    private static String required(String s, String name) { if (s == null || s.isBlank()) throw new IllegalArgumentException("Missing " + name); return s; }
    private static String safeMessage(Exception e) { return e.getMessage() == null ? e.getClass().getSimpleName() : shorten(e.getMessage()); }
    private static String shorten(String s) { return s == null ? "" : s.replaceAll("[\\r\\n]+", " ").substring(0, Math.min(s.replaceAll("[\\r\\n]+", " ").length(), 320)); }
    private static String string(Object value) { return value == null ? "" : String.valueOf(value); }
    private static String optionName(Object value) { return value instanceof Map<?, ?> map ? string(map.get("value")) : string(value); }
    @SuppressWarnings("unchecked") private static Map<String, Object> object(Object value) {
        if (!(value instanceof Map<?, ?>)) throw new IllegalArgumentException("Expected a JSON object in Jira response");
        return (Map<String, Object>) value;
    }
    private static List<String> parseIds(String raw) {
        Set<String> unique = new LinkedHashSet<>();
        if (raw != null) {
            Matcher m = ID.matcher(raw);
            while (m.find()) unique.add(m.group(1).toUpperCase(Locale.ROOT));
        }
        return new ArrayList<>(unique);
    }
    private static List<Path> findFiles(Path root, String extension) throws IOException {
        try (Stream<Path> walk = Files.walk(root)) {
            return walk.filter(p -> !Files.isDirectory(p) && p.getFileName().toString().endsWith(extension))
                    .filter(p -> { for (Path part : root.relativize(p)) if (IGNORED.contains(part.toString())) return false; return true; })
                    .sorted().toList();
        }
    }
    private static Path findConfiguration(Path root) throws IOException {
        Path direct = root.resolve("ExecutionConfig.properties");
        if (Files.isRegularFile(direct)) return direct;
        try (Stream<Path> walk = Files.walk(root, 10)) {
            List<Path> files = walk.filter(Files::isRegularFile)
                    .filter(p -> p.getFileName().toString().equals("ExecutionConfig.properties"))
                    .filter(p -> { for (Path part : root.relativize(p)) if (IGNORED.contains(part.toString())) return false; return true; })
                    .limit(2).toList();
            if (files.size() != 1) throw new IllegalStateException("Expected exactly one ExecutionConfig.properties (found " + files.size() + "). Use --root to select the correct module.");
            return files.get(0);
        }
    }

    private static boolean isTag(String line) { return TAG_LINE.matcher(line).matches(); }
    private static boolean isScenario(String line) { return SCENARIO.matcher(line).matches(); }
    private static boolean isExamples(String line) { return EXAMPLES.matcher(line).matches(); }
    private static int tagStart(List<String> lines, int heading, int floor) {
        // A group of Examples tags may include disabled tags such as
        //   @PROJECT-123
        //   # @PROJECT-999
        //   Examples:
        // The disabled tag must NOT break association with the active one.
        int pos = heading;
        boolean foundActiveTag = false;
        while (pos > floor) {
            String previous = lines.get(pos - 1).strip();
            if (isTag(previous)) {
                foundActiveTag = true;
                pos--;
            } else if (previous.isEmpty() || previous.startsWith("#")) {
                pos--;
            } else {
                break;
            }
        }
        return foundActiveTag ? pos : heading;
    }
    private static String exampleBlock(List<String> lines, int from, int to) {
        // Disabled ID tags must never be sent to Jira as active test metadata.
        StringBuilder b = new StringBuilder();
        for (int i = from; i < to; i++) {
            String line = lines.get(i);
            if (line.stripLeading().matches("#\\s*@[^\\s]+.*")) continue;
            b.append(line).append('\n');
        }
        return b.toString().stripTrailing();
    }
    private static void add(Map<String, List<Match>> index, Match match) {
        index.computeIfAbsent(match.key, k -> new ArrayList<>()).add(match);
    }
    private static Set<String> tags(List<String> lines, int begin, int end) {
        Set<String> found = new LinkedHashSet<>();
        for (int i = begin; i < end; i++) {
            Matcher matcher = ID.matcher(lines.get(i));
            if (isTag(lines.get(i))) while (matcher.find()) found.add(matcher.group(1).toUpperCase(Locale.ROOT));
        }
        return found;
    }
    private static String join(List<String> lines, int from, int to) {
        if (to <= from) return "";
        return String.join("\n", lines.subList(from, to)).strip() + "\n";
    }
    private static void parseFeature(Path file, Map<String, List<Match>> index) throws IOException {
        List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
        for (int head = 0; head < lines.size(); head++) {
            Matcher sm = SCENARIO.matcher(lines.get(head));
            if (!sm.matches()) continue;
            String type = sm.group(1).equalsIgnoreCase("Scenario") ? "Scenario" : "Scenario Outline";
            int end = head + 1;
            while (end < lines.size() && !isScenario(lines.get(end)) &&
                    !lines.get(end).stripLeading().matches("(?i)^(Feature|Rule):.*")) end++;
            // Tags immediately preceding the NEXT scenario belong to that next scenario, not this one.
            if (end < lines.size() && isScenario(lines.get(end))) end = tagStart(lines, end, head + 1);
            List<Integer> exs = new ArrayList<>();
            for (int i = head + 1; i < end; i++) if (isExamples(lines.get(i))) exs.add(i);
            if (exs.isEmpty()) {
                int tagBegin = tagStart(lines, head, 0);
                String body = join(lines, head + 1, end);
                for (String id : tags(lines, tagBegin, head))
                    add(index, new Match(id, file, head + 1, type, body, lines.get(head) + "\n" + body));
            } else {
                int commonEnd = tagStart(lines, exs.get(0), head + 1);
                String common = join(lines, head + 1, commonEnd).stripTrailing();
                for (int i = 0; i < exs.size(); i++) {
                    int ex = exs.get(i);
                    int exStart = tagStart(lines, ex, head + 1);
                    int exEnd = i + 1 < exs.size() ? tagStart(lines, exs.get(i + 1), ex + 1) : end;
                    String example = exampleBlock(lines, exStart, exEnd);
                    String body = common + "\n\n" + example + "\n";
                    Set<String> caseIds = tags(lines, exStart, ex);
                    for (String id : caseIds)
                        add(index, new Match(id, file, exStart + 1, type, body, lines.get(head) + "\n" + body));
                }
            }
            head = Math.max(head, end - 1);
        }
    }

    private void authenticate(Properties p) throws Exception {
        List<String> candidates = new ArrayList<>();
        String envBearer = System.getenv("JTMF_BEARER_TOKEN");
        String envBasic = System.getenv("JTMF_BASIC_TOKEN");
        if (envBearer != null && !envBearer.isBlank()) candidates.add("Bearer " + envBearer.trim());
        if (envBasic != null && !envBasic.isBlank()) candidates.add("Basic " + envBasic.trim());
        String user = System.getenv().getOrDefault("JTMF_USERNAME", p.getProperty("username", ""));
        String password = System.getenv().getOrDefault("JTMF_PASSWORD", p.getProperty("password", ""));
        if (!user.isBlank() && !password.isBlank()) candidates.add("Basic " + Base64.getEncoder().encodeToString((user + ":" + password).getBytes(StandardCharsets.UTF_8)));
        String token = p.getProperty("token", "").trim();
        if (!token.isBlank()) {
            candidates.add("Bearer " + token);
            if (token.matches("[A-Za-z0-9+/]+={0,2}")) candidates.add("Basic " + token);
        }
        if (candidates.isEmpty()) throw new IllegalStateException("No existing JTMF credentials available. Configure an approved token via JTMF_BEARER_TOKEN/JTMF_BASIC_TOKEN environment variable.");
        for (String candidate : new LinkedHashSet<>(candidates)) {
            auth = candidate;
            ApiResponse r = request("GET", "/rest/api/2/myself", null);
            if (r.status == 200 && r.body.stripLeading().startsWith("{")) return;
            if (r.status != 401 && r.status != 403) throw new IllegalStateException("JTMF API authentication check returned HTTP " + r.status + " (maybe VPN, SSO or proxy issue).");
        }
        auth = null;
        throw new IllegalStateException("JTMF rejected the existing credentials (401/403). Browser SSO alone does not authenticate a Java program. Obtain an approved Jira API credential; no tests were changed.");
    }

    private Update preflight(Match m) throws Exception {
        ApiResponse meta = request("GET", "/rest/api/2/issue/" + m.key + "/editmeta", null);
        ensureOk(meta, "Edit metadata for " + m.key);
        Map<String, Object> fieldsMeta = object(object(Json.parse(meta.body)).get("fields"));
        String type = getField(fieldsMeta, "Test Type", "customfield_10001");
        String subtype = getField(fieldsMeta, "Cucumber Test Type", "customfield_10002");
        String scenario = getField(fieldsMeta, "Cucumber Scenario", "customfield_10003");
        validateAllowed(fieldsMeta, type, "Cucumber");
        validateAllowed(fieldsMeta, subtype, m.type);
        ApiResponse issue = request("GET", "/rest/api/2/issue/" + m.key, null);
        ensureOk(issue, "Issue " + m.key);
        Map<String, Object> data = object(Json.parse(issue.body));
        if (!m.key.equalsIgnoreCase(string(data.get("key")))) throw new IllegalStateException("Jira returned a different issue key.");
        Map<String, Object> fields = object(data.get("fields"));
        String issueType = optionName(fields.get("issuetype"));
        if (fields.get("issuetype") instanceof Map<?, ?> map) issueType = string(map.get("name"));
        if (!"Test".equalsIgnoreCase(issueType)) throw new IllegalStateException("Issue is " + issueType + ", not a Test.");
        String oldType = optionName(fields.get(type));
        String oldSubType = optionName(fields.get(subtype));
        String oldScenario = string(fields.get(scenario));
        // Existing Xray manual step custom field; never overwrite it directly.
        Object oldSteps = fields.get("customfield_10005");
        boolean unchanged = "Cucumber".equalsIgnoreCase(oldType) && m.type.equalsIgnoreCase(oldSubType)
                && normalize(oldScenario).equals(normalize(m.body));
        if (m.body.isBlank() || !m.body.matches("(?s).*\\b(Given|When|Then|And|But|\\*)\\b.*"))
            throw new IllegalStateException("Extracted scenario has no recognizable Gherkin steps.");
        if ("Scenario Outline".equals(m.type) && !m.body.contains("Examples:"))
            throw new IllegalStateException("Scenario Outline is missing Examples.");
        return new Update(m, type, subtype, scenario, oldType, oldSubType, oldScenario, oldSteps, string(fields.get("summary")), unchanged);
    }
    private static String getField(Map<String, Object> meta, String name, String fallback) {
        for (var e : meta.entrySet()) {
            Object info = e.getValue();
            if (info instanceof Map<?, ?> map && name.equalsIgnoreCase(string(map.get("name")))) {
                Object ops = map.get("operations");
                if (!(ops instanceof List<?> list) || !list.contains("set")) throw new IllegalStateException(name + " is not editable.");
                return e.getKey();
            }
        }
        if (meta.containsKey(fallback)) {
            Object ops = object(meta.get(fallback)).get("operations");
            if (ops instanceof List<?> list && list.contains("set")) return fallback;
        }
        throw new IllegalStateException("Editable field not found: " + name);
    }
    private static void validateAllowed(Map<String, Object> meta, String field, String value) {
        Object allowed = object(meta.get(field)).get("allowedValues");
        if (allowed instanceof List<?> list && !list.isEmpty()) {
            boolean found = list.stream().filter(Map.class::isInstance).map(x -> ((Map<?, ?>) x).get("value"))
                    .anyMatch(x -> value.equalsIgnoreCase(string(x)));
            if (!found) throw new IllegalStateException("Option " + value + " is not allowed for " + field);
        }
    }
    private void writeBackup(Path folder, Update u) throws IOException {
        Map<String, Object> backup = new LinkedHashMap<>();
        backup.put("key", u.match.key);
        backup.put("sourceFile", u.match.file.toString());
        backup.put("previousTestType", u.oldType);
        backup.put("previousCucumberType", u.oldSubType);
        backup.put("previousScenario", u.oldScenario);
        backup.put("previousManualSteps", u.oldSteps);
        backup.put("newScenario", u.match.body);
        Files.writeString(folder.resolve(u.match.key + ".json"), Json.stringify(backup), StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    }
    private ApiResponse request(String method, String path, String json) throws Exception {
        URI target = base.resolve(base.getPath().replaceAll("/+$", "") + path);
        if (!target.getHost().equalsIgnoreCase(base.getHost()) || !target.getScheme().equalsIgnoreCase(base.getScheme()))
            throw new IllegalStateException("Unsafe redirect or API URL.");
        HttpRequest.Builder builder = HttpRequest.newBuilder(target).timeout(Duration.ofSeconds(30))
                .header("Accept", "application/json").header("Authorization", required(auth, "Jira API authentication"));
        if (json == null) builder.GET();
        else builder.header("Content-Type", "application/json; charset=UTF-8")
                .method(method, HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8));
        HttpResponse<String> response = client.send(builder.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        return new ApiResponse(response.statusCode(), response.body());
    }
    private static void ensureOk(ApiResponse r, String operation) {
        if (r.status != 200) throw new IllegalStateException(operation + " failed: HTTP " + r.status + " " + shorten(r.body));
    }

    /** Minimal standards-compliant JSON parser/writer; avoids requiring Maven dependencies. */
    private static final class Json {
        private final String s; private int pos;
        private Json(String s) { this.s = s; }
        static Object parse(String s) {
            Json j = new Json(s); Object v = j.value(); j.ws();
            if (j.pos != s.length()) throw new IllegalArgumentException("Unexpected characters after JSON");
            return v;
        }
        private void ws() { while (pos < s.length() && Character.isWhitespace(s.charAt(pos))) pos++; }
        private char peek() { ws(); if (pos >= s.length()) throw new IllegalArgumentException("Unexpected JSON end"); return s.charAt(pos); }
        private void expect(char c) { if (peek() != c) throw new IllegalArgumentException("Expected " + c + " in JSON"); pos++; }
        private Object value() {
            char c = peek();
            if (c == '"') return str();
            if (c == '{') {
                pos++; Map<String, Object> map = new LinkedHashMap<>();
                if (peek() == '}') { pos++; return map; }
                do { String key = str(); expect(':'); map.put(key, value()); if (peek() == '}') { pos++; return map; } expect(','); } while (true);
            }
            if (c == '[') {
                pos++; List<Object> list = new ArrayList<>();
                if (peek() == ']') { pos++; return list; }
                do { list.add(value()); if (peek() == ']') { pos++; return list; } expect(','); } while (true);
            }
            if (s.startsWith("true", pos)) { pos += 4; return true; }
            if (s.startsWith("false", pos)) { pos += 5; return false; }
            if (s.startsWith("null", pos)) { pos += 4; return null; }
            int from = pos; while (pos < s.length() && "-+.0123456789eE".indexOf(s.charAt(pos)) >= 0) pos++;
            if (from == pos) throw new IllegalArgumentException("Invalid JSON value");
            String number = s.substring(from, pos);
            try { return number.matches("-?(0|[1-9][0-9]*)") ? Long.parseLong(number) : Double.parseDouble(number); }
            catch (NumberFormatException e) { throw new IllegalArgumentException("Invalid JSON number", e); }
        }
        private String str() {
            expect('"'); StringBuilder out = new StringBuilder();
            while (pos < s.length()) {
                char c = s.charAt(pos++);
                if (c == '"') return out.toString();
                if (c == '\\') {
                    if (pos >= s.length()) break;
                    char e = s.charAt(pos++);
                    switch (e) {
                        case '"' -> out.append('"'); case '\\' -> out.append('\\'); case '/' -> out.append('/');
                        case 'b' -> out.append('\b'); case 'f' -> out.append('\f'); case 'n' -> out.append('\n');
                        case 'r' -> out.append('\r'); case 't' -> out.append('\t');
                        case 'u' -> { if (pos + 4 > s.length()) throw new IllegalArgumentException("Invalid Unicode escape");
                            out.append((char) Integer.parseInt(s.substring(pos, pos + 4), 16)); pos += 4; }
                        default -> throw new IllegalArgumentException("Invalid JSON escape");
                    }
                } else { if (c < 32) throw new IllegalArgumentException("Invalid control character in JSON"); out.append(c); }
            }
            throw new IllegalArgumentException("Unterminated JSON string");
        }
        static String stringify(Object value) {
            if (value == null) return "null";
            if (value instanceof String s) return quote(s);
            if (value instanceof Boolean || value instanceof Number) return value.toString();
            if (value instanceof Map<?, ?> map) {
                List<String> elements = new ArrayList<>();
                for (var e : map.entrySet()) elements.add(quote(string(e.getKey())) + ":" + stringify(e.getValue()));
                return "{" + String.join(",", elements) + "}";
            }
            if (value instanceof Iterable<?> elements) {
                List<String> out = new ArrayList<>(); for (Object e : elements) out.add(stringify(e));
                return "[" + String.join(",", out) + "]";
            }
            return quote(value.toString());
        }
        private static String quote(String value) {
            StringBuilder b = new StringBuilder("\"");
            for (char c : value.toCharArray()) {
                switch (c) {
                    case '"' -> b.append("\\\""); case '\\' -> b.append("\\\\");
                    case '\n' -> b.append("\\n"); case '\r' -> b.append("\\r"); case '\t' -> b.append("\\t");
                    default -> { if (c < 32) b.append(String.format("\\u%04x", (int) c)); else b.append(c); }
                }
            }
            return b.append('"').toString();
        }
    }
}
