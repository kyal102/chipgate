"""ChipGate Lite: deterministic structural sanity checks for Verilog RTL."""

from chipgate.rtl_check import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
    check_file,
    check_source,
    format_report,
)

__all__ = [
    "VERDICT_FAIL",
    "VERDICT_PASS",
    "VERDICT_REVIEW",
    "check_file",
    "check_source",
    "format_report",
]
