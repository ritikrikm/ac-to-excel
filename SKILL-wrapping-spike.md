name: live-inspector-wrapping-spike description: > Team-only
Spike 1 for Live Inspector: wrap the CTS BaseCollection device
in the user's own team project only, with an on/off switch
added to the existing run command. No CTS change. Plan first,
then code, only after user approval. Show whatever the xpath
gives, on the right side of the code line, in the plugin phase.
Spike 1 proves capture to console/file first.


Live Inspector — Wrapping Spike (new
complete skill)

0. FINAL PRODUCT — READ THIS FIRST, THIS IS NOT A CTS
PRODUCT

FINAL PRODUCT = the user's own TEAM PROJECT that uses CTS. CTS is only a library / dependency
that team project calls. You are NOT building a product for CTS, NOT building a product for the
CTS team, and NOT changing CTS.

    Product owner: the team project (its repo, its pages, its ObjectRepository, its run command,
    its editor plugin install).
    CTS role: only the framework the team project already uses. You call CTS things, you do NOT
    build, change, or deliver CTS.
    Final product, when done, lives and works in the team project: wrapper helper in the team
    project, demo runner in the team project, plugin installed in the team project's developers'
    editors, switch on the team project's existing run command.
    The CTS-hook version for all teams is NOT the final product here. It is optional, later, and only
    if the CTS owners ask for it. The team project product works fully without it. Do NOT present
    CTS adoption as a required step for this product to be finished.

If you write anything that reads as "deliver this to CTS" or "change CTS to finish this", you have
misunderstood the scope. Stop and re-read this section.


0. What this skill is, in one paragraph

You are building ONE small thing first: a wrapper around the CTS device that the user's team
project already uses, so that when a test line runs normally, we can see what that line's xpath
actually gave, live. Nothing else in this skill. No plugin yet in Spike 1, no CTS change, no
Playwright, no recommended locators, no CI change.

The user will run the project exactly as today, plus one switch:


  <existing project run command> -DliveInspector=true




    Without the switch, or with -DliveInspector=false : the project runs EXACTLY as today. No
    wrapper, no log, no hold, no behaviour change, no slowdown.
    With -DliveInspector=true : the wrapper is active, the fetched value is logged, and the
    browser is held open at the end for the demo run (see Section 7).

The switch name is fixed in this skill: liveInspector . Do NOT invent a different switch name, a
different property name, or an environment variable, unless the PLAN (Section 2) proves that
name collides with an existing property in this repo — and then stop and ask the user, do not
silently rename it.


1. HARD RULE — DO NOT ASSUME ANYTHING

This is the most important section. AI agents easily assume and start working. You must NOT do
that here.


1.1 Forbidden assumptions

Do NOT assume, guess, invent, or copy from examples in this file:

    File paths, package names, class names, method names, method signatures, return types, or
    line numbers.
    The exact name of the ObjectRepository file, the exact feature file, the exact step definition
    file, or the exact page file.
    The exact existing command used to run the project.
    The exact BaseCollection methods available, or what they return.
    The editor (VS Code vs IntelliJ) — Spike 1 does not need it, do not pick one in Spike 1.
    That a field, a DTO, or a reflection path exists inside CTS.
    That the user's team project has a common base page class.
    That any example code in this skill compiles as-is in this repo.

Every example in this skill is ILLUSTRATIVE ONLY. It shows the shape of the idea. It is NOT repo
code. Before you write any real code, you must replace every illustrative name with a name you
actually found in this repo, with a file path and a line number.


1.2 Verification rule
For every fact you will rely on in code, you must:

  1. Search the repo for it.
  2. Quote the exact file path and line number where you found it.
  3. If you cannot find it, write NOT FOUND for that item in the PLAN, and do NOT write code that
    depends on it. Stop that item and ask the user, or propose a verified alternative in the PLAN.

If a fact is in the CTS jar but not in source in this repo, say so explicitly: "found in CTS jar, not in
team project source". Do NOT pretend jar internals are team project source, and do NOT guess jar
field names.


1.3 Scope rule — only calling CTS things

This spike works ONLY by calling / watching CTS things that the team project already calls. That
means:

ALLOWED — only these kinds of work:

    Calling DriverManager.getDriverInstance() exactly as existing team code already does, and
    wrapping the returned BaseCollection .
    Intercepting BaseCollection methods that existing team code already calls, for example
     click , elementSendText , waitForElement , waitForElementClickable ,
     waitForElementInvisible , waitForElementAttributeToBe , launchUrl , executeJavaScript
    — ONLY the methods you actually find used in this repo, verified in the PLAN. Do NOT list a
    method here as if it exists if you did not find it.
    Reading the team's own ObjectRepository properties file, to map a locator string key to its
    real xpath / id / etc.
    Running the team's own existing feature / step / page chain, exactly as today: feature file ->
    step definition -> page object -> CTS device call.
    Adding ONE new helper class in the team project, and ONE demo runner in the team project
    (Section 7), both in team project source only.

NOT ALLOWED in this spike:

    Changing CTS source, CTS jar, CTS version in pom.xml, or any file inside a CTS package
    ( com.td.automation_libraries , com.td.core , etc.).
    Changing SeleniumLibrary , ElementFinder , DriverManager , DriverInitializer , or
     CucumberTemplate in CTS.

    Creating your own WebDriver, your own browser, your own login, your own navigation, or
    your own test.
    Clicking, typing, submitting, or deleting anything on your own. The inspector NEVER acts on
    its own. It only watches CTS calls the test already makes, and reads what those calls gave.
    Changing any existing locator, test data, feature text, step text, or test logic.
    Changing any page file except the ONE demo page in Spike 1 (Section 6).
    Playwright, Appium, Grid, CI, production URLs, or any new framework.

If a step would require breaking the NOT ALLOWED list, stop, put it in the PLAN as a blocked item,
and ask the user. Do NOT work around it silently.


2. WORKFLOW — PLAN FIRST, THEN CODE, ONLY AFTER
APPROVAL

Do NOT write any code in your first response. Your first response must be a PLAN only, and then
you must STOP and wait for the user to say "go".


2.1 PLAN — what your first response must contain

Produce a plan with exactly these sections, filled from THIS repo only, with file paths and line
numbers for every verified fact, and NOT FOUND where you could not verify:

 1. Existing run command, verified: the exact command the team uses today to run a scenario
    (from pom.xml, README, or run config in the repo). Then show that SAME command with -
    DliveInspector=true added at the end. Do NOT invent a run command. If you find more than
    one run command, list them all and ask which one is the demo command.
 2. Demo scope, verified: ONE feature file, ONE scenario, ONE step definition file, ONE page file.
    The previous analysis used a Forgot Password example — do NOT assume that is the demo in
    THIS repo. Find the actual files in this repo and name them. If the Forgot Password files exist
    here, name them with paths. If they do not, name the actual demo files you found, or ask the
    user to pick one scenario.
 3. How the demo page gets its device, verified: quote the exact line(s) in the demo page
    where DriverManager is called and where the BaseCollection device is stored, and whether
    that page has a common base class or does it directly. If every page does it directly, say so —
    that is why Spike 1 touches only ONE page.
 4. BaseCollection methods used by the demo page, verified: list every device method the
    demo page actually calls, with the line number for each call, and what each method returns
    (void, boolean, String, etc., as declared in the CTS interface you can see from the jar / imports
    in this repo).
 5. ObjectRepository, verified: exact file path(s) for the ObjectRepository used by the demo
    page, and 3 real entries from that file, copied exactly, for locators the demo page actually
    uses.
 6. How the fetched value can be obtained, verified, with options in order:
        Option A (preferred, cleanest): does any BaseCollection method used by the demo page
        RETURN the fetched element / value? Quote it if yes.
        Option B (spike-only, needs explicit user approval): is there a verified way, from team
        project code, to re-evaluate the resolved xpath/id in the SAME live browser that CTS is
        already driving, without creating a new driver? Name the exact mechanism you verified
        (for example, reflection into a specific CTS class — but ONLY if you verified the exact class
        and field names from the CTS jar in this repo, with evidence). If you cannot verify exact
        names, write NOT FOUND — value capture method not verified and propose the
        reduced Spike 1 scope in Section 2.2.
        Do NOT present Option B as if it is already verified. It is a PLAN question, not a fact, until
        you verify it.

 7. Files you will create, files you will change, files you will NOT touch: three separate lists,
    with exact paths. The change list for Spike 1 must be: 1 new wrapper helper file, 1 line
    changed in 1 demo page, 1 new demo runner file (if needed for hold, Section 7), and nothing
    else.
 8. Switch implementation, verified: where the switch will be read
    ( System.getProperty("liveInspector", "false") or the repo's existing config mechanism —
    but only if you verify that mechanism exists in this repo), and what happens in code when it is
    false (return the real device unchanged, no log, no hold).
 9. Risks and open questions: list every risk from Section 9 that applies to THIS repo, with
    evidence, plus any new risk you found. Do NOT claim a risk is solved until you prove it in code
    and in a run.
