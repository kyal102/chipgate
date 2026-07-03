"""
ChipGate OpenLanePhysicalBench — Static HTML report generation.

Generates a self-contained HTML report with no external dependencies.
Uses inline CSS and no JavaScript.
"""

from typing import Any, Dict

from . import __version__, statuses as st


def _status_class(status: str) -> str:
    """Return CSS class for a status value."""
    s = status.upper()
    if "PASS" in s and "FAIL" not in s and "SKIP" not in s:
        return "pass"
    if "FAIL" in s or "MISSING" in s or "LEAK" in s or "INVALID" in s:
        return "fail"
    if "SKIP" in s or "SKIPPED" in s:
        return "skip"
    return "neutral"


def _status_badge(status: str) -> str:
    """Return HTML badge for a status value."""
    cls = _status_class(status)
    short = status.replace("SKIPPED_TOOL_MISSING", "SKIPPED").replace("PHYSICAL_", "PHY_")
    if len(short) > 28:
        short = short[:25] + "..."
    return f'<span class="badge {cls}">{short}</span>'


def generate_physical_html(data: Dict[str, Any]) -> str:
    """Generate a static HTML report for OpenLanePhysicalBench results.

    Args:
        data: Dictionary from OpenLanePhysicalBenchResult.to_dict().

    Returns:
        Complete HTML string.
    """
    timestamp = data.get("timestamp_utc", "unknown")
    version = data.get("benchmark_version", "unknown")
    overall = data.get("overall_status", "unknown")
    designs = data.get("design_results", [])
    tc = data.get("toolchain_report", {})
    metrics = data.get("metrics", {})
    manual_items = data.get("manual_review_items", [])

    public_wording = data.get("public_wording", "")
    limitation = data.get("limitation", "")

    overall_class = _status_class(overall)

    # Build toolchain rows
    tc_rows = ""
    for name, info in tc.items():
        if info.get("found"):
            ver = info.get("version", "")
            ver_str = f" ({ver})" if ver else ""
            tc_rows += (f'<tr><td>{name}</td><td class="pass">found</td>'
                        f'<td>{info.get("path", "")}{ver_str}</td></tr>\n')
        else:
            tc_rows += (f'<tr><td>{name}</td><td class="skip">skipped</td>'
                        f'<td>{info.get("note", "")}</td></tr>\n')

    # Build design rows
    design_rows = ""
    for d in designs:
        design_rows += f"""<tr>
<td><strong>{d.get("design_id", "?")}</strong></td>
<td>{_status_badge(d.get("safety_status", "N/A"))}</td>
<td>{_status_badge(d.get("openlane_config_status", "N/A"))}</td>
<td>{_status_badge(d.get("openroad_run_status", "N/A"))}</td>
<td>{_status_badge(d.get("drc_status", "N/A"))}</td>
<td>{_status_badge(d.get("lvs_status", "N/A"))}</td>
<td>{_status_badge(d.get("timing_status", "N/A"))}</td>
<td>{_status_badge(d.get("gds_status", "N/A"))}</td>
<td>{_status_badge(d.get("overall_status", "N/A"))}</td>
</tr>\n"""

    # Build artifact hash rows
    hash_rows = ""
    for d in designs:
        ev = d.get("evidence_record", {})
        hashes = ev.get("artifact_hashes", [])
        for h in hashes:
            hash_rows += (f'<tr><td>{d.get("design_id", "?")}</td>'
                          f'<td>{h.get("label", "")}</td>'
                          f'<td class="hash">{h.get("sha256", "")[:32]}...</td>'
                          f'<td>{h.get("size_bytes", 0)}</td></tr>\n')

    # Build manual review items
    manual_html = ""
    for item in manual_items:
        manual_html += f"<li>{item}</li>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenLanePhysicalBench Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; color: #1f2937; background: #fff; line-height: 1.6; }}
