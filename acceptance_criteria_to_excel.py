#!/usr/bin/env python3
"""
Acceptance Criteria to Excel Test Cases
=======================================

Paste Gherkin-style acceptance criteria into the desktop window, then save a
formatted Excel workbook.  The script is deliberately a single file and uses
only Python's standard library -- no `pip install` is required.

It also works from a terminal, which is useful when the acceptance criteria
are already in a text file:

    python3 acceptance_criteria_to_excel.py \
        --input acceptance_criteria.txt \
        --output test_cases.xlsx \
        --label CEPSCRMP-35844 \
        --language EN --also-fr \
        --area RetailRB \
        --page RESL_MATURITY_LISTVIEW

Use `python3 acceptance_criteria_to_excel.py --help` to see every option.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as xml_escape


# ---------------------------------------------------------------------------
# Project conventions.  Change these aliases if your project has other view
# names that should use a specific Test Summary page code.
# ---------------------------------------------------------------------------

PAGE_ALIASES = {
    "my resl maturities list view": "RESL_MATURITY_LISTVIEW",
    "my branch resl maturities list view": "MY_BRANCH_RESL_MATURITY_LISTVIEW",
    "my district resl maturities list view": "MY_DISTRICT_RESL_MATURITY_LISTVIEW",
    "my closed maturities list view": "MY_CLOSED_MATURITIES_LISTVIEW",
    "branch closed maturities list view": "BRANCH_CLOSED_MATURITIES_LISTVIEW",
    "district closed maturities list view": "DISTRICT_CLOSED_MATURITIES_LISTVIEW",
}

ROLE_ORDER = ("PBA", "SPB", "PB", "BM", "DVP")

ROLE_ALIASES = {
    "retail manager": "BM",
    "branch manager": "BM",
    "district vice president": "DVP",
    "district vp": "DVP",
}

HEADERS = (
    "ID",
    "Labels",
    "Lan",
    "Test Summary",
    "Description",
    "Action",
    "Expected Result",
    "Data",
    "Auto/ Assessment",
)

DEFAULT_AUTOMATION = "A: In Sprint Automation"
DEFAULT_SAMPLE = """AC01
Scenario: Add new Opportunity record crm opp maturities locked
Given a Retail user (PBA/SPB/PB) is logged into RB
And the user navigates to the My Closed Maturities list view
When the list view is loaded
Then crm opp maturities locked is added under Opportunity record type

AC02
Scenario: Add new Opportunity record crm opp maturities locked for a manager
Given a Retail Manager is logged into RB
And the user navigates to the Branch Closed Maturities list view
When the list view is loaded
Then crm opp maturities locked is added under Opportunity record type

AC03
Scenario: Add new Opportunity record crm opp maturities locked for DVP
Given DVP is logged into RB
And the user navigates to the District Closed Maturities list view
When the list view is loaded
Then crm opp maturities locked is added under Opportunity record type
"""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Step:
    """One Given/When/Then/And/But statement from an acceptance criterion."""

    marker: str
    content: str

    def render(self) -> str:
        return (self.marker + " " + self.content).strip()


@dataclass
class ParsedCase:
    """A fully parsed test case before it is converted to an Excel row."""

    source_id: str
    language: str
    scenario_title: str
    description: str
    action: str
    expected_result: str
    role: str
    page: str
    suffix: str
    warnings: List[str] = field(default_factory=list)
    test_summary: str = ""


@dataclass
class ConverterOptions:
    label: str = ""
    language: str = "EN"
    # In the desktop app, EN and FR are independent checkboxes.  Leaving this
    # empty keeps backwards-compatible single-language CLI behavior.
    languages: Tuple[str, ...] = ()
    area: str = "RetailRB"
    page_override: str = ""
    role_override: str = ""
    role_mode: str = "primary"
    summary_suffix_override: str = ""
    data: str = ""
    auto_assessment: str = DEFAULT_AUTOMATION
    start_number: int = 1


# ---------------------------------------------------------------------------
# Acceptance-criteria parsing
# ---------------------------------------------------------------------------


AC_HEADER_RE = re.compile(
    r"""^\s*(?P<identifier>
            (?:AC|TC)\s*[-_ ]?\s*\d+
            |Acceptance\s+Criteria\s*[-_ ]?\s*\d+
        )\b\s*[:\-–—]?\s*(?P<tail>.*)$""",
    re.IGNORECASE | re.VERBOSE,
)

SCENARIO_RE = re.compile(
    r"^\s*(?:[-*•]\s*)?(?:scenario|scénario)\s*:\s*(?P<title>.*?)\s*$",
    re.IGNORECASE,
)

BDD_RE = re.compile(
    r"""^\s*(?:[-*•]\s*|\d+[.)]\s*)?
        (?P<marker>
            given|when|then|and|but
            |étant\s+donn[ée]e?|etant\s+donne(?:e)?
            |lorsque|quand|alors|et|mais
        )\b\s*[:\-–—]?\s*(?P<content>.*?)\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

