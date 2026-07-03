"""
ChipGate Formal Verification — Output parser.

Parses output from formal verification tools (SymbiYosys/sby) and mocked
fixture output files used in unit tests.  Extracts pass/fail/unknown counts,
per-property results, counterexample details, and VCD trace metadata.

Does not run formal verification.  It parses text output and extracts
structured data.

Public API
----------
- parse_sby_output(output: str) -> dict
      Parse raw SBY stdout/stderr text.  Returns pass/fail/unknown counts.

- parse_formal_fixture_file(path: str) -> dict
      Parse a fixture formal output file.  Returns counts plus lines and
      per-property breakdowns.

- parse_counterexample(output: str) -> list[dict]
      Parse the counterexample section from formal output.  Returns a list
      of dicts keyed by property, status, and line.

- parse_formal_trace_file(trace_path: str) -> dict
      Parse an SBY VCD trace file produced after a formal failure.  Returns
      trace provenance and extracted signal lines.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FormalResult:
    """Parsed formal verification result summary."""
    passed: int = 0
    failed: int = 0
    unknown: int = 0
    source_file: str = ""
    raw_text: str = ""
    parser_note: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "unknown": self.unknown,
            "source_file": self.source_file,
            "parser_note": self.parser_note,
        }


@dataclass
class FormalPropertyResult:
    """Result for a single checked formal property."""
    name: str = ""
    status: str = ""       # "PASSED", "FAILED", "UNKNOWN"
    line: str = ""          # The raw output line that reported this property

    def to_dict(self) -> dict:
        return {
            "property": self.name,
            "status": self.status,
            "line": self.line,
        }


@dataclass
class FormalTraceResult:
    """Parsed VCD trace metadata from a formal failure."""
    trace_file: str = ""
    property: str = ""      # Name of the property that failed
    extracted_lines: List[str] = field(default_factory=list)
    source_file: str = ""
    parser_note: str = ""

    def to_dict(self) -> dict:
        return {
            "trace_file": self.trace_file,
            "property": self.property,
            "extracted_lines": self.extracted_lines,
            "source_file": self.source_file,
            "parser_note": self.parser_note,
        }


# ---------------------------------------------------------------------------
# Public API — SBY output parser
# ---------------------------------------------------------------------------

def parse_sby_output(output: str) -> dict:
    """Parse SBY output to extract pass/fail/unknown counts.

    SBY output includes lines like::

      PASSED: ...
      FAILED: ...
      [sby] ...

    Returns dict with keys: ``passed`` (int), ``failed`` (int),
    ``unknown`` (int), ``parser_note`` (str).

    Parameters
    ----------
    output : str
        Raw stdout/stderr text produced by ``sby``.

    Returns
    -------
    dict
        ``{passed, failed, unknown, parser_note}``
    """
    result = FormalResult(raw_text=output)
    extracted = _extract_formal_results(output)

    result.passed = extracted["passed"]
    result.failed = extracted["failed"]
    result.unknown = extracted["unknown"]
    result.parser_note = extracted["parser_note"]

    return result.to_dict()


# ---------------------------------------------------------------------------
# Public API — Fixture file parser
# ---------------------------------------------------------------------------

def parse_formal_fixture_file(path: str) -> dict:
    """Parse a fixture formal output file.

    Reads the file at *path*, passes the text through
    :func:`parse_sby_output` for the summary counts, and additionally
    extracts every property-level line.

    Returns dict with keys: ``passed``, ``failed``, ``unknown``,
    ``lines`` (int), ``properties`` (list of dicts).

    Parameters
    ----------
    path : str
        Path to a text file containing formal verification output.

    Returns
    -------
    dict
        ``{passed, failed, unknown, lines, properties}``
    """
    trace = Path(path)

    # Handle missing or empty files
    if not trace.exists():
        return {
            "passed": 0,
            "failed": 0,
            "unknown": 0,
            "lines": 0,
            "properties": [],
        }

    try:
        raw = trace.read_text(encoding="utf-8")
    except OSError:
        return {
            "passed": 0,
            "failed": 0,
            "unknown": 0,
            "lines": 0,
            "properties": [],
        }

    if not raw.strip():
        return {
            "passed": 0,
            "failed": 0,
            "unknown": 0,
            "lines": 0,
            "properties": [],
        }

    # Get the summary counts
    summary = parse_sby_output(raw)

    # Count lines
    line_count = len(raw.splitlines())

    # Extract per-property results
    property_results = _extract_properties(raw)

    return {
        "passed": summary["passed"],
        "failed": summary["failed"],
        "unknown": summary["unknown"],
        "lines": line_count,
        "properties": property_results,
        "parser_note": summary.get("parser_note", ""),
    }


# ---------------------------------------------------------------------------
# Public API — Counterexample parser
# ---------------------------------------------------------------------------

def parse_counterexample(output: str) -> list:
    """Parse counterexample section from formal output.

    Looks for counterexample lines that appear after a ``---`` divider
    or after explicit ``FAILED`` markers in the output.  Each entry is a
    dict with keys ``property`` (str), ``status`` (str), ``line`` (str).

    Parameters
    ----------
    output : str
        Raw formal verification output text.

    Returns
    -------
    list[dict]
        List of ``{property, status, line}`` dicts.
    """
    results: list[dict] = []

    if not output or not output.strip():
        return results

    # Strategy 1: lines after a "----" divider that contain property names
    divider_pattern = re.compile(
        r"^-{3,}",
        re.MULTILINE,
    )
    divider_positions = [m.start() for m in divider_pattern.finditer(output)]

    if divider_positions:
        # Take the section after the last divider
        last_divider_end = divider_positions[-1]
        # Find the newline after the divider line
        newline_after = output.find("\n", last_divider_end)
        if newline_after != -1:
            tail_section = output[newline_after:]
        else:
            tail_section = ""

        for line in tail_section.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            entry = _parse_counterexample_line(stripped)
            if entry:
                results.append(entry)

    # Strategy 2: explicit FAILED lines anywhere in the output
    failed_pattern = re.compile(
        r"(?:FAILED|FAIL)\b[:\s]+(.+)",
        re.IGNORECASE,
    )
    failed_matches = failed_pattern.findall(output)
    for match_text in failed_matches:
        prop_name = match_text.strip().rstrip(".")
        # Avoid duplicates from strategy 1
        existing_names = {r.get("property", "") for r in results}
        if prop_name and prop_name not in existing_names:
            results.append({
                "property": prop_name,
                "status": "FAILED",
                "line": f"FAILED: {match_text.strip()}",
            })

    # Strategy 2b: [error] [SBE] property: name (SBY error format)
    sbe_pattern = re.compile(
        r"\[error\].*?property\s*:\s*(\S+)",
        re.IGNORECASE,
    )
    sbe_matches = sbe_pattern.findall(output)
    for prop_name in sbe_matches:
        existing_names = {r.get("property", "") for r in results}
        if prop_name and prop_name not in existing_names:
            results.append({
                "property": prop_name,
                "status": "FAILED",
                "line": f"counterexample for {prop_name}",
            })

    # Strategy 3: lines with "counterexample" keyword
    cex_pattern = re.compile(
        r"counterexample\s+for\s+(\S+)",
        re.IGNORECASE,
    )
    cex_matches = cex_pattern.findall(output)
    for prop_name in cex_matches:
        existing_names = {r.get("property", "") for r in results}
        if prop_name and prop_name not in existing_names:
            results.append({
                "property": prop_name,
                "status": "FAILED",
                "line": f"counterexample for {prop_name}",
            })

    return results


# ---------------------------------------------------------------------------
# Public API — VCD trace parser
# ---------------------------------------------------------------------------

def parse_formal_trace_file(trace_path: str) -> dict:
    """Parse an SBY VCD trace file (after formal failure).

    Reads the trace file, attempts to identify the property that failed
    (from header comments or file naming conventions), and extracts
    meaningful signal lines.

    Returns dict with keys: ``trace_file`` (str), ``property`` (str),
    ``extracted_lines`` (list[str]).

    Parameters
    ----------
    trace_path : str
        Path to the VCD or text trace file.

    Returns
    -------
    dict
        ``{trace_file, property, extracted_lines}``
    """
    trace = Path(trace_path)
    result = FormalTraceResult(source_file=trace_path)

    # Handle missing trace file
    if not trace.exists():
        return result.to_dict()

    try:
        raw = trace.read_text(encoding="utf-8")
    except OSError:
        return result.to_dict()

    if not raw.strip():
        result.trace_file = str(trace_path)
        return result.to_dict()

    result.trace_file = str(trace_path)

    # Extract the property name from VCD comments or file name
    result.property = _extract_trace_property_name(raw, trace_path)

    # Extract meaningful lines (signal changes, not pure VCD header junk)
    result.extracted_lines = _extract_trace_lines(raw)

    return result.to_dict()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_formal_results(output: str) -> dict:
    """Extract PASSED / FAILED / UNKNOWN counts from SBY-style output.

    Uses ``re.findall`` to locate status markers.  Also handles bracketed
    forms such as ``[sby] PASSED``.

    Parameters
    ----------
    output : str
        Raw SBY output text.

    Returns
    -------
    dict
        ``{passed, failed, unknown, parser_note}``
    """
    passed = 0
    failed = 0
    unknown = 0
    parser_note = ""

    # Pattern 1: PASSED / FAILED / UNKNOWN at line start (SBY property results)
    # Matches lines like "PASS: property_name" or "FAILED: property_name"
    # Uses line-anchored patterns to avoid matching words like "passed" in prose
    line_status_pattern = re.compile(
        r"^\s*(PASSED|PASS|FAILED|FAIL|UNKNOWN)\s*:",
        re.MULTILINE | re.IGNORECASE,
    )
    line_status_matches = line_status_pattern.findall(output)

    passed = 0
    failed = 0
    unknown = 0
    for m in line_status_matches:
        mu = m.upper()
        if mu in ("PASSED", "PASS"):
            passed += 1
        elif mu in ("FAILED", "FAIL"):
            failed += 1
        elif mu == "UNKNOWN":
            unknown += 1

    if passed > 0 or failed > 0 or unknown > 0:
        parser_note = "keyword_counts"
        return {
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
            "parser_note": parser_note,
        }

    # Pattern 2: [sby] status summary lines
    #   e.g. "[sby] tasks: 10.0s  PASSED" or "[sby] PASS"
    sby_status = re.findall(
        r"\[sby\].*\b(?:PASS|FAIL|DONE)\b",
        output,
        re.IGNORECASE,
    )
    if sby_status:
        for line in sby_status:
            if re.search(r"\bPASS\b", line, re.IGNORECASE):
                passed += 1
            if re.search(r"\bFAIL\b", line, re.IGNORECASE):
                failed += 1
        parser_note = "sby_bracket_summary"
        return {
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
            "parser_note": parser_note,
        }

    # Pattern 3: "prove" task status lines
    #   e.g. "prove_0: PASSED" or "task prove: FAILED"
    task_matches = re.findall(
        r"(?:prove|bmc|cover)_[A-Za-z0-9_]*\s*:\s*(PASSED|FAILED|UNKNOWN)",
        output,
        re.IGNORECASE,
    )
    for status in task_matches:
        if status.upper() == "PASSED":
            passed += 1
        elif status.upper() == "FAILED":
            failed += 1
        elif status.upper() == "UNKNOWN":
            unknown += 1

    if task_matches:
        parser_note = "task_status_lines"
        return {
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
            "parser_note": parser_note,
        }

    # No patterns found
    parser_note = "no_patterns_found"
    return {
        "passed": passed,
        "failed": failed,
        "unknown": unknown,
        "parser_note": parser_note,
    }


def _extract_properties(output: str) -> list:
    """Extract per-property results from the formal output.

    Looks for lines matching ``property_name: PASSED/FAILED/UNKNOWN``
    or ``assert property_name: ...`` patterns.

    Parameters
    ----------
    output : str
        Raw formal verification output text.

    Returns
    -------
    list[dict]
        List of ``{property, status, line}`` dicts.
    """
    results: list[dict] = []

    # Pattern 1: "name: PASSED" / "name: FAILED" / "name: UNKNOWN"
    prop_pattern = re.compile(
        r"^\s*(\S+)\s*:\s*(PASSED|FAILED|UNKNOWN)",
        re.MULTILINE | re.IGNORECASE,
    )
    for match in prop_pattern.finditer(output):
        name = match.group(1).strip()
        status = match.group(2).strip().upper()
        full_line = match.group(0).strip()
        results.append({
            "property": name,
            "status": status,
            "line": full_line,
        })

    # Pattern 1b: "STATUS: name" (SBY fixture format)
    status_first_pattern = re.compile(
        r"^\s*(PASSED|PASS|FAILED|FAIL|UNKNOWN)\s*:\s*(\S+)",
        re.MULTILINE | re.IGNORECASE,
    )
    for match in status_first_pattern.finditer(output):
        status = match.group(1).strip().upper()
        name = match.group(2).strip()
        full_line = match.group(0).strip()
        existing_names = {r.get("property", "") for r in results}
        if name not in existing_names:
            results.append({
                "property": name,
                "status": status,
                "line": full_line,
            })

    # Pattern 2: "assert <name>" lines with a status marker
    assert_pattern = re.compile(
        r"assert\s+(\S+)\s+.*?(PASSED|FAILED|UNKNOWN)",
        re.IGNORECASE,
    )
    for match in assert_pattern.finditer(output):
        name = match.group(1).strip()
        status = match.group(2).strip().upper()
        full_line = match.group(0).strip()
        existing_names = {r.get("property", "") for r in results}
        if name not in existing_names:
            results.append({
                "property": name,
                "status": status,
                "line": full_line,
            })

    return results


def _parse_counterexample_line(line: str) -> Optional[dict]:
    """Attempt to parse a single counterexample line.

    Recognised forms::

        property_name: counterexample found
        property_name FAILED
        <signal> = <value>

    Parameters
    ----------
    line : str
        A single stripped output line.

    Returns
    -------
    dict or None
        ``{property, status, line}`` if the line contains a property name
        and status, else ``None``.
    """
    # Property with explicit status
    prop_status = re.match(
        r"(\S+)\s*:\s*(?:counterexample\s+found|FAILED|FAIL|UNKNOWN)",
        line,
        re.IGNORECASE,
    )
    if prop_status:
        return {
            "property": prop_status.group(1).strip(),
            "status": "FAILED",
            "line": line,
        }

    # Property followed by FAILED/FAIL at end of line
    prop_suffix = re.match(
        r"(\S+)\s+(FAILED|FAIL|counterexample)",
        line,
        re.IGNORECASE,
    )
    if prop_suffix:
        return {
            "property": prop_suffix.group(1).strip(),
            "status": "FAILED",
            "line": line,
        }

    return None


def _extract_trace_property_name(raw: str, trace_path: str) -> str:
    """Extract the failed property name from a trace file.

    Attempts three strategies:

    1. VCD ``$comment`` lines that mention a property.
    2. SBY header comment blocks (``// ...``) referencing a property.
    3. File name heuristic (e.g. ``trace_property_name.vcd``).

    Parameters
    ----------
    raw : str
        Raw trace file content.
    trace_path : str
        Path to the trace file (used for the filename heuristic).

    Returns
    -------
    str
        The extracted property name, or an empty string if not found.
    """
    # Strategy 1: VCD $comment lines
    vcd_comment = re.search(
        r"\$comment\s.*?(?:property|assert|check)\s+(\S+)",
        raw,
        re.IGNORECASE,
    )
    if vcd_comment:
        return vcd_comment.group(1).strip()

    # Strategy 2: SBY header // comment lines
    header_comment = re.search(
        r"//\s.*?(?:property|assert|failed|counterexample)\s+[:=]?\s*(\S+)",
        raw,
        re.IGNORECASE,
    )
    if header_comment:
        return header_comment.group(1).strip()

    # Strategy 3: file name heuristic
    #   e.g. "trace_kill_switch_blocks_output.vcd" or "sby_task_prove0.vcd"
    basename = os.path.basename(trace_path)
    # Strip known extensions
    stem = re.sub(r"\.(vcd|txt|log|trace)$", "", basename, flags=re.IGNORECASE)
    # Remove common prefixes
    stem = re.sub(r"^(trace_|sby_|task_|proof_|cex_)", "", stem, flags=re.IGNORECASE)
    if stem:
        return stem

    return ""


def _extract_trace_lines(raw: str) -> list:
    """Extract meaningful signal lines from VCD/trace output.

    Filters out pure VCD header directives and keeps signal value
    changes and timestamp markers.

    Parameters
    ----------
    raw : str
        Raw trace file content.

    Returns
    -------
    list[str]
        List of extracted non-header lines.
    """
    lines: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Skip pure VCD structural headers
        if re.match(
            r"^\s*\$(date|version|timescale|scope|upscope|enddefinitions"
            r"|var|end|dumpvars|endvariables)",
            stripped,
        ):
            continue

        # Keep timestamp lines (#N)
        if re.match(r"^#", stripped):
            lines.append(stripped)
            continue

        # Keep signal value changes (0X, 1X, bXXXX X, etc.)
        if re.match(r"^[01xXzZrbB]", stripped):
            lines.append(stripped)
            continue

        # Keep comment lines ($comment ... $end)
        if re.match(r"^\$comment", stripped):
            lines.append(stripped)
            continue

        # Keep any line that looks like an SBY trace annotation
        if re.match(r"^\[sby\]", stripped):
            lines.append(stripped)
            continue

    return lines
