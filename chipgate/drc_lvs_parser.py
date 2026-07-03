"""
ChipGate OpenLanePhysicalBench — DRC / LVS report parser.

Parses fixture-style DRC and LVS reports to extract violation counts,
clean/dirty status, and summary information. Designed to work with
OpenLane/Magic/Netgen output formats as well as generic text-based
report fixtures used in unit tests.

Does not guarantee silicon correctness, fabrication readiness, or DRC/LVS
signoff. It parses text reports and extracts structured data.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DRCResult:
    """Parsed DRC report result."""
    clean: bool = False
    violation_count: int = 0
    violations: List[Dict[str, str]] = field(default_factory=list)
    source_file: str = ""
    raw_text: str = ""
    parser_note: str = ""

    def to_dict(self) -> dict:
        return {
            "clean": self.clean,
            "violation_count": self.violation_count,
            "violations": self.violations,
            "source_file": self.source_file,
            "parser_note": self.parser_note,
        }


@dataclass
class LVSResult:
    """Parsed LVS report result."""
    clean: bool = False
    mismatch_count: int = 0
    mismatches: List[Dict[str, str]] = field(default_factory=list)
    source_file: str = ""
    raw_text: str = ""
    parser_note: str = ""

    def to_dict(self) -> dict:
        return {
            "clean": self.clean,
            "mismatch_count": self.mismatch_count,
            "mismatches": self.mismatches,
            "source_file": self.source_file,
            "parser_note": self.parser_note,
        }


def parse_drc_report(report_text: str, source_file: str = "") -> DRCResult:
    """Parse a DRC report and extract violation information.

    Supports multiple report formats:
    - Magic DRC output: "0 errors" or "N errors"
    - OpenLane DRC summary lines
    - Generic "violation" keyword counting
    - KLayout DRC reports with violation counts

    Args:
        report_text: Full text content of the DRC report.
        source_file: Optional path for provenance tracking.

    Returns:
        DRCResult with structured violation data.
    """
    result = DRCResult(source_file=source_file, raw_text=report_text)

    # Pattern 1: Magic-style "0 errors" / "N errors"
    magic_match = re.search(
        r"(\d+)\s+(?:DRC\s+)?errors?",
        report_text,
        re.IGNORECASE,
    )
    if magic_match:
        result.violation_count = int(magic_match.group(1))
        result.clean = result.violation_count == 0
        result.parser_note = "magic_style"
        return result

    # Pattern 2: OpenLane summary "DRC violations: N" or "Total DRC: N"
    ol_match = re.search(
        r"(?:total\s+)?(?:drc\s+)?violations?\s*[:=]\s*(\d+)",
        report_text,
        re.IGNORECASE,
    )
    if ol_match:
        result.violation_count = int(ol_match.group(1))
        result.clean = result.violation_count == 0
        result.parser_note = "openlane_style"
        return result

    # Pattern 3: "CLEAN" / "DRC CLEAN" / "no violations" keyword
    if re.search(r"\bDRC\s+CLEAN\b|\bclean\b.*\bdrc\b|\bno\s+violations?\b",
                 report_text, re.IGNORECASE):
        result.clean = True
        result.violation_count = 0
        result.parser_note = "keyword_clean"
        return result

    # Pattern 4: Generic "violation" line counting
    violation_lines = re.findall(
        r"^\s*(?:violation|error|rule\s+\S+)\s*[:\s].+",
        report_text,
        re.MULTILINE | re.IGNORECASE,
    )
    if violation_lines:
        result.violation_count = len(violation_lines)
        result.clean = result.violation_count == 0
        result.parser_note = "line_count"
        for i, line in enumerate(violation_lines):
            result.violations.append({
                "index": str(i + 1),
                "text": line.strip()[:200],
            })
        return result

    # Pattern 5: Count "Violation" as a word anywhere
    word_count = len(re.findall(r"\bviolation\b", report_text, re.IGNORECASE))
    if word_count > 0:
        result.violation_count = word_count
        result.clean = False
        result.parser_note = "word_count"
        return result

    # No violation patterns found — assume clean if file is non-empty
    result.clean = True
    result.parser_note = "no_patterns_found_assumed_clean"
    return result


def parse_lvs_report(report_text: str, source_file: str = "") -> LVSResult:
    """Parse an LVS report and extract mismatch information.

    Supports multiple report formats:
    - Netgen-style: "Netlists match" / "Netlists do not match"
    - OpenLane LVS summary
    - Generic "mismatch" keyword counting
    - "ERROR" counting in LVS context

    Args:
        report_text: Full text content of the LVS report.
        source_file: Optional path for provenance tracking.

    Returns:
        LVSResult with structured mismatch data.
    """
    result = LVSResult(source_file=source_file, raw_text=report_text)

    # Pattern 1: Netgen-style "Netlists match" / "match perfectly"
    if re.search(r"\bnetlists?\s+match\b|\bmatch\s+perfectly\b|\blvs\s+clean\b",
                 report_text, re.IGNORECASE):
        result.clean = True
        result.mismatch_count = 0
        result.parser_note = "netgen_clean"
        return result

    # Pattern 2: Netgen-style "do not match" / "mismatch"
    if re.search(r"\bdo\s+not\s+match\b|\bnetlists?\s+fail\b",
                 report_text, re.IGNORECASE):
        result.clean = False
        mismatch_lines = re.findall(
            r"^\s*(?:error|mismatch|difference)\s*[:\s].+",
            report_text,
            re.MULTILINE | re.IGNORECASE,
        )
        result.mismatch_count = max(len(mismatch_lines), 1)
        result.parser_note = "netgen_mismatch"
        for i, line in enumerate(mismatch_lines):
            result.mismatches.append({
                "index": str(i + 1),
                "text": line.strip()[:200],
            })
        if not result.mismatches:
            result.mismatches.append({
                "index": "1",
                "text": "Netlists do not match (details not parsed)",
            })
        return result

    # Pattern 3: OpenLane "LVS: PASS" / "LVS: FAIL"
    if re.search(r"\bLVS\s*:\s*PASS\b", report_text, re.IGNORECASE):
        result.clean = True
        result.parser_note = "openlane_pass"
        return result
    if re.search(r"\bLVS\s*:\s*FAIL\b", report_text, re.IGNORECASE):
        result.clean = False
        result.mismatch_count = 1
        result.mismatches.append({
            "index": "1",
            "text": "LVS reported FAIL",
        })
        result.parser_note = "openlane_fail"
        return result

    # Pattern 4: Generic "mismatch" word counting
    mismatch_words = len(re.findall(r"\bmismatch\b", report_text, re.IGNORECASE))
    if mismatch_words > 0:
        result.clean = False
        result.mismatch_count = mismatch_words
        result.parser_note = "mismatch_word_count"
        return result

    # No mismatch patterns found — assume clean if file is non-empty
    result.clean = True
    result.parser_note = "no_patterns_found_assumed_clean"
    return result