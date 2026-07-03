"""
FormalGate-Lite HTML report generator.

Generates a static, dependency-free HTML report with:
  - Overall status and summary cards
  - Safety precheck result
  - Property results table (pass/fail/skip per property)
  - Toolchain status (Verilator, Yosys, sby, etc.)
  - Per-design results
  - Counterexample details
  - Public disclaimer and limitation notice
"""

from typing import Any, Dict


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


def generate_formal_html(data: Dict[str, Any]) -> str:
    """
    Generate a complete static HTML report from a FormalGate-Lite result dict.

    Args:
        data: Dict containing overall_status, timestamp_utc, mode,
              toolchain_status, hygiene, stages, properties,
              counterexamples, designs, public_wording, limitation.

    Returns:
        Complete HTML string.
    """
    overall_status = data.get("overall_status", "N/A")
    timestamp_utc = data.get("timestamp_utc", "")
    mode = data.get("mode", "formal")

    # ── Toolchain rows ──────────────────────────────────────────────
    tc = data.get("toolchain_status", {})
    tc_rows = ""
    for name, info in tc.items():
        if info.get("found"):
            ver = info.get("version", "")
            ver_str = f" ({ver})" if ver else ""
            tc_rows += (
                f'<tr><td>{name}</td>'
                f'<td class="pass">found</td>'
                f'<td>{info.get("path", "")}{ver_str}</td></tr>\n'
            )
        else:
            tc_rows += (
                f'<tr><td>{name}</td>'
                f'<td class="skip">skipped</td>'
                f'<td>{info.get("note", "")}</td></tr>\n'
            )

    # ── Hygiene / safety precheck ───────────────────────────────────
    hygiene = data.get("hygiene", {})
    safety_passed = hygiene.get("safety_precheck_passed", False)
    safety_summary = hygiene.get("summary", "No safety precheck performed.")
    if safety_passed:
        safety_class = "pass"
        safety_label = "PASSED"
    else:
        safety_class = "fail"
        safety_label = "FAILED"
    safety_html = f'<p class="{safety_class}"><strong>{safety_label}</strong> &mdash; {safety_summary}</p>'

    # ── Summary counts ──────────────────────────────────────────────
    properties = data.get("properties", [])
    counterexamples = data.get("counterexamples", [])
    designs = data.get("designs", [])

    prop_passed = sum(1 for p in properties if _status_class(p.get("status", "")) == "pass")
    prop_failed = sum(1 for p in properties if _status_class(p.get("status", "")) == "fail")
    prop_total = len(properties)
    ce_count = len(counterexamples)

    # Toolchain coverage: fraction of tools found
    tc_total = len(tc) if tc else 1
    tc_found = sum(1 for v in tc.values() if v.get("found")) if tc else 0
    tc_coverage = tc_found / tc_total

    overall_cls = "pass" if _status_class(overall_status) == "pass" else "fail"

    # ── Property rows ───────────────────────────────────────────────
    prop_rows = ""
    for p in properties:
        prop_rows += (
            f'<tr>'
            f'<td class="mono">{p.get("property", "")}</td>'
            f'<td>{_status_badge(p.get("status", "N/A"))}</td>'
            f'<td>{p.get("details", "")}</td>'
            f'</tr>\n'
        )

    # ── Counterexample rows ─────────────────────────────────────────
    ce_rows = ""
    for ce in counterexamples:
        ce_rows += (
            f'<tr>'
            f'<td class="mono">{ce.get("property", "")}</td>'
            f'<td>{_status_badge(ce.get("status", "N/A"))}</td>'
            f'<td class="mono">{ce.get("line", "")}</td>'
            f'</tr>\n'
        )

    # ── Design rows ─────────────────────────────────────────────────
    design_rows = ""
    for d in designs:
        d_prop_pass = d.get("properties_passed", 0)
        d_prop_fail = d.get("properties_failed", 0)
        d_ce = d.get("counterexample", "")
        d_ce_html = (
            f'<span class="mono">{d_ce}</span>' if d_ce else '<span class="skip">&mdash;</span>'
        )
        design_rows += (
            f'<tr>'
            f'<td><strong>{d.get("design", "")}</strong></td>'
            f'<td>{_status_badge(d.get("status", "N/A"))}</td>'
            f'<td><span class="pass">{d_prop_pass}</span> / <span class="fail">{d_prop_fail}</span></td>'
            f'<td>{d_ce_html}</td>'
            f'</tr>\n'
        )

    # ── Assemble HTML ───────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FormalGate-Lite Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; color: #1f2937; background: #fff; line-height: 1.6; }}