10. Success criteria for Spike 1: the exact checks in Section 8, restated for the actual demo
    scenario you found.


2.2 If value capture cannot be verified cleanly

If Option A and Option B in 2.1(6) are both NOT FOUND, do NOT invent a third method and do
NOT proceed to full code. In the PLAN, propose the reduced Spike 1:

    Wrapper logs, for each CTS call in the demo page: file, line, method name, locator string key,
    resolved xpath/id from the team's own ObjectRepository file.
    Fetched value display is marked as BLOCKED pending a CTS-hook decision, and the PLAN
    says so plainly.
    User decides: approve reduced spike, or approve the verified reflection hack, or stop.

Do NOT silently downgrade the goal, and do NOT silently upgrade an unverified hack to a fact.


2.3 After PLAN approval

Only after the user explicitly says "go" / approves the PLAN, in their own words, you may write
code — and only the code listed in the approved PLAN, in the order listed in Section 6.

After EACH phase (Spike 1a console, Spike 1b hold, plugin phase later), STOP, report what you did,
what run you did, what output you got, and what failed. Wait for user approval before the next
phase. Do NOT chain phases automatically.
3. GOAL — what the user must see, in the user's own terms

    Run the project normally, with the existing command plus -DliveInspector=true .
    No debug mode. No breakpoint. No special run the user has to learn.
    As each line runs, the value that line's xpath gave must be available to show on the right side
    of that line.
    In Spike 1, that value is proved by console/file log first (Section 6). In the plugin phase, the
    SAME value, in the SAME event format (Section 5), is drawn on the right side.
    Right-side display rule, fixed: the right side shows ONLY whatever the xpath gave. Example,
    using the illustrative Forgot Password case only if verified in this repo:


  device.click("account.forgetPassword");   ↳ "Forgot password"




That is: this xpath gave this value. That is what the next line of code will act on. Do NOT add any
other number or metric to the right-side display. If the xpath gave nothing, show that plainly on
the right side, in red if the editor supports it, with the page URL in the hover/log — do NOT invent
a reason, just show that nothing was given.


4. CTS FACTS — background only, verify before using

The following facts came from a previous CTS analysis (screenshots, 2026-11-01). They are
BACKGROUND, not repo-verified facts for THIS run. You must verify each one you rely on in THIS
repo, in the PLAN, before coding. If a fact differs in this repo, the repo wins.

    CTS = Continuous Testing Suite, unified Selenium / Appium / REST framework, behind a single
     BaseCollection interface. Child code does NOT touch a raw WebDriver directly.

    Child code pattern (illustrative): BaseCollection device = (BaseCollection)
    DriverManager.getDriverInstance(); then device.click("...") ,
     device.elementSendText("...", "...") , device.waitForElement("...", 5) ,
     device.launchUrl("...") .

    Locators in child code are STRING KEYS, not By objects. The real xpath/id lives in an
    ObjectRepository properties file in the team project. CTS resolves string -> By internally.
    CTS driver creation is centralised in CTS (previously reported as
     SeleniumLibrary.createInternalDriverInstance() and getSeleniumWebDriver() ), and CTS
    teardown is centralised (previously reported as tearDownDriver() / quit() via
     CucumberTemplate / DriverInitializer ). You must NOT change any of those in this spike.
    They are listed here only so you understand why team-only wrapping cannot be at driver
    creation in this spike, and why Spike 1 wraps at the device level in the team project instead.
    CTS storage was previously reported as ThreadLocal per user / device. If you use thread/user
    tagging in events, you must verify that tagging mechanism in THIS repo first. Do NOT assume
    thread names or user names.
    CTS has NO Playwright support in the previous analysis, NO keep-browser-open mode, and
    NO logging of what a finder gave. Those are gaps this spike addresses for the team project
    only, not for all CTS teams.