EXPECTED_LABEL_RE = re.compile(
    r"^\s*(?:expected\s+result|expected|résultat\s+attendu)\s*:\s*(?P<content>.*?)\s*$",
    re.IGNORECASE,
)

NOTE_RE = re.compile(r"^\s*(?:note|notes|remarque|remarques|nota)\s*:\s*", re.IGNORECASE)

ACTION_LABEL_RE = re.compile(
    r"^\s*(?:action|steps?|étapes?)\s*:?\s*$", re.IGNORECASE
)

NAVIGATION_RE = re.compile(
    r"""\b(?:
            navigate(?:s|d)?\s+to|go(?:es)?\s+to|open(?:s|ed)?\s+to|access(?:es|ed)?\s+to
            |navigue(?:nt)?\s+vers|naviguer\s+vers|va\s+vers|vont\s+vers
            |ouvre(?:nt)?\s+(?:la\s+|le\s+)?|accède(?:nt)?\s+[àa]
        )\s+(?:the\s+|la\s+|le\s+|l['’])?
        (?P<page>.+?(?:list\s*view|vue\s+de\s+liste|page|screen|écran|tab|onglet))\b""",
    re.IGNORECASE | re.VERBOSE,
)

VIEW_RE = re.compile(
    r"""\b(?P<page>
            (?:my\s+)?[A-Za-z0-9&/\- ]+?(?:list\s*view|vue\s+de\s+liste|screen|écran|tab|onglet)
            |(?:my\s+)?page\s+[A-Za-z0-9&/\- ]+
        )\b""",
    re.IGNORECASE | re.VERBOSE,
)


def normalize_source(text: str) -> str:
    """Clean formatting artefacts commonly introduced by Word, Jira, or PDF."""

    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

    cleaned: List[str] = []
    skipped_headers = {
        "sno",
        "s. no",
        "acceptance criteria",
        "acceptance criterion",
        "description",
        "test summary",
        "labels",
        "lan",
        "language",
        "data",
        "auto assessment",
        "auto/ assessment",
    }

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        # Copying a table from a wiki sometimes leaves a pipe on either side.
        line = re.sub(r"^\|\s*", "", line)
        line = re.sub(r"\s*\|$", "", line)
        line = re.sub(r"[\t ]+", " ", line).strip()
        if line.casefold() in skipped_headers:
            continue
        cleaned.append(line)

    # Keep one blank line as a useful block separator, but remove blank runs.
    result: List[str] = []
    previous_blank = False
    for line in cleaned:
        if not line:
            if not previous_blank:
                result.append("")
            previous_blank = True
        else:
            result.append(line)
            previous_blank = False
    return "\n".join(result).strip()


def canonical_ac_id(value: str, fallback_number: int) -> str:
    """Convert AC-01 / Acceptance Criteria 1 to a tidy AC01 identifier."""

    match = re.search(r"\d+", value)
    if not match:
        return "AC{:02d}".format(fallback_number)
    return "AC{:02d}".format(int(match.group(0)))


def split_ac_blocks(text: str) -> List[Tuple[str, str]]:
    """Split a document into AC-labelled blocks without throwing any text away."""

    blocks: List[Tuple[str, str]] = []
    current_id: Optional[str] = None
    current_lines: List[str] = []
    generated_number = 1

    def flush() -> None:
        nonlocal current_id, current_lines
        body = "\n".join(current_lines).strip()
        if body:
            blocks.append((current_id or "AC{:02d}".format(len(blocks) + 1), body))
        current_id = None
        current_lines = []

    for line in text.splitlines():
        match = AC_HEADER_RE.match(line)
        if match:
            if current_id is not None:
                flush()
            else:
                # A copied Jira selection can include the story title immediately
                # above AC01.  It is context, not a separate test case.
                current_lines = []
            current_id = canonical_ac_id(match.group("identifier"), generated_number)
            generated_number += 1
            tail = match.group("tail").strip()
            if tail:
                current_lines.append(tail)
            continue

        current_lines.append(line)

    flush()
    return blocks or [("AC01", text)] if text.strip() else []


def split_scenarios(block_text: str) -> List[Tuple[str, str]]:
    """Return one or more Scenario blocks contained in an AC block."""

    scenarios: List[Tuple[str, str]] = []
    intro_lines: List[str] = []
    current_title: Optional[str] = None
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if current_title is not None:
            body = "\n".join(current_lines).strip()
            scenarios.append((current_title, body))
        current_title = None
        current_lines = []

    for line in block_text.splitlines():
        match = SCENARIO_RE.match(line)
        if match:
            flush()
            current_title = match.group("title").strip()
            continue
        if current_title is None:
            intro_lines.append(line)
        else:
            current_lines.append(line)

    flush()
    if scenarios:
        # Sometimes a copied table puts an ID or a useful title before Scenario.
        # Keep it with the first scenario rather than discarding it.
        intro = "\n".join(line for line in intro_lines if line.strip()).strip()
        if intro:
            title, body = scenarios[0]
            scenarios[0] = (title, (intro + "\n" + body).strip())
        return scenarios
    return [("", block_text.strip())] if block_text.strip() else []


