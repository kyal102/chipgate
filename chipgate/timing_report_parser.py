"""
ChipGate OpenLanePhysicalBench — Timing report parser.

Parses fixture-style timing reports to extract slack values, clock names,
and pass/fail status. Designed to work with OpenROAD STA output and
generic text-based report fixtures.

Does not prove timing signoff, real clock frequency, or silicon performance.
It parses text reports and extracts structured data.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TimingPath:
    """A single parsed timing path."""
    startpoint: str = ""
    endpoint: str = ""
    slack_ns: float = 0.0
    path_delay_ns: float = 0.0
    clock: str = ""
    is_setup: bool = True
    is_negative_slack: bool = False

    def to_dict(self) -> dict:
        return {
            "startpoint": self.startpoint,
            "endpoint": self.endpoint,
            "slack_ns": self.slack_ns,
            "path_delay_ns": self.path_delay_ns,
            "clock": self.clock,
            "is_setup": self.is_setup,
            "is_negative_slack": self.is_negative_slack,
        }


@dataclass
class TimingResult:
    """Parsed timing report result."""
    pass_status: bool = False
    worst_negative_slack: float = 0.0
    total_negative_slack_paths: int = 0
    paths: List[TimingPath] = field(default_factory=list)
    clock_name: str = ""
    source_file: str = ""
    raw_text: str = ""
    parser_note: str = ""

    def to_dict(self) -> dict:
        return {
            "pass_status": self.pass_status,
            "worst_negative_slack": self.worst_negative_slack,
            "total_negative_slack_paths": self.total_negative_slack_paths,
            "paths": [p.to_dict() for p in self.paths],
            "clock_name": self.clock_name,
            "source_file": self.source_file,
            "parser_note": self.parser_note,
        }


def parse_timing_report(report_text: str, source_file: str = "") -> TimingResult:
    """Parse a timing report and extract slack information.

    Supports multiple report formats:
    - OpenROAD STA: "slack (MET/VIOLATED)" with ns values
    - OpenSTA: "slack" lines with values
    - Generic: "WNS" / "TNS" / "worst negative slack" keywords
    - Simple "TIMING PASS" / "TIMING FAIL" keywords

    Args:
        report_text: Full text content of the timing report.
        source_file: Optional path for provenance tracking.

    Returns:
        TimingResult with structured timing data.
    """
    result = TimingResult(source_file=source_file, raw_text=report_text)

    # Pattern 1: OpenROAD-style "slack (MET)" or "slack (VIOLATED)"
    slack_matches = re.findall(
        r"slack\s*\((?:MET|VIOLATED|met|violated)\)\s+([+-]?\d+\.?\d*)\s*(?:ns|ps)?",
        report_text,
        re.IGNORECASE,
    )
    if slack_matches:
        _process_slack_matches(result, slack_matches)
        return result

    # Pattern 2: "WNS" / "worst negative slack" with value
    wns_match = re.search(
        r"(?:worst\s+negative\s+slack|WNS)\s*[:=]\s*([+-]?\d+\.?\d*)\s*(?:ns|ps)?",
        report_text,
        re.IGNORECASE,
    )
    if wns_match:
        slack_val = float(wns_match.group(1))
        result.worst_negative_slack = min(slack_val, 0.0)
        result.pass_status = slack_val >= 0.0
        result.parser_note = "wns_keyword"
        result.total_negative_slack_paths = 1 if slack_val < 0 else 0
        return result

    # Pattern 3: Generic "slack" lines with numeric values
    generic_slacks = re.findall(
        r"\bslack\s*[:=]\s*([+-]?\d+\.?\d*)\s*(?:ns|ps)?",
        report_text,
        re.IGNORECASE,
    )
    if generic_slacks:
        for s in generic_slacks:
            val = float(s)
            if val < result.worst_negative_slack:
                result.worst_negative_slack = val
            if val < 0:
                result.total_negative_slack_paths += 1
        result.pass_status = result.total_negative_slack_paths == 0
        result.parser_note = "generic_slack_lines"
        return result

    # Pattern 4: Keyword "TIMING PASS" / "timing passed" / "TIMING FAIL"
    if re.search(r"\bTIMING\s+PASS\b|\btiming\s+passed\b|\btiming\s+met\b",
                 report_text, re.IGNORECASE):
        result.pass_status = True
        result.parser_note = "keyword_pass"
        return result
    if re.search(r"\bTIMING\s+FAIL\b|\btiming\s+violated\b|\btiming\s+failed\b",
                 report_text, re.IGNORECASE):
        result.pass_status = False
        result.parser_note = "keyword_fail"
        return result

    # Pattern 5: Look for negative numbers near "slack" anywhere
    negative_near_slack = re.findall(
        r"(?:slack|WNS)\D*?([+-]?\d+\.\d+)",
        report_text,
        re.IGNORECASE,
    )
    if negative_near_slack:
        for s in negative_near_slack:
            val = float(s)
            if val < result.worst_negative_slack:
                result.worst_negative_slack = val
            if val < 0:
                result.total_negative_slack_paths += 1
        result.pass_status = result.total_negative_slack_paths == 0
        result.parser_note = "proximity_slack"
        return result

    # No timing patterns found — assume pass if file is non-empty
    result.pass_status = True
    result.parser_note = "no_patterns_found_assumed_pass"
    return result


def _process_slack_matches(result: TimingResult, matches: list) -> None:
    """Process OpenROAD-style slack matches into a TimingResult."""
    worst = 0.0
    neg_count = 0
    for val_str in matches:
        val = float(val_str)
        if val < 0:
            neg_count += 1
        if val < worst:
            worst = val

    result.worst_negative_slack = worst
    result.total_negative_slack_paths = neg_count
    result.pass_status = neg_count == 0
    result.parser_note = "openroad_style"


def parse_area_stats(report_text: str, source_file: str = "") -> Dict:
    """Parse area/cell statistics from a report.

    Extracts:
    - Cell count
    - Die area (if present)
    - Core area (if present)
    - Utilization percentage (if present)

    Args:
        report_text: Full text content of the area stats report.
        source_file: Optional path for provenance tracking.

    Returns:
        Dict with extracted area statistics.
    """
    stats = {
        "cell_count": None,
        "die_area_um2": None,
        "core_area_um2": None,
        "utilization_pct": None,
        "source_file": source_file,
        "parser_note": "",
    }

    # Cell count: "Cell count: N" / "Number of cells: N" / "#cells N"
    cell_match = re.search(
        r"(?:cell\s*count|number\s+of\s+cells?|#\s*cells?)\s*[:=]\s*(\d+)",
        report_text,
        re.IGNORECASE,
    )
    if cell_match:
        stats["cell_count"] = int(cell_match.group(1))
        stats["parser_note"] = "cell_count_found"

    # Die area: "Die area: XxY um" / "die area = N"
    die_match = re.search(
        r"(?:die\s*area)\s*[:=]\s*([\d.]+)\s*([x*]\s*[\d.]+)?\s*(?:um|um2|mm2)?",
        report_text,
        re.IGNORECASE,
    )
    if die_match:
        area_str = die_match.group(1)
        # If format is "WxH", multiply
        if die_match.group(2):
            h = re.sub(r"[x*\s]", "", die_match.group(2))
            try:
                stats["die_area_um2"] = float(area_str) * float(h)
            except (ValueError, TypeError):
                stats["die_area_um2"] = float(area_str)
        else:
            stats["die_area_um2"] = float(area_str)
        if not stats["parser_note"]:
            stats["parser_note"] += "die_area_found" if not stats["parser_note"] else ", die_area_found"

    # Core area: "Core area: XxY um"
    core_match = re.search(
        r"(?:core\s*area)\s*[:=]\s*([\d.]+)\s*([x*]\s*[\d.]+)?\s*(?:um|um2|mm2)?",
        report_text,
        re.IGNORECASE,
    )
    if core_match:
        area_str = core_match.group(1)
        if core_match.group(2):
            h = re.sub(r"[x*\s]", "", core_match.group(2))
            try:
                stats["core_area_um2"] = float(area_str) * float(h)
            except (ValueError, TypeError):
                stats["core_area_um2"] = float(area_str)
        else:
            stats["core_area_um2"] = float(area_str)

    # Utilization: "Utilization: N%" / "util = N%"
    util_match = re.search(
        r"(?:utilization|util)\s*[:=]\s*([\d.]+)\s*%",
        report_text,
        re.IGNORECASE,
    )
    if util_match:
        stats["utilization_pct"] = float(util_match.group(1))

    if not stats["parser_note"]:
        stats["parser_note"] = "no_patterns_found"

    return stats