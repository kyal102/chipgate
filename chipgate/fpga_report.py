"""
ChipGate FPGABoardBench HTML report generator.

Generates a static, dependency-free HTML report with:
  - Board profiles
  - Design table with safety/pin/synth/PnR/bitstream status
  - Pin constraint check details
  - Board evidence summary
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
    if "FAIL" in s or "MISSING" in s:
        return "fail"
    if "SKIP" in s or "BLOCKED" in s:
        return "skip"
    return "neutral"


def _status_badge(status: str) -> str:
    """Return HTML badge for a status value."""
    cls = _status_class(status)
    short = status.replace("SKIPPED_TOOL_MISSING", "SKIPPED")
    return f'<span class="badge {cls}">{short}</span>'


def _check_badge(check_status: str) -> str:
    """Return HTML badge for a pin constraint check result."""
    if check_status == "PASS":
        return '<span class="badge pass">PASS</span>'
    return '<span class="badge fail">FAIL</span>'


def generate_fpga_html(result: dict) -> str:
    """
    Generate a complete static HTML report from an FPGABenchResult dict.

    Args:
        result: Dict from FPGABenchResult.to_dict()

    Returns:
        Complete HTML string.
    """
    designs = result.get("design_results", [])
    board_profile_name = result.get("board_profile", "generic_fpga")
    tc = result.get("toolchain_report", {})

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
<td><strong>{d["design_id"]}</strong></td>
<td>{_status_badge(d.get("safety_precheck_status", "N/A"))}</td>
<td>{_status_badge(d.get("pin_constraint_status", "N/A"))}</td>
<td>{_status_badge(d.get("fpga_synth_status", "N/A"))}</td>
<td>{_status_badge(d.get("place_route_status", "N/A"))}</td>
<td>{_status_badge(d.get("bitstream_status", "N/A"))}</td>
<td>{_status_badge(d.get("board_evidence_status", "N/A"))}</td>
<td>{_status_badge(d.get("overall_status", "N/A"))}</td>
</tr>\n"""

    # Build pin constraint detail rows
    pin_rows = ""
    for d in designs:
        pin_checks = d.get("pin_constraint_checks", [])
        for chk in pin_checks:
            pin_rows += (f'<tr><td>{d["design_id"]}</td>'
                         f'<td>{chk.get("check", "")}</td>'
                         f'<td>{_check_badge(chk.get("status", ""))}</td>'
                         f'<td>{chk.get("message", "")}</td></tr>\n')

    # Build board evidence rows
    evidence_rows = ""
    for d in designs:
        be = d.get("board_evidence", {})
        if be:
            evidence_rows += (f'<tr>'
                              f'<td>{d["design_id"]}</td>'
                              f'<td>{_status_badge(d.get("board_evidence_status", "N/A"))}</td>'
                              f'<td>{be.get("test_cycles", "N/A")}</td>'
                              f'<td>{be.get("unsafe_enable_events", "N/A")}</td>'
                              f'<td>{be.get("kill_switch_bypasses", "N/A")}</td>'
                              f'<td>{be.get("reset_glitches", "N/A")}</td>'
                              f'<td>{be.get("tester", "N/A")}</td>'
                              f'<td>{be.get("notes", "")}</td>'
                              f'</tr>\n')

    # Artifact hash rows
    hash_rows = ""
    for d in designs:
        ev = d.get("evidence_record", {})
        hashes = ev.get("artifact_hashes", [])
        if hashes:
            for h in hashes:
                hash_rows += (f'<tr><td>{d["design_id"]}</td>'
                              f'<td>{h.get("label", "")}</td>'
                              f'<td class="hash">{h.get("sha256", "")[:24]}...</td>'
                              f'</tr>\n')

    # Replay commands
    replay_rows = ""
    for d in designs:
        ev = d.get("evidence_record", {})
        cmd = ev.get("replay_command", "")
        if cmd:
            replay_rows += (f'<tr><td>{d["design_id"]}</td>'
                            f'<td><code>{cmd}</code></td></tr>\n')

    # Board profile info rows
    profile = result.get("board_profile_info", {})
    profile_rows = ""
    if profile:
        for k, v in profile.items():
            if isinstance(v, list):
                v = ", ".join(v)
            profile_rows += f'<tr><td>{k}</td><td>{v}</td></tr>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FPGABoardBench Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; color: #1f2937; background: #fff; line-height: 1.6; }}