def canonical_marker(marker: str) -> str:
    """Use English Gherkin labels in Excel even when the input is French."""

    marker = marker.casefold().replace("é", "e")
    mapping = {
        "given": "Given",
        "when": "When",
        "then": "Then",
        "and": "And",
        "but": "But",
        "etant donnee": "Given",
        "etant donne": "Given",
        "lorsque": "When",
        "quand": "When",
        "alors": "Then",
        "et": "And",
        "mais": "But",
    }
    return mapping.get(marker, marker.title())


def parse_bdd_steps(text: str) -> Tuple[List[Step], List[str], List[str]]:
    """Parse line-start Gherkin keywords and attach continuation lines."""

    steps: List[Step] = []
    preamble: List[str] = []
    warnings: List[str] = []
    expected_heading_seen = False
    note_mode = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            note_mode = False
            continue
        if NOTE_RE.match(line):
            note_mode = True
            warnings.append("A Note section was omitted from the test steps; review it manually.")
            continue
        if note_mode:
            # Notes often follow the last AC in a copied Jira table.  They are
            # not part of the prior Then result, but a new Gherkin step resumes
            # normal parsing in case the source contains a real step afterward.
            if not BDD_RE.match(line):
                continue
            note_mode = False
        if ACTION_LABEL_RE.match(line):
            continue
        expected_label = EXPECTED_LABEL_RE.match(line)
        if expected_label:
            expected_heading_seen = True
            content = expected_label.group("content").strip()
            if content:
                steps.append(Step("Then", content))
            continue

        match = BDD_RE.match(line)
        if match:
            marker = canonical_marker(match.group("marker"))
            content = match.group("content").strip()
            # "Expected Result:" may be followed by a plain sentence.  Treat the
            # first sentence after that heading as a Then statement.
            if expected_heading_seen and marker not in ("Then", "And", "But"):
                marker = "Then"
            steps.append(Step(marker, content))
            continue

        if expected_heading_seen and (not steps or steps[-1].marker not in ("Then", "And", "But")):
            steps.append(Step("Then", line))
        elif steps:
            # Preserve wrapped paragraphs copied from Word/PDF.
            steps[-1].content = (steps[-1].content + "\n" + line).strip()
        else:
            preamble.append(line)

    return steps, preamble, ordered_unique(warnings)


def partition_steps(steps: Sequence[Step]) -> Tuple[List[Step], List[Step], List[str]]:
    """Place Given/When steps in Action and Then-and-after steps in Result."""

    action: List[Step] = []
    expected: List[Step] = []
    warnings: List[str] = []
    expected_mode = False

    for step in steps:
        if step.marker == "Then":
            expected_mode = True
        if expected_mode:
            if step.marker in ("Given", "When"):
                warnings.append("Given/When found after Then; review the source formatting.")
            expected.append(step)
        else:
            action.append(step)

    if not action:
        warnings.append("No Given/When action step was found.")
    if not expected:
        warnings.append("No Then/Expected Result step was found.")
    return action, expected, warnings


def render_steps(steps: Iterable[Step]) -> str:
    return "\n".join(step.render() for step in steps).strip()


def compact_text(value: str) -> str:
    """Make a readable one-line description without removing meaningful words."""

    return re.sub(r"\s+", " ", value or "").strip(" .:-")


def choose_description(scenario_title: str, preamble: Sequence[str], expected: Sequence[Step]) -> str:
    """Prefer the explicit Scenario title, then a readable assertion fallback."""

    if compact_text(scenario_title):
        return compact_text(scenario_title)
    if preamble:
        return compact_text(" ".join(preamble))
    if expected:
        description = re.sub(r"^(Then|And|But)\s+", "", expected[0].render(), flags=re.I)
        return compact_text(description)
    return "Acceptance criteria validation"