h1 {{ font-size: 1.6rem; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
h2 {{ font-size: 1.2rem; color: #374151; margin-top: 2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.3rem; }}
.meta {{ color: #6b7280; font-size: 0.875rem; margin-bottom: 1.5rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }}
.card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; text-align: center; }}
.card .label {{ font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }}
.card .value {{ font-size: 1.5rem; font-weight: 700; color: #111827; }}
.pass {{ color: #16a34a; }}
.fail {{ color: #dc2626; }}
.skip {{ color: #9ca3af; }}
.neutral {{ color: #6366f1; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.8rem; }}
th, td {{ padding: 0.4rem 0.6rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
th {{ background: #f3f4f6; font-weight: 600; position: sticky; top: 0; }}
tr:hover {{ background: #f9fafb; }}
.badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 600; }}
.badge.pass {{ background: #dcfce7; color: #166534; }}
.badge.fail {{ background: #fee2e2; color: #991b1b; }}
.badge.skip {{ background: #f3f4f6; color: #6b7280; }}
.badge.neutral {{ background: #e0e7ff; color: #3730a3; }}
.mono {{ font-family: monospace; font-size: 0.8rem; }}
code {{ background: #f3f4f6; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; font-family: monospace; }}
.disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1.5rem 0; font-size: 0.85rem; color: #92400e; }}
.disclaimer strong {{ color: #92400e; }}
.section {{ margin: 1.5rem 0; }}
</style>
</head>
<body>

<h1>FormalGate-Lite Report</h1>
<p class="meta">{mode.upper()} | {timestamp_utc}</p>

<div class="disclaimer">
<strong>Public Disclaimer:</strong> {data.get("public_wording", "This report is generated by FormalGate-Lite for informational purposes only. It does not constitute a formal correctness guarantee.")}
</div>

<div class="cards">
<div class="card"><div class="label">Overall Status</div><div class="value {overall_cls}">{overall_status}</div></div>
<div class="card"><div class="label">Designs Tested</div><div class="value">{len(designs)}</div></div>
<div class="card"><div class="label">Properties Checked</div><div class="value">{prop_total}</div></div>
<div class="card"><div class="label">Properties Passed</div><div class="value pass">{prop_passed}</div></div>
<div class="card"><div class="label">Properties Failed</div><div class="value fail">{prop_failed}</div></div>
<div class="card"><div class="label">Counterexamples Found</div><div class="value fail">{ce_count}</div></div>
<div class="card"><div class="label">Toolchain Coverage</div><div class="value">{tc_coverage:.0%}</div></div>
</div>

<h2>Safety Precheck</h2>
{safety_html}

<h2>Property Results</h2>
<table>
<tr><th>Property</th><th>Status</th><th>Details</th></tr>
{prop_rows}
</table>

<h2>Toolchain Status</h2>
<table>
<tr><th>Tool</th><th>Status</th><th>Details</th></tr>
{tc_rows}
</table>

<h2>Design Results</h2>
<table>
<tr><th>Design</th><th>Status</th><th>Properties (pass / fail)</th><th>Counterexample</th></tr>
{design_rows}
</table>

<h2>Counterexamples</h2>
<table>
<tr><th>Property</th><th>Status</th><th>Line</th></tr>
{ce_rows}
</table>

<div class="disclaimer">
<strong>Limitation:</strong> {data.get("limitation", "FormalGate-Lite uses bounded model checking and may not exhaustively prove all properties. Absence of a counterexample does not guarantee correctness under all possible inputs and sequences.")}
</div>

</body>
</html>"""
    return html