5. EVENT FORMAT — fixed, so plugin work later does not
rework this

Every wrapped CTS call, when the switch is true, must produce ONE event with exactly these
fields, in this order, with no extra invented fields unless the PLAN approves them:

     file : page file name, as found in the stack walk (Section 6.3)

     line : line number in that file for the CTS call

     method : BaseCollection method name, e.g. click

     locatorKey : string key as written in code, e.g. account.forgetPassword (illustrative only)

     resolved : real xpath/id/etc. from the team's ObjectRepository file, e.g. xpath=//*
    [@class='td-link-action'] (illustrative only)

     value : whatever the xpath gave, as text / element description, truncated for display (tag,
    visible text, key attributes). If nothing was given, value is empty / "nothing given" — do NOT
    invent a value.
     threadUser : thread / user tag ONLY if verified in this repo, otherwise omit this field and say
    so in the PLAN.

In Spike 1, events go to console AND to a local log file in the team project run output (path to be
named in the PLAN, e.g. under target/ — verify the project's output folder first, do NOT assume
target/ if the project uses another folder). In the plugin phase, the SAME events go over
localhost to the plugin, which draws value on the right side of file:line . The plugin phase is
NOT in Spike 1 code, unless the PLAN explicitly approves it after Spike 1 passes.


6. SPIKE 1 IMPLEMENTATION — in order, no skipping

6.1 Switch first

    Read the switch at the single entry point of the wrapper:
     System.getProperty("liveInspector", "false") — unless the PLAN verifies a different
    existing mechanism in this repo.
    If the switch is false, missing, or any value other than exactly true (case-insensitive, as
    verified in the PLAN): return the real BaseCollection device UNCHANGED, do no logging, do
    no hold, do no extra work.
    If the switch is true: return the wrapped device (Section 6.2).
    The switch must be read once per device creation, not on every call, unless the PLAN proves a
    reason to re-read it.
     Document in the PLAN and in code comments: "Switch off = behaviour identical to today."


6.2 Wrapper — ONE new file in the team project

     Create ONE new helper class in the team project, in a package the PLAN names from this
     repo's existing structure. Do NOT create it in a CTS package. Do NOT create it in com.td.*
     unless the PLAN proves the team project already uses that package for its own code — if in
     doubt, use the team project's own helper / utils package, as found in the repo.
     The wrapper must be a dynamic proxy for BaseCollection (Java Proxy ), IF the PLAN verifies
     BaseCollection is an interface in this repo. If it is NOT an interface, STOP and propose a
     verified alternative in the PLAN — do NOT assume proxy works.
     Proxy rules:
          Every method call on the proxy must, by default, delegate to the real device with the
          exact same arguments, and return the exact same result. No method may change test
          behaviour.
          Only methods whose first argument is a String locator key produce a Live Inspector
          event. Other methods pass through silently, with no log.
          For action methods ( click , elementSendText , etc. — only methods verified in the
          PLAN), capture the fetched value BEFORE delegating, if the PLAN proves that timing is
          needed (for example, a click may navigate away). For other methods, capture timing
          must be stated in the PLAN, per method, with a reason. Do NOT use one timing rule for
          all methods without stating it.
          Value extraction must be synchronous at that moment, so the value matches that line's
          moment. Sending / logging may be queued / asynchronous, so the test is not slowed by
          display work.
          If value capture fails for a call (exception, NOT FOUND, timeout), log the failure for that
          call, do NOT fail the test, and DO delegate to the real device as normal. The inspector
          must never break a test that would otherwise pass.

     Illustrative shape only (do NOT copy names blindly):


 // Team project helper only — illustrative, replace every name
 // with a repo-verified name from the PLAN before coding.
 public class LiveInspector {
      public static BaseCollection wrap(BaseCollection realDevice) {
           if (!"true".equalsIgnoreCase(System.getProperty("liveInspector", "false"))) {
               return realDevice;
           }
           // return Proxy for BaseCollection that intercepts String-key
           // methods, logs an event (Section 5), then delegates.
           // ... implementation from PLAN, verified names only ...
      }
 }