def ordered_unique(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def extract_roles(action_steps: Sequence[Step], role_override: str, role_mode: str) -> Tuple[List[str], List[str]]:
    """Find PBA/BM/DVP-like roles and apply the requested summary behavior."""

    if role_override.strip():
        overrides = [sanitize_component(x) for x in re.split(r"[,/;]+", role_override)]
        overrides = [value for value in overrides if value]
        return (overrides or ["USER"]), []

    source = " ".join(step.render() for step in action_steps)
    lower = source.casefold()
    found = []
    for role in ROLE_ORDER:
        if re.search(r"\b{}\b".format(re.escape(role)), source, re.IGNORECASE):
            found.append(role)
    for phrase, role in ROLE_ALIASES.items():
        if phrase in lower:
            found.append(role)

    found = ordered_unique(found)
    warnings: List[str] = []
    if not found and "retail user" in lower:
        # The supplied convention uses PBA for a generic Retail user.  This is
        # intentionally easy to override in the UI/CLI when a project differs.
        found = ["PBA"]
    if not found:
        found = [""]
        warnings.append("Could not identify a user role; the role part was omitted from Test Summary.")

    if role_mode == "split":
        return found, warnings
    if role_mode == "combined":
        return ["_".join(found)], warnings

    for preferred in ROLE_ORDER:
        if preferred in found:
            return [preferred], warnings
    return [found[0]], warnings


def lookup_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip(" .,:;-")


def generic_page_code(page: str) -> str:
    """Make a safe, descriptive fallback page code when no alias matches."""

    page = re.sub(r"\b(?:the|la|le)\s+", "", page, flags=re.IGNORECASE)
    page = re.sub(r"\b(?:list\s+view|vue\s+de\s+liste)\b", "LISTVIEW", page, flags=re.IGNORECASE)
    page = re.sub(r"\b(?:page|screen|écran|tab|onglet)\b", lambda m: m.group(0).upper(), page, flags=re.IGNORECASE)
    code = sanitize_component(page)
    return code or "GENERAL"


def extract_page(action_steps: Sequence[Step], page_override: str) -> Tuple[str, List[str]]:
    """Use an explicit page input first, then inspect navigation/action steps."""

    if page_override.strip():
        return sanitize_component(page_override), []

    candidates: List[str] = []
    for step in action_steps:
        navigation = NAVIGATION_RE.search(step.content)
        if navigation:
            candidates.append(navigation.group("page"))
    if not candidates:
        for step in action_steps:
            view = VIEW_RE.search(step.content)
            if view:
                candidates.append(view.group("page"))

    if not candidates:
        return "GENERAL", ["Could not identify the page/view; GENERAL was used in Test Summary."]

    page_text = compact_text(candidates[-1])
    page_text = re.sub(r"^(?:the|la|le|l['’])\s+", "", page_text, flags=re.IGNORECASE)
    page_text = re.sub(r"^(?:page|screen|écran|tab|onglet)\s+", "", page_text, flags=re.IGNORECASE)
    alias = PAGE_ALIASES.get(lookup_key(page_text))
    if alias:
        return alias, []
    return generic_page_code(page_text), ["Used generic page-name normalization for: {}".format(page_text)]


def sanitize_component(value: str, max_words: Optional[int] = None) -> str:
    """Convert any summary component to uppercase words joined with underscores."""

    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    words = re.findall(r"[A-Za-z0-9]+", value.upper())
    if max_words is not None:
        words = words[:max_words]
    return "_".join(words)


def make_suffix(expected: Sequence[Step], scenario_title: str, override: str) -> str:
    """Generate the concise final part of the Test Summary."""

    if override.strip():
        return sanitize_component(override, max_words=14) or "VALIDATION"

    source = " ".join(step.content for step in expected) or scenario_title
    lower = source.casefold()

    comments = "comment" in lower
    visible = bool(
        re.search(
            r"\b(?:visible|display(?:ed|ing)?|shown?|appear(?:s|ed)?|affich(?:é|ée|e|es|er|age)?)\b",
            lower,
        )
    )
    last_column = bool(
        re.search(r"\b(?:last|final|dernier|dernière)\s+(?:field|column|champ|colonne)\b", lower)
        or re.search(r"\b(?:field|column|champ|colonne)\b[^.]{0,45}\b(?:last|final|dernier|dernière)\b", lower)
    )
    character_limit = bool(re.search(r"\b(?:255|character\s+limit|max(?:imum)?)\b", lower))
    if comments and character_limit:
        return "COMMENTS_255_CHARACTER_LIMIT"
    if comments and visible and last_column:
        return "COMMENTS_VISIBLE_AND_LASTCOLUMN"
    if comments and last_column:
        return "COMMENTS_LASTCOLUMN"
    if comments and visible:
        return "COMMENTS_VISIBLE"

    stop_words = {
        "then", "and", "but", "the", "a", "an", "is", "are", "be", "been",
        "shall", "should", "will", "must", "to", "in", "on", "of", "for", "with",
        "under", "as", "at", "by", "from", "that", "this", "it", "become",
        "appear", "appears", "displayed", "display", "should", "result",
    }
    words = [
        word for word in re.findall(r"[A-Za-z0-9]+", source.upper())
        if word.casefold() not in stop_words
    ]
    return "_".join(words[:9]) or "VALIDATION"


def make_summary(area: str, language: str, role: str, page: str, suffix: str) -> str:
    """Follow RetailRB_EN_PBA_RESL_MATURITY_LISTVIEW_WHAT_WAS_TESTED."""

    area = (area or "RetailRB").strip()
    language = sanitize_component(language) or "EN"
    parts = [area, language]
    if role:
        parts.append(sanitize_component(role))
    parts.extend([sanitize_component(page) or "GENERAL", sanitize_component(suffix) or "VALIDATION"])
    return "_".join(part for part in parts if part)


def selected_languages(options: ConverterOptions) -> Tuple[str, ...]:
    """Return the checked/requested language codes in a stable, unique order."""

    source = options.languages or (options.language,)
    codes = ordered_unique(sanitize_component(value) for value in source)
    return tuple(code for code in codes if code) or ("EN",)


def parse_cases(text: str, options: ConverterOptions) -> List[ParsedCase]:
    """Convert source text into one case per AC/scenario/selected role."""

    normalized = normalize_source(text)
    if not normalized:
        raise ValueError("Paste or provide at least one acceptance criterion first.")

    parsed: List[ParsedCase] = []
    for source_id, ac_body in split_ac_blocks(normalized):
        scenarios = split_scenarios(ac_body)
        if not scenarios:
            continue
        for title, scenario_body in scenarios:
            steps, preamble, parser_warnings = parse_bdd_steps(scenario_body)
            action_steps, expected_steps, warnings = partition_steps(steps)
            description = choose_description(title, preamble, expected_steps)
            roles, role_warnings = extract_roles(action_steps, options.role_override, options.role_mode)
            page, page_warnings = extract_page(action_steps, options.page_override)
            suffix = make_suffix(expected_steps, title, options.summary_suffix_override)
            for role in roles:
                for language in selected_languages(options):
                    case = ParsedCase(
                        source_id=source_id,
                        language=language,
                        scenario_title=title,
                        description=description,
                        action=render_steps(action_steps),
                        expected_result=render_steps(expected_steps),
                        role=role,
                        page=page,
                        suffix=suffix,
                        warnings=parser_warnings + warnings + role_warnings + page_warnings,
                    )
                    case.test_summary = make_summary(
                        options.area, case.language, case.role, case.page, case.suffix
                    )
                    parsed.append(case)

    if not parsed:
        raise ValueError("No acceptance-criteria blocks could be read from the supplied text.")

    # Excel test summaries should be unique.  A short numeric suffix is easier
    # to find than silently creating duplicate identifiers.
    seen = {}
    for case in parsed:
        base = case.test_summary
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            case.test_summary = "{}_{}".format(base, seen[base])
            case.warnings.append("Duplicate Test Summary received suffix _{}".format(seen[base]))
    return parsed


# ---------------------------------------------------------------------------
# Minimal, dependency-free XLSX writer
# ---------------------------------------------------------------------------


def xml_text(value: object) -> str:
    """Return XML-safe cell text (Excel accepts at most 32,767 characters)."""

    raw_text = str(value if value is not None else "")[:32767]
    # XML 1.0 rejects clipboard control characters and surrogate code points.
    # Silently removing those is safer than creating an Excel file that cannot
    # be opened because somebody pasted rich text from another application.
    text = "".join(
        char
        for char in raw_text
        if char in "\t\n\r"
        or 0x20 <= ord(char) <= 0xD7FF
        or 0xE000 <= ord(char) <= 0xFFFD
        or 0x10000 <= ord(char) <= 0x10FFFF
    )
    escaped = xml_escape(text, {'"': "&quot;", "'": "&apos;"})
    if text.startswith(" ") or text.endswith(" ") or "\n" in text:
        return '<t xml:space="preserve">{}</t>'.format(escaped)
    return "<t>{}</t>".format(escaped)


def col_letter(number: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""

    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def estimate_row_height(values: Sequence[str]) -> int:
    """Give wrapped acceptance-criteria rows enough room in Excel/LibreOffice."""

    # Approximate characters per visible line based on the narrowest long-text
    # columns.  Clamp so a very long pasted criterion does not create a giant row.
    line_count = 1
    for value, chars_per_line in zip(values, (12, 20, 8, 52, 45, 50, 50, 18, 22)):
        value = str(value or "")
        wrapped = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line) for line in value.split("\n"))
        line_count = max(line_count, wrapped)
    return min(240, max(30, 15 * line_count + 8))


