"""DTL Verified Design Passport — Report Generation.

Generates JSON and HTML reports for passport evaluation runs.
HTML reports are static and dependency-free.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .passport_schema import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    PASSPORT_LIMITATION,
    PASSPORT_PUBLIC_WORDING,
    SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------


def generate_passport_json_report(
    passport_build: Dict[str, Any],
    benchmark_name: str = BENCHMARK_NAME,
    benchmark_version: str = BENCHMARK_VERSION,
) -> str:
    """Generate a JSON report string for a passport build.

    Returns a JSON-formatted string.
    """
    passport = passport_build.get("passport", {})
    badge = passport_build.get("badge", {})
    metrics = passport_build.get("metrics", {})
    gate_results = passport_build.get("gate_results", [])

    report: Dict[str, Any] = {
        "benchmark_name": benchmark_name,
        "benchmark_version": benchmark_version,
        "schema_version": SCHEMA_VERSION,
        "passport_id": passport.get("passport_id", ""),
        "artifact_id": passport.get("artifact_id", ""),
        "artifact_type": passport.get("artifact_type", ""),
        "artifact_hash": passport.get("artifact_hash", ""),
        "risk_level": passport.get("risk_level", ""),
        "passport_status": passport.get("passport_status", ""),
        "export_decision": passport.get("export_decision", ""),
        "badge": badge.get("badge", ""),
        "badge_reason": badge.get("reason", ""),
        "certificate_hash": passport.get("certificate_hash", ""),
        "gates_requested": passport.get("gates_requested", []),
        "gates_run": passport.get("gates_run", []),
        "gates_passed": passport.get("gates_passed", []),
        "gates_failed": passport.get("gates_failed", []),
        "evidence_packs": passport.get("evidence_packs", []),
        "artifact_hashes": passport.get("artifact_hashes", {}),
        "replay_command": passport.get("replay_command", ""),
        "manual_review_items": passport.get("manual_review_items", []),
        "limitations": passport.get("limitations", []),
        "metrics": metrics,
        "gate_results": gate_results,
        "public_wording": PASSPORT_PUBLIC_WORDING,
        "limitation": PASSPORT_LIMITATION,
    }

    return json.dumps(report, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def generate_passport_html_report(
    passport_build: Dict[str, Any],
    output_path: str = "",
    benchmark_name: str = BENCHMARK_NAME,
) -> str:
    """Generate a static, dependency-free HTML report.

    If *output_path* is provided, the report is written to that file.
    Returns the HTML string.
    """
    passport = passport_build.get("passport", {})
    badge = passport_build.get("badge", {})
    metrics = passport_build.get("metrics", {})
    gate_results = passport_build.get("gate_results", [])

    # Gate table rows
    gate_rows = ""
    for gr in gate_results:
        status_cls = "pass" if gr.get("passed") else "fail"
        status_txt = "PASS" if gr.get("passed") else "FAIL"
        gate_rows += f"""<tr>
  <td>{gr.get('gate_id', '')}</td>
  <td class="{status_cls}">{status_txt}</td>
  <td>{gr.get('reason', '')}</td>
</tr>
"""

    # Evidence table rows
    evidence_rows = ""
    for ep in passport.get("evidence_packs", []):
        evidence_rows += f"""<tr>
  <td>{ep.get('gate_id', '')}</td>
  <td><code>{ep.get('evidence_hash', '')}</code></td>
</tr>
"""

    # Manual review items
    review_items = ""
    for item in passport.get("manual_review_items", []):
        review_items += f"<li>{item}</li>\n"

    # Artifact hashes
    hash_rows = ""
    for name, h in passport.get("artifact_hashes", {}).items():
        hash_rows += f"<tr><td>{name}</td><td><code>{h}</code></td></tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DTL Verified Design Passport — {passport.get('passport_id', '')}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; color: #333; max-width: 960px; }}
  h1 {{ color: #1a1a2e; border-bottom: 2px solid #16213e; padding-bottom: 0.5rem; }}
  h2 {{ color: #16213e; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #16213e; color: white; }}
  .pass {{ color: #2e7d32; font-weight: bold; }}
  .fail {{ color: #c62828; font-weight: bold; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 4px; color: white; font-weight: bold; }}
  .badge-CHECKED {{ background: #4CAF50; }}
  .badge-BLOCKED {{ background: #F44336; }}
  .badge-NEEDS_REVIEW {{ background: #FF9800; }}
  .badge-REPLAYABLE {{ background: #2196F3; }}
  .badge-UNVERIFIED {{ background: #999; }}
  .badge-MISSING_EVIDENCE {{ background: #FF5722; }}
  .badge-EXTERNAL_REVIEW_PENDING {{ background: #9C27B0; }}
  .limitation {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 1rem; margin: 1rem 0; }}
  code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  .summary-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0; }}
  .summary-card {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 1rem; }}
  .summary-card h3 {{ margin: 0 0 0.5rem 0; color: #495057; }}
  .summary-card p {{ margin: 0; }}
</style>
</head>
<body>
<h1>DTL Verified Design Passport</h1>

<div class="summary-grid">
  <div class="summary-card">
    <h3>Passport ID</h3>
    <p>{passport.get('passport_id', '')}</p>
  </div>
  <div class="summary-card">
    <h3>Artifact ID</h3>
    <p>{passport.get('artifact_id', '')}</p>
  </div>
  <div class="summary-card">
    <h3>Artifact Type</h3>
    <p>{passport.get('artifact_type', '')}</p>
  </div>
  <div class="summary-card">
    <h3>Risk Level</h3>
    <p><strong>{passport.get('risk_level', '')}</strong></p>
  </div>
  <div class="summary-card">
    <h3>Passport Status</h3>
    <p>{passport.get('passport_status', '')}</p>
  </div>
  <div class="summary-card">
    <h3>Export Decision</h3>
    <p>{passport.get('export_decision', '')}</p>
  </div>
  <div class="summary-card">
    <h3>Badge</h3>
    <p><span class="badge badge-{badge.get('badge', 'UNVERIFIED')}">{badge.get('badge', 'UNVERIFIED')}</span></p>
    <p>{badge.get('reason', '')}</p>
  </div>
  <div class="summary-card">
    <h3>Created</h3>
    <p>{passport.get('created_at', '')}</p>
  </div>
</div>

<h2>Gate Results</h2>
<table>
  <tr><th>Gate</th><th>Status</th><th>Reason</th></tr>
  {gate_rows}
</table>

<h2>Evidence Packs</h2>
<table>
  <tr><th>Gate</th><th>Evidence Hash</th></tr>
  {evidence_rows if evidence_rows else '<tr><td colspan="2">No evidence packs</td></tr>'}
</table>

<h2>Replay Command</h2>
<code>{passport.get('replay_command', '')}</code>

<h2>Artifact Hashes</h2>
<table>
  <tr><th>Name</th><th>Hash</th></tr>
  {hash_rows if hash_rows else '<tr><td colspan="2">No hashes</td></tr>'}
</table>

<h2>Certificate Hash</h2>
<code>{passport.get('certificate_hash', '')}</code>

<h2>Manual Review Items</h2>
<ul>
  {review_items if review_items else '<li>None</li>'}
</ul>

<h2>Metrics</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  {chr(10).join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in metrics.items())}
</table>

<div class="limitation">
  <strong>Limitation:</strong> {PASSPORT_LIMITATION}
</div>

<hr>
<p><em>{PASSPORT_PUBLIC_WORDING}</em></p>
<p><small>Benchmark: {benchmark_name} v{BENCHMARK_VERSION}</small></p>

</body>
</html>"""

    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(html)

    return html