6.3 Line mapping — prove it, do not assume it

   When a wrapped call happens, walk the current stack trace.
   Skip frames belonging to: the wrapper itself, Java proxy classes, CTS packages, Selenium
   packages, Cucumber, TestNG. The exact skip list must be written in the PLAN, from frames
   you actually observe in a real run in this repo — do NOT copy a skip list from this skill as if it is
   complete.
   The first remaining frame must be the team project page / step file and line number. That is
   the file and line in the event.
   If no such frame is found, log the event with file and line as NOT FOUND , do NOT invent a
   line, and record it as a Spike 1 failure to fix in the PLAN review.
   Deduplication: if the same file + line + locator key fires repeatedly because of a wait poll, show
   only the latest value for that line in the log / plugin. Do NOT flood the log with every poll retry.
   The exact deduplication rule must be in the PLAN.


6.4 Change ONLY one demo page in Spike 1

   Change exactly ONE line in exactly ONE demo page file (named in the PLAN): replace the
   direct device creation with the wrapped version, for example (illustrative only):


 // Before (illustrative):
 // private BaseCollection device = (BaseCollection) DriverManager.getDriverInstance();
 // After (illustrative, verified names only):
 // private BaseCollection device = LiveInspector.wrap((BaseCollection)
 DriverManager.getDriverInstance());




   All other lines in that page, and all other pages, stay EXACTLY unchanged in Spike 1.
   If the demo page gets its device from a common base class (verified in the PLAN), then
   changing that base class counts as the ONE change, and the PLAN must say so explicitly, with
   the impact (all pages inheriting it will be wrapped — user must approve that impact in the
   PLAN, it is NOT automatic).


6.5 ObjectRepository resolution — team project file only

   Read ONLY the team's own ObjectRepository file(s) named in the PLAN.
   Map locator key -> real xpath/id/etc. exactly as written in that file. Do NOT hardcode any
   mapping in code. If a key is not in the file, log resolved: NOT FOUND for that call, do NOT
   guess a xpath.
   If the file format is not simple key=type=value , the PLAN must describe the actual format
   found in this repo before coding the parser.


7. HOLD — demo runner, team project only, switch-gated
Hold is part of Spike 1b, AFTER Spike 1a (capture) passes, and ONLY if the PLAN approves it. Do
NOT do hold in the same step as capture without approval.

    Normal run (switch false): teardown runs exactly as today, browser closes exactly as today.
    Demo run (switch true): the browser must NOT close at the end of the scenario. It must stay
    open, logged in, on the last page, until the user manually closes it.
    Team-only hold mechanism, to be verified in the PLAN: create a demo runner in the TEAM
    project that does the same setup as the normal runner, runs the demo scenario, then WAITS
    (for example, "press Enter to close" in console, or a local close signal — exact mechanism to
    be named in the PLAN) instead of calling teardown, and only then calls teardown normally.
    Do NOT change the normal runner, do NOT change CucumberTemplate in CTS, do NOT
    change teardown in CTS. The demo runner is a SEPARATE runner file, used only for the demo
    command with the switch on.
    If the demo runner crashes, the user kills the run, or the plugin is not connected, teardown
    must still run as a fallback. The fallback mechanism and timeout must be in the PLAN. A held
    browser must never leak into the next run, and must never run in CI. CI runs with switch
    false, by definition, and must never be given the switch true.


8. ACCEPTANCE — Spike 1 passes only if ALL of these are true

Run these checks, in order, and report the actual output for each. Do NOT claim a pass you did
not run.

  1. Switch off test: run the existing command WITHOUT the switch (and once with -
    DliveInspector=false ). Test result is identical to before, no Live Inspector log appears,
    browser closes as normal.
  2. Switch on, demo scenario: run the existing command WITH -DliveInspector=true , for the
    ONE demo scenario named in the PLAN. Test result (pass/fail) is the same as switch-off,
    except for hold.
  3. Value log: for every CTS call in the demo page, the console/file log shows, in order: file, line,
    method, locator key, resolved xpath/id, and the fetched value. No invented values. Any call
    where value could not be obtained is logged as a failure for that call, not hidden.
  4. Right-side readiness: every log event matches the Section 5 format exactly, so the later
    plugin can draw value on the right side of file:line without rework.
  5. Hold: after the demo scenario, with switch true, the browser stays open on the last page.
    Manual close (as defined in the PLAN) then runs normal teardown and the browser closes
    cleanly. A second run after that works.
  6. No other files changed: git status / diff shows ONLY the files listed in the approved PLAN.
    Any other changed file is a failure, revert it, and report it.