def make_cell(ref: str, value: object, style: int) -> str:
    """Create an inline-string cell.  Values never become accidental formulas."""

    if value is None or value == "":
        return '<c r="{}" s="{}"/>'.format(ref, style)
    return '<c r="{}" s="{}" t="inlineStr"><is>{}</is></c>'.format(
        ref, style, xml_text(value)
    )


def workbook_styles_xml() -> str:
    """Cell styles: default, yellow header, body, and pale-yellow language."""

    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="0"/>
  <fonts count="2">
    <font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
    <font><b/><sz val="11"/><color rgb="FF000000"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
  </fonts>
  <fills count="4">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFFF00"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFD9D9D9"/></left><right style="thin"><color rgb="FFD9D9D9"/></right><top style="thin"><color rgb="FFD9D9D9"/></top><bottom style="thin"><color rgb="FFD9D9D9"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="4">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1" xfId="0"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyBorder="1" applyAlignment="1" xfId="0"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" applyFill="1" applyBorder="1" applyAlignment="1" xfId="0"><alignment horizontal="center" vertical="top" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def sheet_xml(rows: Sequence[Sequence[str]]) -> str:
    """Build the visible Test Cases worksheet XML."""

    widths = (13, 21, 9, 66, 58, 62, 62, 22, 28)
    total_rows = len(rows) + 1
    cols = "".join(
        '<col min="{0}" max="{0}" width="{1}" customWidth="1"/>'.format(index, width)
        for index, width in enumerate(widths, start=1)
    )
    header_cells = "".join(
        make_cell("{}1".format(col_letter(index)), value, 1)
        for index, value in enumerate(HEADERS, start=1)
    )
    row_xml = ['<row r="1" ht="33" customHeight="1">{}</row>'.format(header_cells)]

    for row_number, values in enumerate(rows, start=2):
        cells = []
        for column_number, value in enumerate(values, start=1):
            # Match the supplied template by gently highlighting the language.
            style = 3 if column_number == 3 else 2
            cells.append(make_cell("{}{}".format(col_letter(column_number), row_number), value, style))
        row_xml.append(
            '<row r="{0}" ht="{1}" customHeight="1">{2}</row>'.format(
                row_number, estimate_row_height(values), "".join(cells)
            )
        )

    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:I{total_rows}"/>
  <sheetViews><sheetView workbookViewId="0" showGridLines="0">
    <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    <selection pane="bottomLeft" activeCell="A2" sqref="A2"/>
  </sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>{cols}</cols>
  <sheetData>{row_xml}</sheetData>
  <autoFilter ref="A1:I{total_rows}"/>
  <pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.3" footer="0.3"/>
  <pageSetup orientation="landscape" paperSize="9" fitToWidth="1" fitToHeight="0"/>
