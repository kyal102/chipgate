"""
ChipGate TinyTapeoutPrep — Static HTML report generation.

Generates a self-contained HTML report with no external dependencies.
Uses inline CSS and no JavaScript to keep the report lightweight and safe.
"""

from typing import Any, Dict


def generate_tinytapeout_html(data: Dict[str, Any]) -> str:
    """Generate a static HTML report for TinyTapeoutPrep results.

    Args:
        data: Dictionary from TinyTapeoutPrepResult.to_dict().

    Returns:
        Complete HTML string.
    """
    timestamp = data.get("timestamp_utc", "unknown")
    version = data.get("benchmark_version", "unknown")
    overall = data.get("overall_status", "unknown")
    designs = data.get("design_results", [])
    pinout = data.get("pinout", {})
    checks = data.get("submission_checks", [])
    manual_items = data.get("manual_review_items", [])

    designs_gen = data.get("designs_generated", 0)
    wrappers_gen = data.get("wrappers_generated", 0)
    pinout_pass = data.get("pinout_checks_passed", 0)
    sub_checks_pass = data.get("submission_checks_passed", 0)
    safety_props = data.get("safety_properties_count", 0)
    private_leaks = data.get("private_leak_count", 0)
    testbench_count = data.get("testbench_count", 0)
    evidence_count = data.get("evidence_packs_created", 0)

    public_wording = data.get("public_wording", "")
    limitation = data.get("limitation", "")

    overall_class = "status-pass" if "PASS" in overall else "status-fail"
    overall_label = overall.replace("TINYTAPEOUT_", "TT_")

    # Build check rows
    check_rows = ""
    for chk in checks:
        status = chk.get("status", "PENDING")
        chk_id = chk.get("id", "?")
        name = chk.get("name", "Unknown")
        detail = chk.get("detail", "")
        status_class = "status-pass" if status == "PASS" else (
            "status-fail" if status == "FAIL" else "status-skip"
        )
        detail_str = f" <span class=\"detail\">({detail})</span>" if detail else ""
        check_rows += f"<tr><td>{chk_id}</td><td>{name}</td>" \
                      f"<td class=\"{status_class}\">{status}</td></tr>\n"

    # Build design rows
    design_rows = ""
    for d in designs:
        did = d.get("design_id", "?")
        wrapper = _short_html(d.get("wrapper_status", ""))
        pinout_s = _short_html(d.get("pinout_status", ""))
        subchk = _short_html(d.get("submission_check_status", ""))
        safety = _short_html(d.get("safety_result", ""))
        ov = _short_html(d.get("overall_status", ""))
        design_rows += f"<tr><td>{did}</td><td>{wrapper}</td><td>{pinout_s}</td>" \
                       f"<td>{subchk}</td><td>{safety}</td><td>{ov}</td></tr>\n"

    # Build pinout rows
    pinout_rows = ""
    for pin, sig in sorted(pinout.items()):
        pinout_rows += f"<tr><td class=\"mono\">{pin}</td><td class=\"mono\">{sig}</td></tr>\n"

    # Build manual review items
    manual_html = ""
    for item in manual_items:
        manual_html += f"<li>{item}</li>\n"

    design_table = (
        "<h2>Design Results</h2>\n<table>\n"
        "  <tr><th>Design</th><th>Wrapper</th><th>Pinout</th>\n"
        "      <th>SubChk</th><th>Safety</th><th>Overall</th></tr>\n  "
        + design_rows + "</table>"
    ) if design_rows else ""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ChipGate TinyTapeoutPrep Report</title>
