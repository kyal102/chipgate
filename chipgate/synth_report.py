"""
ChipSynthBench HTML report generator.

Produces a single, self-contained, dependency-free HTML file
with candidate rankings, PPA proxy comparisons, and evidence hashes.
"""

import html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .synthbench import SynthBenchResult


def generate_synthbench_html(result: "SynthBenchResult") -> str:
    """Generate a complete HTML report from a SynthBenchResult."""
    d = result.to_dict()

    # Build candidate rows
    candidate_rows = _build_candidate_rows(result)
    ranked_rows = _build_ranked_rows(result)
    unsafe_rows = _build_unsafe_rows(result)
    ppa_area_rows = _build_ppa_rows(result, "area")
    ppa_timing_rows = _build_ppa_rows(result, "timing")
    ppa_power_rows = _build_ppa_rows(result, "power")
    evidence_rows = _build_evidence_rows(result)

    # Best tradeoff highlight
    best = result.best_tradeoff_candidate
    best_cls = "green" if best else "red"

    # Status for overall
    overall_status = "SYNTHBENCH_PASS" if result.safe_improved_designs > 0 else "SYNTHBENCH_FAIL"
    overall_cls = "green" if overall_status == "SYNTHBENCH_PASS" else "red"

    return _HTML_TEMPLATE.format(
        timestamp=html.escape(result.timestamp_utc),
        version=html.escape(result.benchmark_version),
        total_candidates=result.total_candidates,
        safe_improved=result.safe_improved_designs,
        unsafe_rejected=result.unsafe_improvements_rejected,
        regressions=result.regressions_detected,
        eligible=result.eligible_for_ranking,
        best_tradeoff=html.escape(best) if best else "None",
        best_cls=best_cls,
        area_imp=f"{result.area_proxy_improvement_pct:.1f}%",
        timing_imp=f"{result.timing_depth_improvement_pct:.1f}%",
        power_imp=f"{result.power_proxy_improvement_pct:.1f}%",
        replay=f"{result.replay_match_rate:.0f}%",
        evidence_count=result.evidence_packs_created,
        bench_hash=html.escape(result.benchmark_hash[:16]),
        overall_status=overall_status,
        overall_cls=overall_cls,
        candidate_rows=candidate_rows,
        ranked_rows=ranked_rows,
        unsafe_rows=unsafe_rows,
        ppa_area_rows=ppa_area_rows,
        ppa_timing_rows=ppa_timing_rows,
        ppa_power_rows=ppa_power_rows,
        evidence_rows=evidence_rows,
        disclaimer=html.escape(result.disclaimer),
        public_wording=html.escape(result.public_wording),
        replay_cmd=html.escape(result.replay_command),
    )