</worksheet>""".format(total_rows=total_rows, cols=cols, row_xml="".join(row_xml))


def package_parts(rows: Sequence[Sequence[str]]) -> dict:
    """Return all OOXML files needed for a compact, valid XLSX package."""

    created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <workbookPr/>
  <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews>
  <sheets><sheet name="Test Cases" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        "xl/styles.xml": workbook_styles_xml(),
        "xl/worksheets/sheet1.xml": sheet_xml(rows),
        "docProps/core.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>Acceptance Criteria to Excel</dc:creator>
  <dc:title>Test Cases</dc:title>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>""".format(created=created),
        "docProps/app.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Acceptance Criteria to Excel</Application>
  <Sheets>1</Sheets><TitlesOfParts><vt:vector size="1" baseType="lpstr"><vt:lpstr>Test Cases</vt:lpstr></vt:vector></TitlesOfParts>
</Properties>""",
    }


def verify_xlsx(path: Path) -> None:
    """Catch corrupt archives or malformed XML before reporting success."""

    required = {
        "[Content_Types].xml",
        "_rels/.rels",
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
        "xl/styles.xml",
        "xl/worksheets/sheet1.xml",
    }
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("The generated Excel file did not pass its ZIP integrity check.")
        missing = required.difference(archive.namelist())
        if missing:
            raise ValueError("The generated Excel file is missing: {}".format(", ".join(sorted(missing))))
        # The standard XML parser is sufficient to detect malformed package XML.
        import xml.etree.ElementTree as element_tree
        for name in required:
            if name.endswith(".xml"):
                element_tree.fromstring(archive.read(name))


def write_xlsx(path: Path, cases: Sequence[ParsedCase], options: ConverterOptions) -> Path:
    """Write the final .xlsx file to `path`, then return its final path."""

    if path.suffix.casefold() != ".xlsx":
        path = path.with_suffix(".xlsx")
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for index, case in enumerate(cases, start=options.start_number):
        rows.append(
            (
                "TC-{:03d}".format(index),
                options.label.strip(),
                case.language,
                case.test_summary,
                case.description,
                case.action,
                case.expected_result,
                options.data.strip(),
                options.auto_assessment.strip(),
            )
        )

    parts = package_parts(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content.encode("utf-8"))
    verify_xlsx(path)
    return path


def warning_lines(cases: Sequence[ParsedCase]) -> List[str]:
    """Format per-case parser warnings for the terminal and GUI."""

    messages = []
    for index, case in enumerate(cases, start=1):
        for warning in ordered_unique(case.warnings):
            messages.append("TC-{:03d} ({}): {}".format(index, case.source_id, warning))
    return ordered_unique(messages)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Gherkin-style acceptance criteria into a formatted Excel test-case workbook.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --input criteria.txt --output test_cases.xlsx --label CEPSCRMP-35844 --page RESL_MATURITY_LISTVIEW
  %(prog)s --input - --output test_cases.xlsx --label CEPSCRMP-35844 < criteria.txt
  %(prog)s --example --output sample_test_cases.xlsx
""",
    )
    parser.add_argument("--input", help="Text file containing acceptance criteria. Use - to read from standard input.")
    parser.add_argument("--output", help="Excel file to create (default: test_cases.xlsx).")
    parser.add_argument("--label", default="", help="Value for the Labels column, for example CEPSCRMP-35844.")
    parser.add_argument("--language", default="EN", choices=("EN", "FR"), help="Primary language code for Lan (default: EN).")
    parser.add_argument(
        "--also-fr",
        action="store_true",
        help="Also create an FR row for every test case when the primary language is EN.",
    )
    parser.add_argument("--area", default="RetailRB", help="First part of Test Summary (default: RetailRB).")
    parser.add_argument("--page", default="", help="Page name override, for example RESL_MATURITY_LISTVIEW.")
    parser.add_argument("--role", default="", help="Role override, for example PBA, BM, or DVP.")
    parser.add_argument(
        "--role-mode",
        choices=("primary", "split", "combined"),
        default="primary",
        help="For multi-role criteria: first/primary role, one row per role, or combined roles (default: primary).",
    )
    parser.add_argument("--what-tested", dest="summary_suffix", default="", help="Optional concise Test Summary suffix override.")
    parser.add_argument("--data", default="", help="Default value for the Data column.")
    parser.add_argument("--auto-assessment", default=DEFAULT_AUTOMATION, help="Default Auto/ Assessment value.")
    parser.add_argument("--start-number", default=1, type=int, help="First test-case number (default: 1).")
    parser.add_argument("--example", action="store_true", help="Generate a workbook from the built-in example instead of reading input.")
    return parser