<style>
  :root {{
    --bg: #ffffff;
    --fg: #1a1a2e;
    --muted: #6c757d;
    --accent: #0d6efd;
    --border: #dee2e6;
    --card-bg: #f8f9fa;
    --pass: #198754;
    --fail: #dc3545;
    --skip: #6c757d;
    --warn: #ffc107;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f1117;
      --fg: #e4e4e7;
      --muted: #9ca3af;
      --accent: #60a5fa;
      --border: #374151;
      --card-bg: #1f2937;
      --pass: #4ade80;
      --fail: #f87171;
      --skip: #9ca3af;
      --warn: #fbbf24;
    }}
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1rem;
    background: var(--bg);
    color: var(--fg);
    line-height: 1.6;
  }}
  h1 {{ border-bottom: 2px solid var(--accent); padding-bottom: 0.5rem; }}
  h2 {{ margin-top: 2rem; color: var(--accent); }}
  .meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .status-pass {{ color: var(--pass); font-weight: bold; }}
  .status-fail {{ color: var(--fail); font-weight: bold; }}
  .status-skip {{ color: var(--skip); font-style: italic; }}
  .detail {{ color: var(--muted); font-size: 0.85rem; }}
  .mono {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.9rem; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    font-size: 0.9rem;
  }}
  th, td {{
    border: 1px solid var(--border);
    padding: 0.5rem 0.75rem;
    text-align: left;
  }}
  th {{ background: var(--card-bg); font-weight: 600; }}
  .metrics {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
  }}
  .metric-card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    text-align: center;
  }}
  .metric-value {{ font-size: 1.5rem; font-weight: bold; color: var(--accent); }}
  .metric-label {{ font-size: 0.8rem; color: var(--muted); }}
  .disclaimer {{
    background: var(--card-bg);
    border-left: 3px solid var(--warn);
    padding: 1rem;
    margin: 2rem 0;
    font-size: 0.85rem;
    color: var(--muted);
  }}
  ul {{ padding-left: 1.5rem; }}
  li {{ margin: 0.25rem 0; }}
</style>
</head>
<body>
<h1>ChipGate TinyTapeoutPrep Report</h1>
<p class="meta">Version {version} | {timestamp}</p>

<div class="metrics">
  <div class="metric-card">
    <div class="metric-value">{designs_gen}</div>
    <div class="metric-label">Designs Generated</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{wrappers_gen}</div>
    <div class="metric-label">Wrappers Created</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{pinout_pass}</div>
    <div class="metric-label">Pinout Checks Passed</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{sub_checks_pass}</div>
    <div class="metric-label">Submission Checks Passed</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{safety_props}</div>
    <div class="metric-label">Safety Properties</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{private_leaks}</div>
    <div class="metric-label">Private Leaks</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{testbench_count}</div>
    <div class="metric-label">Testbenches</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{evidence_count}</div>
    <div class="metric-label">Evidence Packs</div>
  </div>
</div>

<h2>Overall Status</h2>
<p class="{overall_class}">{overall_label}</p>

<h2>Pinout Mapping</h2>
<table>
  <tr><th>TinyTapeout Pin</th><th>Signal</th></tr>
  {pinout_rows}
</table>

<h2>Submission Readiness Checks</h2>
<table>
  <tr><th>#</th><th>Check</th><th>Status</th></tr>
  {check_rows}
</table>

{design_table}

{"<h2>Manual Review Items</h2><ul>" + manual_html + "</ul>" if manual_html else ""}

<div class="disclaimer">
  <strong>Limitations:</strong> {limitation or public_wording}
</div>

<p class="meta">Generated by ChipGate TinyTapeoutPrep. This report is an automated
structural check and does not constitute fabrication signoff, Tiny Tapeout
acceptance, or safety certification.</p>

</body>
</html>"""

    return html


def _short_html(status: str) -> str:
    """Convert a status to a short coloured HTML span."""
    s = status.upper() if status else ""
    if "SKIPPED" in s or "SKIP" in s:
        return '<span class="status-skip">SKIP</span>'
    if "PASS" in s and "FAIL" not in s:
        return '<span class="status-pass">PASS</span>'
    if "FAIL" in s or "INVALID" in s or "MISSING" in s or "LEAK" in s:
        return '<span class="status-fail">FAIL</span>'
    return f'<span class="mono">{s[:8]}</span>'