def _build_candidate_rows(result: "SynthBenchResult") -> str:
    """Build the all-candidates table rows."""
    rows = []
    for cr in result.candidate_results:
        safety_cls = "green" if cr.safety_status == "SYNTHBENCH_PASS" else "red"
        longevity_cls = "green" if cr.longevity_status == "SYNTHBENCH_PASS" else "red"
        reg_cls = "green" if cr.no_regression_status == "NO_REGRESSION_PASS" else "red"
        score_display = (
            f"{cr.safe_improvement_score:.4f}"
            if cr.safe_improvement_score != float("-inf")
            else "N/A"
        )
        score_cls = "green" if cr.can_rank else "red"
        rows.append(
            f'<tr>'
            f'<td>{html.escape(cr.candidate_id)}</td>'
            f'<td>{html.escape(cr.description[:60])}</td>'
            f'<td class="{safety_cls}">{html.escape(cr.safety_status)}</td>'
            f'<td class="{longevity_cls}">{html.escape(cr.longevity_status)}</td>'
            f'<td class="{reg_cls}">{html.escape(cr.no_regression_status)}</td>'
            f'<td class="num">{cr.area_proxy_score:.1f}</td>'
            f'<td class="num">{cr.timing_depth_proxy:.2f}</td>'
            f'<td class="num">{cr.power_toggle_proxy:.1f}</td>'
            f'<td class="num">{cr.area_improvement_pct:.1f}%</td>'
            f'<td class="num">{cr.timing_improvement_pct:.1f}%</td>'
            f'<td class="num">{cr.power_improvement_pct:.1f}%</td>'
            f'<td class="num {score_cls}">{score_display}</td>'
            f'<td>{"&#10003;" if cr.can_rank else "&#10007;"}</td>'
            f'<td class="num">{cr.estimated_verification_cost}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _build_ranked_rows(result: "SynthBenchResult") -> str:
    """Build the ranked candidates table rows."""
    rows = []
    for i, ds in enumerate(result.ranked_candidates, 1):
        score_display = (
            f"{ds.safe_improvement_score:.4f}"
            if ds.safe_improvement_score != float("-inf")
            else "N/A (disqualified)"
        )
        tradeoff_badge = ""
        if ds.is_best_tradeoff:
            tradeoff_badge = ' <span class="badge-best">BEST</span>'
        cls = "best-row" if ds.is_best_tradeoff else ("rank-row" if ds.can_rank else "disqualified-row")
        rows.append(
            f'<tr class="{cls}">'
            f'<td class="num">#{i}</td>'
            f'<td>{html.escape(ds.candidate_id)}{tradeoff_badge}</td>'
            f'<td class="num {("green" if ds.safety_pass else "red")}">{"PASS" if ds.safety_pass else "FAIL"}</td>'
            f'<td class="num {("green" if ds.longevity_pass else "red")}">{"PASS" if ds.longevity_pass else "FAIL"}</td>'
            f'<td class="num {("green" if ds.no_regression_pass else "red")}">{"PASS" if ds.no_regression_pass else "FAIL"}</td>'
            f'<td class="num">{ds.area_improvement_pct:.1f}%</td>'
            f'<td class="num">{ds.timing_improvement_pct:.1f}%</td>'
            f'<td class="num">{ds.power_improvement_pct:.1f}%</td>'
            f'<td class="num">{score_display}</td>'
            f'<td>{html.escape(ds.reason[:80])}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _build_unsafe_rows(result: "SynthBenchResult") -> str:
    """Build the unsafe-rejected candidates rows."""
    unsafe = [cr for cr in result.candidate_results
              if cr.safety_status == "SYNTHBENCH_FAIL"]
    if not unsafe:
        return '<tr><td colspan="4" class="center">No unsafe candidates in this benchmark</td></tr>'
    rows = []
    for cr in unsafe:
        rows.append(
            f'<tr class="fail-row">'
            f'<td>{html.escape(cr.candidate_id)}</td>'
            f'<td>{html.escape(cr.description[:60])}</td>'
            f'<td>{html.escape(cr.safety_status)}</td>'
            f'<td>{html.escape(cr.design_score_reason[:80])}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _build_ppa_rows(result: "SynthBenchResult", metric: str) -> str:
    """Build PPA comparison rows for a specific metric."""
    rows = []
    for cr in result.candidate_results:
        if metric == "area":
            val = cr.area_proxy_score
            imp = cr.area_improvement_pct
            status = cr.area_status
        elif metric == "timing":
            val = cr.timing_depth_proxy
            imp = cr.timing_improvement_pct
            status = cr.timing_status
        else:
            val = cr.power_toggle_proxy
            imp = cr.power_improvement_pct
            status = cr.power_status

        cls = "green" if "IMPROVED" in status else ("red" if "REGRESSED" in status else "")
        rows.append(
            f'<tr>'
            f'<td>{html.escape(cr.candidate_id)}</td>'
            f'<td class="num">{val:.2f}</td>'
            f'<td class="num {cls}">{imp:.1f}%</td>'
            f'<td>{html.escape(status)}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _build_evidence_rows(result: "SynthBenchResult") -> str:
    """Build evidence hash rows."""
    rows = []
    for cr in result.candidate_results:
        rows.append(
            f'<tr>'
            f'<td>{html.escape(cr.candidate_id)}</td>'
            f'<td class="hash">{html.escape(cr.rtl_hash[:16])}...</td>'
            f'<td class="hash">{html.escape(cr.evidence_hash[:16])}...</td>'
            f'<td><code>{html.escape(cr.replay_command)}</code></td>'
            f'</tr>'
        )
    return "\n".join(rows)


# ── HTML Template ──────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ChipSynthBench Report</title>
<style>
  :root {{ --green: #16a34a; --red: #dc2626; --blue: #2563eb; --gray: #6b7280; --bg: #f9fafb; --card-bg: #ffffff; --amber: #d97706; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: #1f2937; line-height: 1.6; padding: 2rem; }}
  h1 {{ font-size: 1.75rem; margin-bottom: 0.25rem; }}
  h2 {{ font-size: 1.25rem; margin: 2rem 0 1rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
  .subtitle {{ color: var(--gray); margin-bottom: 2rem; }}
  .disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1rem 0 2rem; font-size: 0.875rem; color: #92400e; }}
  .public-wording {{ background: #f3f4f6; border-radius: 8px; padding: 1rem; margin: 1rem 0 1rem; font-size: 0.875rem; color: #374151; font-style: italic; }}
  .banner {{ background: #1e40af; color: white; border-radius: 8px; padding: 1rem; margin: 1rem 0 2rem; font-size: 0.875rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0 2rem; }}
  .card {{ background: var(--card-bg); border-radius: 12px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .card .label {{ font-size: 0.75rem; color: var(--gray); text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ font-size: 2rem; font-weight: 700; margin-top: 0.25rem; }}
  .card .value.green {{ color: var(--green); }}
  .card .value.red {{ color: var(--red); }}
  .card .value.blue {{ color: var(--blue); }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.8rem; }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
  th {{ background: #f3f4f6; font-weight: 600; position: sticky; top: 0; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .center {{ text-align: center; color: var(--gray); }}
  .green {{ color: var(--green); font-weight: 600; }}
  .red {{ color: var(--red); font-weight: 600; }}
  .blue {{ color: var(--blue); }}
  .hash {{ font-family: 'Courier New', monospace; font-size: 0.75rem; }}
  .fail-row {{ background: #fef2f2; }}
  .best-row {{ background: #f0fdf4; font-weight: 600; }}
  .rank-row {{ background: #ffffff; }}
  .disqualified-row {{ background: #fef2f2; opacity: 0.7; }}
  .badge-best {{ background: var(--green); color: white; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.65rem; font-weight: 700; margin-left: 0.5rem; }}
  code {{ background: #f3f4f6; padding: 0.1rem 0.3rem; border-radius: 4px; font-size: 0.75rem; }}
  .meta {{ font-size: 0.75rem; color: var(--gray); margin-top: 2rem; }}
  .ppa-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin: 1rem 0; }}
  .ppa-panel {{ background: var(--card-bg); border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; }}
  .ppa-panel h3 {{ font-size: 0.9rem; margin-bottom: 0.5rem; }}
  @media (max-width: 768px) {{ body {{ padding: 1rem; }} .cards {{ grid-template-columns: repeat(2, 1fr); }} .ppa-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>ChipSynthBench Report</h1>
<p class="subtitle">Version {version} &mdash; Generated {timestamp}</p>

<div class="banner">
  <strong>ChipSynthBench</strong> measures whether RTL candidates become safer,
  smaller and faster without regression. Results use RTL-level proxy metrics only.
</div>

<div class="disclaimer">
  <strong>Limitation:</strong> {disclaimer}
</div>

<div class="public-wording">
  {public_wording}
</div>

<h2>Summary</h2>
<div class="cards">
  <div class="card"><div class="label">Overall Status</div><div class="value {overall_cls}">{overall_status}</div></div>
  <div class="card"><div class="label">Total Candidates</div><div class="value blue">{total_candidates}</div></div>
  <div class="card"><div class="label">Safe Improved</div><div class="value green">{safe_improved}</div></div>
  <div class="card"><div class="label">Unsafe Rejected</div><div class="value red">{unsafe_rejected}</div></div>
  <div class="card"><div class="label">Regressions Detected</div><div class="value red">{regressions}</div></div>
  <div class="card"><div class="label">Eligible for Ranking</div><div class="value blue">{eligible}</div></div>
  <div class="card"><div class="label">Best Tradeoff</div><div class="value green">{best_tradeoff}</div></div>
  <div class="card"><div class="label">Area Proxy Improvement</div><div class="value green">{area_imp}</div></div>
  <div class="card"><div class="label">Timing Proxy Improvement</div><div class="value green">{timing_imp}</div></div>
  <div class="card"><div class="label">Power Proxy Improvement</div><div class="value green">{power_imp}</div></div>
  <div class="card"><div class="label">Replay Match</div><div class="value green">{replay}</div></div>
  <div class="card"><div class="label">Evidence Packs</div><div class="value blue">{evidence_count}</div></div>
</div>

<h2>Candidate Rankings</h2>
<p style="font-size:0.8rem;color:var(--gray);margin-bottom:0.5rem;">
  Only candidates that pass safety, longevity, and no-regression are eligible for ranking.
  Unsafe designs cannot rank above safe designs even if they look smaller or faster.
</p>
<table>
  <tr>
    <th>Rank</th><th>Candidate</th><th>Safety</th><th>Longevity</th><th>No-Regr.</th>
    <th>Area Imp.</th><th>Timing Imp.</th><th>Power Imp.</th><th>Score</th><th>Reason</th>
  </tr>
  {ranked_rows}
</table>

<h2>All Candidate Results</h2>
<table>
  <tr>
    <th>Candidate</th><th>Description</th><th>Safety</th><th>Longevity</th><th>No-Regr.</th>
    <th>Area</th><th>Timing</th><th>Power</th>
    <th>Area %</th><th>Timing %</th><th>Power %</th>
    <th>Score</th><th>Can Rank</th><th>Est. Cost</th>
  </tr>
  {candidate_rows}
</table>

<h2>PPA Proxy Comparison</h2>
<div class="ppa-grid">
  <div class="ppa-panel">
    <h3>Area Proxy</h3>
    <table>
      <tr><th>Candidate</th><th>Score</th><th>vs Baseline</th><th>Status</th></tr>
      {ppa_area_rows}
    </table>
  </div>
  <div class="ppa-panel">
    <h3>Timing-Depth Proxy</h3>
    <table>
      <tr><th>Candidate</th><th>Score</th><th>vs Baseline</th><th>Status</th></tr>
      {ppa_timing_rows}
    </table>
  </div>
  <div class="ppa-panel">
    <h3>Power-Toggle Proxy</h3>
    <table>
      <tr><th>Candidate</th><th>Score</th><th>vs Baseline</th><th>Status</th></tr>
      {ppa_power_rows}
    </table>
  </div>
</div>

<h2>Unsafe Candidates (Rejected)</h2>
<table>
  <tr><th>Candidate</th><th>Description</th><th>Safety Status</th><th>Rejection Reason</th></tr>
  {unsafe_rows}
</table>

<h2>Evidence Hashes</h2>
<table>
  <tr><th>Candidate</th><th>RTL Hash (SHA-256)</th><th>Evidence Hash (SHA-256)</th><th>Replay Command</th></tr>
  {evidence_rows}
</table>

<h2>Limitations</h2>
<div class="disclaimer">
  <strong>Important:</strong> ChipSynthBench uses RTL-level proxy metrics.
  It does not guarantee real silicon performance, real power consumption,
  timing signoff, area after synthesis, fabrication readiness or physical safety.
  These proxy scores are based on RTL text heuristics (assignment count,
  expression nesting depth, signal toggle patterns). Real results require
  EDA synthesis, static timing analysis, and power estimation tools.
</div>
<div style="background:#f3f4f6;border-radius:8px;padding:1rem;margin-top:0.5rem;font-size:0.875rem;color:#374151;">
  <strong>Optional future integrations:</strong><br>
  Yosys synthesis report | Verilator simulation | cocotb simulation | SymbiYosys formal checks | OpenROAD/OpenLane physical reports
</div>

<div class="meta">
  Benchmark hash: {bench_hash}... | Evidence packs: {evidence_count}<br>
  Replay: <code>{replay_cmd}</code>
</div>
</body>
</html>"""