def options_from_args(args: argparse.Namespace) -> ConverterOptions:
    if args.start_number < 1:
        raise ValueError("--start-number must be 1 or greater.")
    languages = (args.language, "FR") if args.also_fr and args.language == "EN" else (args.language,)
    return ConverterOptions(
        label=args.label,
        language=args.language,
        languages=languages,
        area=args.area,
        page_override=args.page,
        role_override=args.role,
        role_mode=args.role_mode,
        summary_suffix_override=args.summary_suffix,
        data=args.data,
        auto_assessment=args.auto_assessment,
        start_number=args.start_number,
    )


def run_cli(args: argparse.Namespace) -> int:
    """Read CLI input, generate a workbook, and print any non-fatal warnings."""

    if args.example:
        source = DEFAULT_SAMPLE
    elif args.input == "-":
        source = sys.stdin.read()
    elif args.input:
        input_path = Path(args.input).expanduser()
        try:
            source = input_path.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError("Could not read {}: {}".format(input_path, error)) from error
    else:
        raise ValueError("Use --input, --example, or start the script without arguments for the paste window.")

    options = options_from_args(args)
    cases = parse_cases(source, options)
    output = Path(args.output or "test_cases.xlsx").expanduser()
    output = write_xlsx(output, cases, options)
    print("Created {} test case(s): {}".format(len(cases), output.resolve()))
    warnings = warning_lines(cases)
    if warnings:
        print("\nReview these parsing notes:")
        for warning in warnings:
            print("- " + warning)
    return 0


# ---------------------------------------------------------------------------
# Paste-friendly Tkinter interface
# ---------------------------------------------------------------------------