h1 {{ font-size: 1.6rem; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
h2 {{ font-size: 1.2rem; color: #374151; margin-top: 2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.3rem; }}
.meta {{ color: #6b7280; font-size: 0.875rem; margin-bottom: 1.5rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 1rem; margin: 1rem 0; }}
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

<h1>FPGABoardBench Report</h1>
<p class="meta">ChipGate v{__version__} | {result.get("timestamp_utc", "")} | {result.get("benchmark_name", "")} | Board: {board_profile_name}</p>

<div class="disclaimer">
<strong>Public Disclaimer:</strong> {result.get("public_wording", st.FPGA_PUBLIC_WORDING)}
</div>

<div class="limitation">
<strong>Limitation:</strong> {result.get("limitation", st.FPGA_LIMITATION)}
</div>

<div class="cards">
<div class="card"><div class="label">Designs Tested</div><div class="value">{result.get("designs_tested", 0)}</div></div>
<div class="card"><div class="label">Safety Pass Rate</div><div class="value pass">{result.get("safety_precheck_pass_rate", 0):.0%}</div></div>
<div class="card"><div class="label">Pin Constraint Pass</div><div class="value pass">{result.get("pin_constraint_pass_rate", 0):.0%}</div></div>
<div class="card"><div class="label">FPGA Synth Pass</div><div class="value">{result.get("fpga_synth_pass_rate", 0):.0%}</div></div>
<div class="card"><div class="label">Place-Route Pass</div><div class="value">{result.get("place_route_pass_rate", 0):.0%}</div></div>
<div class="card"><div class="label">Bitstream Ready</div><div class="value">{result.get("bitstream_ready_rate", 0):.0%}</div></div>
<div class="card"><div class="label">Board Evidence</div><div class="value">{result.get("board_evidence_attached_count", 0)}</div></div>
<div class="card"><div class="label">Toolchain</div><div class="value">{result.get("toolchain_coverage", 0):.0%}</div></div>
<div class="card"><div class="label">Evidence Packs</div><div class="value">{result.get("evidence_packs_created", 0)}</div></div>
<div class="card"><div class="label">Overall</div><div class="value {'pass' if result.get('overall_status') == 'FPGA_BENCH_PASS' else 'fail'}">{result.get("overall_status", "N/A")}</div></div>
</div>

<div class="section">
<h2>Board Profile: {board_profile_name}</h2>
<table>
<tr><th>Property</th><th>Value</th></tr>
{profile_rows}
</table>
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
<th>Design</th><th>Safety</th><th>Pin Constraints</th><th>FPGA Synth</th>
<th>Place-Route</th><th>Bitstream</th><th>Board Evidence</th><th>Overall</th>
</tr>
{design_rows}
</table>
</div>

<div class="section">
<h2>Pin Constraint Details</h2>
<table>
<tr><th>Design</th><th>Check</th><th>Status</th><th>Message</th></tr>
{pin_rows}
</table>
</div>

<div class="section">
<h2>Board Test Evidence</h2>
<table>
<tr><th>Design</th><th>Status</th><th>Test Cycles</th><th>Unsafe Events</th>
<th>Kill Bypasses</th><th>Reset Glitches</th><th>Tester</th><th>Notes</th></tr>
{evidence_rows}
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
<strong>Reminder:</strong> FPGABoardBench does not guarantee ASIC silicon correctness, physical durability, regulatory conformance, medical safety, defence validation or fabrication readiness. It checks whether safe RTL can pass FPGA-oriented preparation, pin mapping, simulation, bitstream-readiness checks and optional board-test evidence.
</div>

</body>
</html>"""
    return html