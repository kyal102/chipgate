"""
ChipGate RealToolchainCI — HTML report generation.

Generates a static dependency-free HTML report with inline CSS.
No JavaScript. Shows toolchain status, stage results, hygiene
checks, demo results, and limitation disclaimers.

Does not guarantee silicon correctness, fabrication readiness, timing
signoff, physical safety, real power or real area.
"""

from typing import Any, Dict
import html as html_mod

from . import __version__, statuses as st


def _sc(status: str) -> str:
    """Return CSS class for a status value."""
    s = status.upper()
    if "PASS" in s and "FAIL" not in s and "SKIP" not in s:
        return "pass"
    if "FAIL" in s:
        return "fail"
    if "SKIP" in s or "PARTIAL" in s:
        return "skip"
    return "neutral"


def _badge(status: str) -> str:
    """Return HTML badge for a status value."""
    cls = _sc(status)
    short = status.replace("SKIPPED_TOOL_MISSING", "SKIPPED").replace(
        "PHYSICAL_FLOW_SKIPPED", "SKIPPED")
    if len(short) > 30:
        short = short[:27] + "..."
    return f'<span class="badge {cls}">{short}</span>'


def generate_ci_html(data: Dict[str, Any]) -> str:
    """Generate a static HTML report for CI results.

    Args:
        data: Dictionary from CIResult.to_dict().

    Returns:
        Complete HTML string.
    """
    ts = data.get("timestamp_utc", "unknown")
    mode = data.get("mode", "quick")
    overall = data.get("overall_status", "unknown")
    tc = data.get("toolchain_status", {})
    hygiene = data.get("hygiene", {})
    stages = data.get("stages", [])
    demos = data.get("demo_results", [])
    metrics = data

    # Toolchain rows
    tc_rows = ""
    for name, info in tc.items():
        if info.get("found"):
            ver = info.get("version", "")
            ver_str = f" ({ver})" if ver else ""
            tc_rows += (f'<tr><td>{name}</td><td class="pass">found</td>'
                        f'<td>{info.get("path", "")}{ver_str}</td></tr>\n')
        else:
            tc_rows += (f'<tr><td>{name}</td><td class="skip">missing</td>'
                        f'<td></td></tr>\n')

    # Stage rows
    stage_rows = ""
    for s in stages:
        stage_rows += f"""<tr>
<td><strong>{s.get("stage_name", "?")}</strong></td>
<td>{_badge(s.get("status", "N/A"))}</td>
<td>{s.get("tool_version", "")[:40]}</td>
<td>{s.get("duration_seconds", 0):.1f}s</td>
<td class="mono">{s.get("command", "")[:60]}</td>
</tr>\n"""

    # Demo rows
    demo_rows = ""
    for d in demos:
        demo_rows += f"""<tr>
<td class="mono">{d.get("command", "?")}</td>
<td>{_badge(d.get("status", "N/A"))}</td>
</tr>\n"""

    # Hygiene checks
    hygiene_items = ""
    for key, val in hygiene.items():
        if key == "issues":
            continue
        if key == "passed":
            continue
        cls = "pass" if val else "fail"
        label = key.replace("no_", "").replace("_", " ").title()
        hygiene_items += f'<li class="{cls}">{label}</li>\n'

    # Hygiene issues — redact the matched phrase to avoid embedding it in HTML
    issues_html = ""
    for issue in hygiene.get("issues", []):
        # Replace the detected phrase with [REDACTED]
        safe_issue = html_mod.escape(issue)
        # Redact text after "detected: " which contains the matched phrase
        if "detected:" in safe_issue:
            prefix, match_text = safe_issue.split("detected:", 1)
            safe_issue = prefix + "detected: [REDACTED]"
        issues_html += f'<li class="fail">{safe_issue}</li>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ChipGate CI Report</title>
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
th {{ background: #f3f4f6; font-weight: 600; }}
.badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 9999px; font-size: 0.65rem; font-weight: 600; }}
.badge.pass {{ background: #dcfce7; color: #166534; }}
.badge.fail {{ background: #fee2e2; color: #991b1b; }}
.badge.skip {{ background: #f3f4f6; color: #6b7280; }}
.badge.neutral {{ background: #e0e7ff; color: #3730a3; }}
.mono {{ font-family: monospace; font-size: 0.75rem; color: #6b7280; }}
.disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1.5rem 0; font-size: 0.85rem; color: #92400e; }}
.disclaimer strong {{ color: #92400e; }}
ul {{ padding-left: 1.5rem; }}
li {{ margin: 0.2rem 0; }}
</style>
</head>
<body>

<h1>ChipGate CI Report</h1>
<p class="meta">ChipGate v{__version__} | {ts} | Mode: {mode}</p>

<div class="disclaimer">
<strong>Public Disclaimer:</strong> {data.get("public_wording", st.CI_PUBLIC_WORDING)}
</div>

<div class="cards">
<div class="card"><div class="label">Overall</div><div class="value {_sc(overall)}">{overall}</div></div>
<div class="card"><div class="label">Tests Passed</div><div class="value pass">{metrics.get("python_tests_passed", 0)}</div></div>
<div class="card"><div class="label">Tests Failed</div><div class="value {'fail' if metrics.get('python_tests_failed', 0) > 0 else 'pass'}">{metrics.get("python_tests_failed", 0)}</div></div>
<div class="card"><div class="label">Tools Found</div><div class="value">{metrics.get("toolchain_tools_found", 0)}</div></div>
<div class="card"><div class="label">Tools Missing</div><div class="value">{metrics.get("toolchain_tools_missing", 0)}</div></div>
<div class="card"><div class="label">Stages Run</div><div class="value">{len(stages)}</div></div>
<div class="card"><div class="label">Demos Run</div><div class="value">{len(demos)}</div></div>
<div class="card"><div class="label">Hashes Created</div><div class="value">{metrics.get("hashes_created", 0)}</div></div>
</div>

<h2>Toolchain Status</h2>
<table><tr><th>Tool</th><th>Status</th><th>Details</th></tr>
{tc_rows}
</table>

<h2>Hygiene Checks</h2>
<ul>{hygiene_items}</ul>
{'<h3>Issues</h3><ul class="fail">' + issues_html + "</ul>" if issues_html else ""}

<h2>Stage Results</h2>
<table>
<tr><th>Stage</th><th>Status</th><th>Version</th><th>Duration</th><th>Command</th></tr>
{stage_rows}
</table>

{"<h2>Demo Commands</h2><table><tr><th>Command</th><th>Status</th></tr>" + demo_rows + "</table>" if demo_rows else ""}

<div class="disclaimer">
<strong>Limitation:</strong> {data.get("limitation", st.CI_LIMITATION)}
</div>

</body>
</html>"""
    return html