If any check fails, STOP, report the failure with the actual log / error, and wait for user direction.
Do NOT proceed to plugin work, and do NOT try a different unverified workaround without
putting it in an updated PLAN first.


9. RISKS — do not assume these are solved

List these in the PLAN, with repo evidence, and revisit them after Spike 1:

    Reflection / value-capture fragility, if Option B in Section 2.1(6) is used: CTS internal names
    can change.
    Timing: value captured after a navigating click can be stale / from the wrong page. Per-
    method timing in the PLAN must address this.
    Dynamic locators, shadow DOM, iframes, Salesforce Lightning loading: a value can be correct
    one moment and missing the next if the page has not finished loading. The wrapper must
    use the same waiting CTS already does, not invent its own wait.
    Wait polling noise: deduplication (Section 6.3) is required, otherwise the log / display flickers.
    Thread / parallel mixing: events must be tagged correctly, or values from one test will appear
    on another test's lines. Verify tagging in the PLAN, do not assume it.
    Sensitive values: element text can contain account numbers, emails, or tokens. Mask such
    values in log / display unless the user explicitly expands them, and never log passwords,
    tokens, or OTPs. Test environments and test users only.
    Performance: value extraction on every call must not noticeably slow the demo scenario.
    Measure it in Spike 1 (run time switch-off vs switch-on) and report it.
    Demo fragility: if the demo scenario's page, login, or locator changes, the demo fails. Use the
    most stable demo scenario in the repo, as named in the PLAN, not the most impressive one.


10. SAFETY AND ENTERPRISE RULES — non-negotiable

    Test environments and test users only, via the normal test run. No production URLs. No new
    login or navigation code.
    No passwords, tokens, OTPs, or secrets in new code, in logs, in the PLAN, or in any config you
    add. Use the team's existing credential handling. The wrapper adds only the switch, no new
    secret.
    Localhost only for any later plugin channel. No event leaves the developer's laptop in Spike 1
    or later.
    The inspector NEVER clicks, types, submits, or deletes on its own. It only watches CTS calls the
    test already makes.
    Switch off by default. Switch true is local demo only. Never add the switch true to CI, to a
    shared run config, or to a committed pom / properties file as a default.
    Do NOT commit any change that is not in the approved PLAN.


11. WHAT COMES AFTER SPIKE 1 — NOT IN THIS SKILL'S CODE
Do NOT build these in Spike 1, even if they seem easy:

    Editor plugin / extension (VS Code or IntelliJ) — separate project, separate skill, after Spike 1
    passes and the user picks the editor. The plugin will consume Section 5 events and draw
     value on the right side. The plugin IS part of the final product for the TEAM PROJECT — it is
    not a CTS product, it is installed by team project developers.
    Recommended locators, replace-in-code, or any locator suggestion.
    CTS-hook version for all teams — that is NOT the final product here, NOT required to finish
    this product, and NOT already approved. It is optional, later, only with CTS-owner approval, if
    they ever ask for it. The team project product is finished when wrapper + plugin work in the
    team project, with or without any CTS change.
    Playwright, Appium, Grid hold, or CI integration.


12. HOW TO HAND THIS SKILL TO CLAUDE — instructions for
the user

The user (not Claude) should do this:

  1. Give Claude this skill file, in the team project workspace.
  2. Say, in their own words: "Follow this skill. First give me the PLAN only, no code. Stop and wait
    for my approval."
  3. Review the PLAN, check every file path, method name, and run command against the real
    repo. Correct anything wrong BEFORE approving code.
  4. Only then say "go" for Spike 1a, then review, then Spike 1b hold, then review.
  5. Bring the PLAN, the code diff, and the run logs back to Muse for review before plugin work.

If Claude's first response contains code instead of a PLAN, stop him and point back to Section 2.
That is a skill violation, not a shortcut.