def run_gui() -> int:
    """Open the no-dependency desktop interface when no CLI input is supplied."""

    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as error:
        raise RuntimeError(
            "Tkinter is not installed on this Python. Use the --input command-line option instead."
        ) from error

    root = tk.Tk()
    root.title("Acceptance Criteria to Excel")
    root.minsize(940, 680)

    frame = ttk.Frame(root, padding=14)
    frame.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(3, weight=1)
    frame.rowconfigure(5, weight=1)

    label_var = tk.StringVar()
    en_var = tk.BooleanVar(value=True)
    fr_var = tk.BooleanVar(value=False)
    area_var = tk.StringVar(value="RetailRB")
    page_var = tk.StringVar()
    role_var = tk.StringVar()
    suffix_var = tk.StringVar()
    data_var = tk.StringVar()
    assessment_var = tk.StringVar(value=DEFAULT_AUTOMATION)
    start_var = tk.StringVar(value="1")
    status_var = tk.StringVar(value="Paste acceptance criteria, then choose Generate Excel.")

    def add_field(row: int, column: int, label: str, variable: tk.StringVar, width: int = 30) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=column, sticky="w", padx=(0, 7), pady=(0, 6))
        entry = ttk.Entry(frame, textvariable=variable, width=width)
        entry.grid(row=row, column=column + 1, sticky="ew", padx=(0, 14), pady=(0, 6))

    heading = ttk.Label(
        frame,
        text="Acceptance Criteria → Excel Test Cases",
        font=("TkDefaultFont", 15, "bold"),
    )
    heading.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))
    ttk.Label(
        frame,
        text="Tick FR to create matching FR test cases too. The pasted wording is preserved, not translated.",
    ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 12))

    add_field(2, 0, "Labels / Jira key", label_var)
    ttk.Label(frame, text="Create language cases").grid(row=2, column=2, sticky="w", padx=(0, 7), pady=(0, 6))
    language_controls = ttk.Frame(frame)
    language_controls.grid(row=2, column=3, sticky="w", pady=(0, 6))
    ttk.Checkbutton(language_controls, text="EN", variable=en_var).grid(row=0, column=0, padx=(0, 8))
    ttk.Checkbutton(language_controls, text="FR", variable=fr_var).grid(row=0, column=1)

    add_field(3, 0, "Application / area", area_var)
    add_field(3, 2, "Start TC number", start_var, width=10)
    add_field(4, 0, "Page override (optional)", page_var)
    add_field(4, 2, "Role override (optional)", role_var)
    add_field(5, 0, "Tested suffix override (optional)", suffix_var)
    add_field(5, 2, "Data (optional)", data_var)
    add_field(6, 0, "Auto/ Assessment", assessment_var)

    text_label = ttk.Label(frame, text="Acceptance criteria (paste one or more AC blocks here)")
    text_label.grid(row=7, column=0, columnspan=4, sticky="w", pady=(12, 5))
    input_text = tk.Text(frame, height=19, wrap="word", undo=True, font=("TkFixedFont", 11))
    input_text.grid(row=8, column=0, columnspan=4, sticky="nsew")
    frame.rowconfigure(8, weight=1)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=input_text.yview)
    scrollbar.grid(row=8, column=4, sticky="ns")
    input_text.configure(yscrollcommand=scrollbar.set)

    controls = ttk.Frame(frame)
    controls.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(10, 0))
    controls.columnconfigure(5, weight=1)

    def load_text() -> None:
        source_file = filedialog.askopenfilename(
            title="Choose acceptance-criteria text",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
        if not source_file:
            return
        try:
            content = Path(source_file).read_text(encoding="utf-8")
        except OSError as error:
            messagebox.showerror("Could not read file", str(error), parent=root)
            return
        input_text.delete("1.0", "end")
        input_text.insert("1.0", content)
        status_var.set("Loaded {}".format(Path(source_file).name))

    def use_example() -> None:
        input_text.delete("1.0", "end")
        input_text.insert("1.0", DEFAULT_SAMPLE)
        if not label_var.get().strip():
            label_var.set("CEPSCRMP-35844")
        status_var.set("Example loaded. Change any fields, then generate Excel.")

    def collect_options() -> ConverterOptions:
        try:
            start_number = int(start_var.get().strip())
            if start_number < 1:
                raise ValueError
        except ValueError:
            raise ValueError("Start TC number must be 1 or greater.")

        languages = tuple(
            code for code, enabled in (("EN", en_var.get()), ("FR", fr_var.get())) if enabled
        )
        if not languages:
            raise ValueError("Select EN, FR, or both under Create language cases.")

        return ConverterOptions(
            label=label_var.get(),
            language=languages[0],
            languages=languages,
            area=area_var.get(),
            page_override=page_var.get(),
            role_override=role_var.get(),
            summary_suffix_override=suffix_var.get(),
            data=data_var.get(),
            auto_assessment=assessment_var.get(),
            start_number=start_number,
        )

    def check_criteria() -> None:
        try:
            options = collect_options()
            cases = parse_cases(input_text.get("1.0", "end-1c"), options)
        except ValueError as error:
            messagebox.showerror("Criteria need attention", str(error), parent=root)
            return

        notes = warning_lines(cases)
        summaries = "\n".join(
            "• {} [{}]".format(case.test_summary, case.source_id) for case in cases[:8]
        )
        more = "\n• … and {} more".format(len(cases) - 8) if len(cases) > 8 else ""
        message = "Ready to create {} test case(s) in {}.\n\n{}{}".format(
            len(cases), ", ".join(selected_languages(options)), summaries, more
        )
        if notes:
            message += "\n\nReview these notes before exporting:\n" + "\n".join(
                "• " + note for note in notes[:8]
            )
        else:
            message += "\n\nAll criteria have Action and Expected Result steps."
        status_var.set("Check complete: {} test case(s) are ready.".format(len(cases)))
        messagebox.showinfo("Criteria check", message, parent=root)

    def generate() -> None:
        try:
            options = collect_options()
        except ValueError as error:
            messagebox.showerror("Invalid settings", str(error), parent=root)
            return
        try:
            cases = parse_cases(input_text.get("1.0", "end-1c"), options)
        except ValueError as error:
            messagebox.showerror("Nothing to generate", str(error), parent=root)
            return

        output_file = filedialog.asksaveasfilename(
            title="Save Excel test cases",
            defaultextension=".xlsx",
            initialfile="test_cases.xlsx",
            filetypes=(("Excel Workbook", "*.xlsx"),),
        )
        if not output_file:
            return
        try:
            output_path = write_xlsx(Path(output_file), cases, options)
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            messagebox.showerror("Could not create Excel file", str(error), parent=root)
            return

        notes = warning_lines(cases)
        status_var.set("Created {} test case(s): {}".format(len(cases), output_path.name))
        message = "Created {} test case(s).\n\n{}".format(len(cases), output_path)
        if notes:
            visible_notes = "\n".join("• " + note for note in notes[:8])
            more = "\n• … and {} more".format(len(notes) - 8) if len(notes) > 8 else ""
            message += "\n\nPlease review these parsing notes:\n" + visible_notes + more
        messagebox.showinfo("Excel file created", message, parent=root)

    ttk.Button(controls, text="Load text file…", command=load_text).grid(row=0, column=0, padx=(0, 7))
    ttk.Button(controls, text="Use example", command=use_example).grid(row=0, column=1, padx=(0, 7))
    ttk.Button(controls, text="Clear", command=lambda: input_text.delete("1.0", "end")).grid(row=0, column=2, padx=(0, 7))
    ttk.Button(controls, text="Check criteria", command=check_criteria).grid(row=0, column=3, padx=(0, 7))
    ttk.Button(controls, text="Generate Excel…", command=generate).grid(row=0, column=4, padx=(0, 14))
    ttk.Label(controls, textvariable=status_var).grid(row=0, column=5, sticky="e")

    root.mainloop()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        if args.input or args.example:
            return run_cli(args)
        return run_gui()
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
