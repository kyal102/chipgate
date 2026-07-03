"""
ChipGate OpenLanePhysicalBench — Unified OpenROAD report parsing.

Provides a single entry point to parse all report types (DRC, LVS,
timing, area, routing/congestion) from a fixtures directory or
individual file paths.

Does not prove physical correctness. It parses text reports.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from .drc_lvs_parser import DRCResult, LVSResult, parse_drc_report, parse_lvs_report
from .timing_report_parser import TimingResult, parse_timing_report, parse_area_stats


class ParsedReports:
    """Container for all parsed reports from a fixtures directory."""
    drc: Optional[DRCResult] = None
    lvs: Optional[LVSResult] = None
    timing: Optional[TimingResult] = None
    area_stats: Optional[Dict] = None
    routing_warnings: List[str] = None  # type: ignore[assignment]
    parsed_count: int = 0
    skipped_count: int = 0
    fixture_files: List[str] = None  # type: ignore[assignment]

    def __init__(self):
        self.drc = None
        self.lvs = None
        self.timing = None
        self.area_stats = None
        self.routing_warnings = []
        self.parsed_count = 0
        self.skipped_count = 0
        self.fixture_files = []

    def to_dict(self) -> dict:
        return {
            "drc": self.drc.to_dict() if self.drc else None,
            "lvs": self.lvs.to_dict() if self.lvs else None,
            "timing": self.timing.to_dict() if self.timing else None,
            "area_stats": self.area_stats,
            "routing_warnings": self.routing_warnings,
            "parsed_count": self.parsed_count,
            "skipped_count": self.skipped_count,
            "fixture_files": self.fixture_files,
        }


# File name to parser mapping (prefix match)
_DRC_PREFIXES = ("drc_", "magic_drc", "drc_report", "drc.")
_LVS_PREFIXES = ("lvs_", "netgen_lvs", "lvs_report", "lvs.")
_TIMING_PREFIXES = ("timing_", "sta_", "timing_report", "timing.")
_AREA_PREFIXES = ("area_", "area_stats", "area.", "cell_stats")
_ROUTING_PREFIXES = ("route_", "routing_", "congestion_", "tritonroute")


def parse_fixtures_directory(fixtures_dir: str) -> ParsedReports:
    """Parse all report fixtures from a directory.

    Automatically detects report type by file name prefix and
    dispatches to the appropriate parser.

    Args:
        fixtures_dir: Path to directory containing report fixture files.

    Returns:
        ParsedReports container with all parsed results.
    """
    result = ParsedReports()
    fix_path = Path(fixtures_dir)
    if not fix_path.is_dir():
        result.skipped_count = 1
        return result

    for f in sorted(fix_path.iterdir()):
        if not f.is_file():
            continue
        name_lower = f.name.lower()
        result.fixture_files.append(f.name)

        text = f.read_text(encoding="utf-8", errors="replace")
        parsed = _parse_single_fixture(name_lower, text, str(f))

        if parsed == "drc":
            result.drc = parse_drc_report(text, str(f))
            result.parsed_count += 1
        elif parsed == "lvs":
            result.lvs = parse_lvs_report(text, str(f))
            result.parsed_count += 1
        elif parsed == "timing":
            result.timing = parse_timing_report(text, str(f))
            result.parsed_count += 1
        elif parsed == "area":
            result.area_stats = parse_area_stats(text, str(f))
            result.parsed_count += 1
        elif parsed == "routing":
            result.routing_warnings = _parse_routing_warnings(text)
            result.parsed_count += 1
        else:
            result.skipped_count += 1

    return result


def _parse_single_fixture(name_lower: str, text: str, path: str) -> str:
    """Determine fixture type from filename and parse.

    Returns one of: "drc", "lvs", "timing", "area", "routing", "unknown".
    """
    for prefix in _DRC_PREFIXES:
        if name_lower.startswith(prefix):
            return "drc"
    for prefix in _LVS_PREFIXES:
        if name_lower.startswith(prefix):
            return "lvs"
    for prefix in _TIMING_PREFIXES:
        if name_lower.startswith(prefix):
            return "timing"
    for prefix in _AREA_PREFIXES:
        if name_lower.startswith(prefix):
            return "area"
    for prefix in _ROUTING_PREFIXES:
        if name_lower.startswith(prefix):
            return "routing"

    # Content-based fallback
    if "drc" in name_lower or "violation" in text[:200].lower():
        return "drc"
    if "lvs" in name_lower or "netlist" in text[:200].lower():
        return "lvs"
    if "timing" in name_lower or "slack" in text[:200].lower():
        return "timing"
    if "area" in name_lower or "cell count" in text[:200].lower():
        return "area"
    if "routing" in name_lower or "congestion" in name_lower:
        return "routing"

    return "unknown"


def _parse_routing_warnings(text: str) -> List[str]:
    """Extract routing/congestion warnings from a report.

    Args:
        text: Full text of the routing report.

    Returns:
        List of warning strings.
    """
    import re
    warnings = []
    # Match lines with "warning" or "congestion" or "overflow"
    for line in text.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if re.search(r"\bwarning\b|\bcongestion\b|\boverflow\b|\bviolation\b",
                     line_stripped, re.IGNORECASE):
            warnings.append(line_stripped[:200])
    return warnings


def parse_single_drc(text: str, source: str = "") -> DRCResult:
    """Convenience wrapper for parse_drc_report."""
    return parse_drc_report(text, source)


def parse_single_lvs(text: str, source: str = "") -> LVSResult:
    """Convenience wrapper for parse_lvs_report."""
    return parse_lvs_report(text, source)


def parse_single_timing(text: str, source: str = "") -> TimingResult:
    """Convenience wrapper for parse_timing_report."""
    return parse_timing_report(text, source)