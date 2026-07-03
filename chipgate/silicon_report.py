"""
ChipGate SiliconReadinessBench HTML report generator.

Generates a static, dependency-free HTML report with:
  - Toolchain status
  - Design table with stage pass/fail/skipped results
  - Cell count / wire count if available
  - Artifact hashes
  - Replay commands
  - Limitations disclaimer
"""

from . import __version__, statuses as st


def _status_class(status: str) -> str:
    """Return CSS class for a status value."""
    s = status.upper()
    if "PASS" in s and "FAIL" not in s and "SKIP" not in s:
        return "pass"
    if "FAIL" in s:
        return "fail"
    if "SKIP" in s or "MISSING" in s or "BLOCKED" in s:
        return "skip"
    return "neutral"


def _status_badge(status: str) -> str:
    """Return HTML badge for a status value."""
    cls = _status_class(status)
    short = status.replace("SKIPPED_TOOL_MISSING", "SKIPPED")
    return f'<span class="badge {cls}">{short}</span>'


def generate_silicon_html(result: dict) -> str:
    """
    Generate a complete static HTML report from a SiliconBenchResult dict.

    Args:
        result: Dict from SiliconBenchResult.to_dict()

    Returns:
        Complete HTML string.
    """
    tc = result.get("toolchain_report", {})
    designs = result.get("design_results", [])

    # Build toolchain rows
    tc_rows = ""
    for name, info in tc.items():
        if info.get("found"):
            ver = info.get("version", "")
            ver_str = f" ({ver})" if ver else ""
            tc_rows += f'<tr><td>{name}</td><td class="pass">found</td><td>{info.get("path", "")}{ver_str}</td></tr>\n'
        else:
            tc_rows += f'<tr><td>{name}</td><td class="skip">skipped</td><td>{info.get("note", "")}</td></tr>\n'

    # Build design rows
    design_rows = ""
    for d in designs:
        design_rows += f"""<tr>
<td><strong>{d["design_id"]}</strong></td>
<td>{_status_badge(d.get("safety_precheck_status", "N/A"))}</td>
<td>{_status_badge(d.get("lint_status", "N/A"))}</td>
<td>{_status_badge(d.get("synthesis_status", "N/A"))}</td>
<td>{_status_badge(d.get("formal_status", "N/A"))}</td>
<td>{_status_badge(d.get("fpga_flow_status", "N/A"))}</td>
<td>{_status_badge(d.get("asic_flow_status", "N/A"))}</td>
<td>{_status_badge(d.get("overall_status", "N/A"))}</td>
<td>{d.get("synthesis_details", {}).get("cell_count", "-")}</td>
<td>{d.get("synthesis_details", {}).get("wire_count", "-")}</td>
</tr>\n"""

    # Artifact hash rows
    hash_rows = ""
    for d in designs:
        ev = d.get("evidence_record", {})
        hashes = ev.get("artifact_hashes", [])
        if hashes:
            for h in hashes:
                hash_rows += f'<tr><td>{d["design_id"]}</td><td>{h.get("label", "")}</td><td class="hash">{h.get("sha256", "")[:24]}...</td></tr>\n'

    # Replay commands
    replay_rows = ""
    for d in designs:
        ev = d.get("evidence_record", {})
        cmd = ev.get("replay_command", "")
        if cmd:
            replay_rows += f'<tr><td>{d["design_id"]}</td><td><code>{cmd}</code></td></tr>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SiliconReadinessBench Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; color: #1f2937; background: #fff; line-height: 1.6; }}