h1 {{ font-size: 1.6rem; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
h2 {{ font-size: 1.2rem; color: #374151; margin-top: 2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.3rem; }}
.meta {{ color: #6b7280; font-size: 0.875rem; margin-bottom: 1.5rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 1rem; margin: 1rem 0; }}
.card {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; text-align: center; }}
.card .label {{ font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }}
.card .value {{ font-size: 1.5rem; font-weight: 700; color: #111827; }}
.pass {{ color: #16a34a; }} .fail {{ color: #dc2626; }} .skip {{ color: #9ca3af; }} .neutral {{ color: #6366f1; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.8rem; }}
th, td {{ padding: 0.4rem 0.6rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
th {{ background: #f3f4f6; font-weight: 600; position: sticky; top: 0; }}
tr:hover {{ background: #f9fafb; }}
.badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 9999px; font-size: 0.65rem; font-weight: 600; }}
.badge.pass {{ background: #dcfce7; color: #166534; }}
.badge.fail {{ background: #fee2e2; color: #991b1b; }}
.badge.skip {{ background: #f3f4f6; color: #6b7280; }}
.badge.neutral {{ background: #e0e7ff; color: #3730a3; }}
.hash {{ font-family: monospace; font-size: 0.7rem; color: #6b7280; }}
.disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1.5rem 0; font-size: 0.85rem; color: #92400e; }}
.disclaimer strong {{ color: #92400e; }}
.limitation {{ background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: 0.8rem; color: #991b1b; }}
.section {{ margin: 1.5rem 0; }}
ul {{ padding-left: 1.5rem; }}
li {{ margin: 0.25rem 0; }}
</style>
</head>
<body>

<h1>OpenLanePhysicalBench Report</h1>
<p class="meta">ChipGate v{version} | {timestamp}</p>

<div class="disclaimer">
<strong>Public Disclaimer:</strong> {public_wording or st.PHYSICAL_PUBLIC_WORDING}
</div>

<div class="limitation">
<strong>Limitation:</strong> {limitation or st.PHYSICAL_LIMITATION}
</div>

<div class="cards">
<div class="card"><div class="label">Designs Tested</div><div class="value">{metrics.get('designs_tested', 0)}</div></div>
<div class="card"><div class="label">Config Pass Rate</div><div class="value pass">{metrics.get('openlane_config_pass_rate', 0):.0%}</div></div>
<div class="card"><div class="label">OpenROAD Pass Rate</div><div class="value">{metrics.get('openroad_run_pass_rate', 0):.0%}</div></div>
<div class="card"><div class="label">DRC Violations</div><div class="value {'fail' if metrics.get('drc_violation_count', 0) > 0 else 'pass'}">{metrics.get('drc_violation_count', 0)}</div></div>
<div class="card"><div class="label">LVS Mismatches</div><div class="value {'fail' if metrics.get('lvs_mismatch_count', 0) > 0 else 'pass'}">{metrics.get('lvs_mismatch_count', 0)}</div></div>
<div class="card"><div class="label">Worst Neg. Slack</div><div class="value">{metrics.get('worst_negative_slack', 0):.2f}</div></div>
<div class="card"><div class="label">GDS Artifacts</div><div class="value">{metrics.get('gds_artifact_count', 0)}</div></div>
<div class="card"><div class="label">Artifact Hashes</div><div class="value">{metrics.get('artifact_hash_count', 0)}</div></div>
<div class="card"><div class="label">Toolchain</div><div class="value">{metrics.get('toolchain_coverage', 0):.0%}</div></div>
<div class="card"><div class="label">Evidence Packs</div><div class="value">{metrics.get('evidence_packs_created', 0)}</div></div>
<div class="card"><div class="label">Manual Review</div><div class="value">{metrics.get('manual_review_items', 0)}</div></div>
<div class="card"><div class="label">Overall</div><div class="value {overall_class}">{overall}</div></div>
</div>

<div class="section">
<h2>Toolchain Status</h2>
<table>
<tr><th>Tool</th><th>Status</th><th>Details</th></tr>
{tc_rows}
</table>
</div>

<div class="section">
<h2>Design Results</h2>
<table>
<tr>
<th>Design</th><th>Safety</th><th>OL Config</th><th>OR Run</th>
<th>DRC</th><th>LVS</th><th>Timing</th><th>GDS</th><th>Overall</th>
</tr>
{design_rows}
</table>
</div>

{"<div class='section'><h2>Artifact Hashes</h2><table><tr><th>Design</th><th>Label</th><th>SHA-256</th><th>Size</th></tr>" + hash_rows + "</table></div>" if hash_rows else ""}

{"<div class='section'><h2>Manual Review Items</h2><ul>" + manual_html + "</ul></div>" if manual_html else ""}

<div class="disclaimer">
<strong>Reminder:</strong> OpenLanePhysicalBench does not guarantee silicon correctness,
fabrication readiness, timing signoff, real power, real area, physical durability,
regulatory conformance or safety-critical deployment. It checks whether RTL and wrapper
artifacts can pass or be prepared for reproducible physical-design flow stages and
records the resulting reports, hashes and limitations.
</div>

</body>
</html>"""
    return html