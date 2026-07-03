"""
ChipGate FormalGate-Lite — Report adapter.

Adapts FormalBenchResult.to_dict() output to the format expected by
formal_report.generate_formal_html(). This thin adapter module keeps
the bench module decoupled from the report module.

Does not guarantee silicon correctness, fabrication readiness, timing signoff,
physical safety, real power or real area.
"""

from typing import Any, Dict


def generate_formal_html(data: Dict[str, Any]) -> str:
    """Generate HTML report from a FormalBenchResult dict.

    This adapter transforms the FormalBenchResult structure into the format
    expected by formal_report.generate_formal_html() and calls that function.

    Args:
        data: Dict from FormalBenchResult.to_dict().

    Returns:
        Complete HTML string.
    """
    from .formal_report import generate_formal_html as _gen_html

    # Transform the data to the format expected by formal_report
    report_data = {
        "overall_status": data.get("overall_status", "N/A"),
        "timestamp_utc": data.get("timestamp_utc", ""),
        "mode": data.get("mode", "formal"),
        "toolchain_status": data.get("toolchain_status", {}),
        "hygiene": {
            "safety_precheck_passed": True,
            "summary": "Safety precheck completed. See design results for details.",
        },
        "properties": _flatten_properties(data),
        "counterexamples": data.get("counterexamples", []),
        "designs": data.get("design_results", []),
        "public_wording": data.get("public_wording", ""),
        "limitation": data.get("limitation", ""),
    }

    # Check if any design has safety failures
    design_results = data.get("design_results", [])
    for d in design_results:
        safety = d.get("safety_status", "")
        if "FAIL" in safety.upper():
            report_data["hygiene"]["safety_precheck_passed"] = False
            report_data["hygiene"]["summary"] = (
                f"Safety precheck FAILED for design: {d.get('design_id', '?')}. "
                "Unsafe designs should not be classified as formally safe."
            )
            break

    return _gen_html(report_data)


def _flatten_properties(data: Dict[str, Any]) -> list:
    """Flatten property results from the FormalBenchResult structure."""
    properties = []

    # Properties are already in the right format from formal_bench
    for p in data.get("properties", []):
        properties.append({
            "property": p.get("property", p.get("property_name", "")),
            "status": p.get("status", ""),
            "details": p.get("details", ""),
        })

    return properties