h1 {{ font-size: 1.6rem; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
h2 {{ font-size: 1.2rem; color: #374151; margin-top: 2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.3rem; }}
.meta {{ color: #6b7280; font-size: 0.875rem; margin-bottom: 1.5rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }}
.card {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; text-align: center; }}
.card .label {{ font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }}
.card .value {{ font-size: 1.5rem; font-weight: 700; color: #111827; }}
.pass {{ color: #16a34a; }} .fail {{ color: #dc2626; }} .skip {{ color: #9ca3af; }} .neutral {{ color: #6366f1; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.8rem; }}
th, td {{ padding: 0.4rem 0.6rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
th {{ background: #f3f4f6; font-weight: 600; position: sticky; top: 0; }}
tr:hover {{ background: #f9fafb; }}
.badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 600; }}
.badge.pass {{ background: #dcfce7; color: #166534; }}
.badge.fail {{ background: #fee2e2; color: #991b1b; }}
.badge.skip {{ background: #f3f4f6; color: #6b7280; }}
.badge.neutral {{ background: #e0e7ff; color: #3730a3; }}
.hash {{ font-family: monospace; font-size: 0.7rem; color: #6b7280; }}
code {{ background: #f3f4f6; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; font-family: monospace; }}
.disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1.5rem 0; font-size: 0.85rem; color: #92400e; }}
.disclaimer strong {{ color: #92400e; }}
.limitation {{ background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: 0.8rem; color: #991b1b; }}
.section {{ margin: 1.5rem 0; }}
</style>
</head>
<body>

<h1>SiliconReadinessBench Report</h1>
<p class="meta">ChipGate v{__version__} | {result.get("timestamp_utc", "")} | {result.get("benchmark_name", "")}</p>

<div class="disclaimer">
<strong>Public Disclaimer:</strong> {result.get("public_wording", st.SILICON_PUBLIC_WORDING)}
</div>

<div class="limitation">
<strong>Limitation:</strong> {result.get("limitation", st.SILICON_LIMITATION)}
</div>

<div class="cards">
<div class="card"><div class="label">Designs Tested</div><div class="value">{result.get("designs_tested", 0)}</div></div>
<div class="card"><div class="label">Safety Precheck Passed</div><div class="value pass">{result.get("safety_precheck_passed", 0)}</div></div>
<div class="card"><div class="label">Lint Pass Rate</div><div class="value">{result.get("lint_pass_rate", 0):.0%}</div></div>
<div class="card"><div class="label">Synthesis Pass Rate</div><div class="value">{result.get("synthesis_pass_rate", 0):.0%}</div></div>
<div class="card"><div class="label">Formal Pass Rate</div><div class="value">{result.get("formal_pass_rate", 0):.0%}</div></div>
<div class="card"><div class="label">FPGA Flow Pass Rate</div><div class="value">{result.get("fpga_flow_pass_rate", 0):.0%}</div></div>
<div class="card"><div class="label">ASIC Flow Ready Rate</div><div class="value">{result.get("asic_flow_ready_rate", 0):.0%}</div></div>
<div class="card"><div class="label">Toolchain Coverage</div><div class="value">{result.get("toolchain_coverage", 0):.0%}</div></div>
<div class="card"><div class="label">Evidence Packs</div><div class="value">{result.get("evidence_packs_created", 0)}</div></div>
<div class="card"><div class="label">Overall</div><div class="value {'pass' if result.get('overall_status') == 'SILICON_READINESS_PASS' else 'fail'}">{result.get("overall_status", "N/A")}</div></div>
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
<th>Design</th><th>Safety</th><th>Lint</th><th>Synthesis</th><th>Formal</th><th>FPGA</th><th>ASIC</th><th>Overall</th><th>Cells</th><th>Wires</th>
</tr>
{design_rows}
</table>
</div>

<div class="section">
<h2>Artifact Hashes</h2>
<table>
<tr><th>Design</th><th>Label</th><th>SHA-256</th></tr>
{hash_rows}
</table>
</div>

<div class="section">
<h2>Replay Commands</h2>
<table>
<tr><th>Design</th><th>Command</th></tr>
{replay_rows}
</table>
</div>

<div class="disclaimer">
<strong>Reminder:</strong> SiliconReadinessBench does not guarantee silicon correctness, physical safety, real power, real timing signoff, physical durability, regulatory conformance or fabrication readiness. It checks whether RTL passes reproducible open-source tool-flow readiness stages.
</div>

</body>
</html>"""
    return html