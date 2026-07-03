"""
DTL-ChipBench HTML report generator.

Produces a single, self-contained, dependency-free HTML file
with benchmark results, score cards, tables, and examples.

Supports both single-mode reports and multi-mode comparison reports.
"""

import html
import json
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .bench import BenchResult, ComparisonResult


def generate_html_report(result: "BenchResult") -> str:
    """Generate a complete HTML report from a single BenchResult."""
    d = result.to_full_dict()

    # Failed cases
    failed = [cr for cr in result.case_results if not cr.gate_correct]

    # Pre-compute conditional CSS classes
    ua_cls = "red" if result.unsafe_accepted > 0 else "green"
    sr_cls = "red" if result.safe_rejected > 0 else "green"
    fa_cls = "red" if result.false_accept_rate > 0 else "green"
    fr_cls = "red" if result.false_reject_rate > 5 else "green"
    pct_reduction = (
        f"{((result.estimated_baseline_cost - result.estimated_dtl_cost) / result.estimated_baseline_cost * 100):.1f}"
        if result.estimated_baseline_cost > 0 else "0.0"
    )

    cpv_display = (
        f"{result.cost_per_verified_accepted:.0f}"
        if result.cost_per_verified_accepted != float("inf")
        else "N/A"
    )

    return _HTML_TEMPLATE.format(
        timestamp=html.escape(result.timestamp_utc),
        version=html.escape(result.benchmark_version),
        total_cases=result.total_cases,
        unsafe_blocked=result.unsafe_blocked,
        unsafe_accepted=result.unsafe_accepted,
        safe_accepted=result.safe_accepted,
        safe_rejected=result.safe_rejected,
        regressions_detected=result.regressions_detected,
        regressions_accepted=result.regressions_accepted,
        false_accept=f"{result.false_accept_rate:.1f}",
        false_reject=f"{result.false_reject_rate:.1f}",
        no_regression=f"{result.no_regression_pass_rate:.1f}",
        replay=f"{result.replay_match_rate:.1f}",
        heavy_baseline=result.heavy_checks_baseline,
        heavy_dtl=result.heavy_checks_dtl,
        heavy_avoided=result.heavy_checks_avoided,
        baseline_cost=result.estimated_baseline_cost,
        dtl_cost=result.estimated_dtl_cost,
        speedup=f"{result.estimated_speedup_ratio:.2f}",
        cost_per_accepted=cpv_display,
        cost_saved=result.estimated_baseline_cost - result.estimated_dtl_cost,
        pct_reduction=pct_reduction,
        bench_hash=html.escape(result.benchmark_hash[:16]),
        evidence_count=result.evidence_packs_created,
        failed_rows=_build_failed_rows(failed),
        category_summary=_build_category_summary(result),
        cost_table=_build_cost_table(),
        failed_count=len(failed),
        case_detail_rows=_build_case_detail_rows(result),
        unsafe_blocked_count=result.unsafe_blocked,
        unsafe_examples=_build_unsafe_examples(result),
        ua_cls=ua_cls,
        sr_cls=sr_cls,
        fa_cls=fa_cls,
        fr_cls=fr_cls,
        disclaimer=html.escape(result.disclaimer),
        public_wording=html.escape(result.public_wording),
        limitation=html.escape(result.limitation),
        benchmark_mode_label=html.escape(result.benchmark_mode_label),
        benchmark_mode=html.escape(result.benchmark_mode),
        adapter_name=html.escape(result.adapter_name),
        proposal_source=html.escape(result.proposal_source),
        categories_run=", ".join(html.escape(c) for c in result.categories),
    )


def generate_comparison_html_report(comparison: "ComparisonResult") -> str:
    """Generate an HTML report comparing multiple benchmark modes."""
    modes = comparison.modes

    # Build mode rows
    mode_rows = ""
    for mode_name, result in modes.items():
        cpv = (
            f"{result.cost_per_verified_accepted:.0f}"
            if result.cost_per_verified_accepted != float("inf")
            else "N/A"
        )
        cpv_cls = ""
        # Compare cost per accepted — lower is better
        cpv_vals = []
        for r in modes.values():
            if r.cost_per_verified_accepted != float("inf"):
                cpv_vals.append(r.cost_per_verified_accepted)
        if cpv_vals and result.cost_per_verified_accepted == min(cpv_vals) and len(cpv_vals) > 1:
            cpv_cls = ' class="green"'

        pct_red = (
            f"{((result.estimated_baseline_cost - result.estimated_dtl_cost) / result.estimated_baseline_cost * 100):.1f}"
            if result.estimated_baseline_cost > 0 else "0.0"
        )

        mode_rows += f"""\
<tr>
  <td><strong>{html.escape(result.benchmark_mode_label)}</strong></td>
  <td>{html.escape(result.proposal_source)}</td>
  <td class="num">{result.total_cases}</td>
  <td class="num">{result.unsafe_blocked}</td>
  <td class="num {'red' if result.unsafe_accepted > 0 else ''}">{result.unsafe_accepted}</td>
  <td class="num">{result.safe_accepted}</td>
  <td class="num {'red' if result.safe_rejected > 0 else ''}">{result.safe_rejected}</td>
  <td class="num">{result.regressions_detected}</td>
  <td class="num {'red' if result.regressions_accepted > 0 else ''}">{result.regressions_accepted}</td>
  <td class="num">{result.false_accept_rate:.1f}%</td>
  <td class="num">{result.heavy_checks_avoided}</td>
  <td class="num">{pct_red}%</td>
  <td class="num{cpv_cls}">{cpv}</td>
  <td class="num">{result.replay_match_rate:.0f}%</td>
  <td class="num">{result.evidence_packs_created}</td>
</tr>"""

    # Build cost per accepted comparison
    cpv_rows = ""
    for mode_name, result in modes.items():
        cpv = result.cost_per_verified_accepted
        if cpv != float("inf"):
            cpv_rows += f'<tr><td>{html.escape(result.benchmark_mode_label)}</td><td class="num">{cpv:.0f}</td></tr>\n'

    return _COMPARISON_HTML_TEMPLATE.format(
        timestamp=html.escape(comparison.timestamp_utc),
        mode_rows=mode_rows,
        cpv_rows=cpv_rows,
        cost_table=_build_cost_table(),
        public_wording=html.escape(comparison.public_wording),
        limitation=html.escape(comparison.limitation),
        disclaimer="These are estimated verification-cost units under the synthetic benchmark cost model. They do not represent real-world EDA cost, GPU time, or monetary cost.",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_failed_rows(failed_cases) -> str:
    if not failed_cases:
        return '<tr><td colspan="5" class="center">No incorrect gate decisions</td></tr>'
    rows = []
    for cr in failed_cases:
        rows.append(
            f'<tr class="fail-row">'
            f'<td>{html.escape(cr.case_id)}</td>'
            f'<td>{html.escape(cr.category)}</td>'
            f'<td>{html.escape(cr.gate_result)}</td>'
            f'<td>{html.escape(cr.expected_gate_result)}</td>'
            f'<td>{html.escape(cr.reason[:80])}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _build_category_summary(result: "BenchResult") -> str:
    """Build category breakdown rows."""
    from collections import defaultdict
    cats = defaultdict(lambda: {"total": 0, "blocked": 0, "passed": 0, "correct": 0})
    for cr in result.case_results:
        cats[cr.category]["total"] += 1
        if cr.gate_result == "block":
            cats[cr.category]["blocked"] += 1
        else:
            cats[cr.category]["passed"] += 1
        if cr.gate_correct:
            cats[cr.category]["correct"] += 1

    rows = []
    for cat in sorted(cats.keys()):
        c = cats[cat]
        accuracy = (c["correct"] / c["total"] * 100) if c["total"] > 0 else 0
        rows.append(
            f'<tr>'
            f'<td>{html.escape(cat)}</td>'
            f'<td>{c["total"]}</td>'
            f'<td>{c["blocked"]}</td>'
            f'<td>{c["passed"]}</td>'
            f'<td>{accuracy:.0f}%</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _build_cost_table() -> str:
    return (
        f'<tr><td>DTL Scan / Adapter Pass (cheap gate)</td><td class="num">1</td></tr>'
        f'<tr><td>Lint</td><td class="num">5</td></tr>'
        f'<tr><td>Simulation</td><td class="num">25</td></tr>'
        f'<tr><td>Formal Verification</td><td class="num">100</td></tr>'
        f'<tr><td>Synthesis</td><td class="num">250</td></tr>'
    )


def _build_case_detail_rows(result: "BenchResult") -> str:
    rows = []
    for cr in result.case_results:
        cls = "" if cr.gate_correct else ' class="fail-row"'
        reg_cell = html.escape(cr.regression_status) if cr.regression_status else "&mdash;"
        rows.append(
            f'<tr{cls}>'
            f'<td>{html.escape(cr.case_id)}</td>'
            f'<td>{html.escape(cr.category)}</td>'
            f'<td>{html.escape(cr.risk_level)}</td>'
            f'<td>{html.escape(cr.gate_result)}</td>'
            f'<td>{html.escape(cr.expected_gate_result)}</td>'
            f'<td>{"&#10003;" if cr.gate_correct else "&#10007;"}</td>'
            f'<td>{html.escape(cr.heavy_check_decision)}</td>'
            f'<td>{reg_cell}</td>'
            f'<td class="num">{cr.duration_ms:.1f}ms</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _build_unsafe_examples(result: "BenchResult") -> str:
    """Show a few example unsafe cases that were blocked."""
    blocked = [cr for cr in result.case_results
               if cr.gate_result == "block" and cr.expected_gate_result == "block"]
    examples = blocked[:3]
    if not examples:
        return "<p>No blocked cases to show.</p>"
    parts = []
    for cr in examples:
        parts.append(
            f'<div class="example-block">'
            f'<strong>{html.escape(cr.case_id)}</strong> &mdash; {html.escape(cr.category)}<br>'
            f'<span class="reason">{html.escape(cr.reason)}</span><br>'
            f'<span class="detail">Findings: {cr.findings_count} | Status: {", ".join(cr.statuses[:3])}</span>'
            f'</div>'
        )
    return "\n".join(parts)


# ── Single-Mode HTML Template ────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DTL-ChipBench Report</title>
<style>
  :root {{ --green: #16a34a; --red: #dc2626; --blue: #2563eb; --gray: #6b7280; --bg: #f9fafb; --card-bg: #ffffff; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: #1f2937; line-height: 1.6; padding: 2rem; }}
  h1 {{ font-size: 1.75rem; margin-bottom: 0.25rem; }}
  h2 {{ font-size: 1.25rem; margin: 2rem 0 1rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
  .subtitle {{ color: var(--gray); margin-bottom: 2rem; }}
  .disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1rem 0 2rem; font-size: 0.875rem; color: #92400e; }}
  .public-wording {{ background: #f3f4f6; border-radius: 8px; padding: 1rem; margin: 1rem 0 1rem; font-size: 0.875rem; color: #374151; font-style: italic; }}
  .limitation-box {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 0 0 2rem; font-size: 0.875rem; color: #92400e; }}
  .banner {{ background: #1e40af; color: white; border-radius: 8px; padding: 1rem; margin: 1rem 0 2rem; font-size: 0.875rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0 2rem; }}
  .card {{ background: var(--card-bg); border-radius: 12px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .card .label {{ font-size: 0.75rem; color: var(--gray); text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ font-size: 2rem; font-weight: 700; margin-top: 0.25rem; }}
  .card .value.green {{ color: var(--green); }}
  .card .value.red {{ color: var(--red); }}
  .card .value.blue {{ color: var(--blue); }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.875rem; }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
  th {{ background: #f3f4f6; font-weight: 600; position: sticky; top: 0; }}
  .fail-row {{ background: #fef2f2; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .center {{ text-align: center; color: var(--gray); }}
  .example-block {{ background: var(--card-bg); border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; }}
  .example-block .reason {{ color: var(--gray); font-size: 0.8rem; }}
  .example-block .detail {{ font-size: 0.75rem; color: var(--gray); }}
  .meta {{ font-size: 0.75rem; color: var(--gray); margin-top: 2rem; }}
  @media (max-width: 768px) {{ body {{ padding: 1rem; }} .cards {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
</head>
<body>
<h1>DTL-ChipBench Report &mdash; {benchmark_mode_label}</h1>
<p class="subtitle">Version {version} &mdash; Mode: {benchmark_mode} | Generated {timestamp}</p>

<div class="banner">
  <strong>Adapter-aware benchmark:</strong> This report reflects mode <strong>{benchmark_mode}</strong>
  using proposal source <strong>{proposal_source}</strong> (adapter: {adapter_name}).
  Model-connected testing requires an external adapter. This public repo does not include private DTL internals.
</div>

<div class="disclaimer">
  <strong>Limitation:</strong> {disclaimer}
</div>

<div class="public-wording">
  {public_wording}
</div>

<div class="limitation-box">
  <strong>Model-Free Benchmark:</strong> {limitation}
</div>

<h2>Summary</h2>
<div class="cards">
  <div class="card"><div class="label">Total Cases</div><div class="value blue">{total_cases}</div></div>
  <div class="card"><div class="label">Unsafe Blocked</div><div class="value green">{unsafe_blocked}</div></div>
  <div class="card"><div class="label">Unsafe Accepted</div><div class="value {ua_cls}">{unsafe_accepted}</div></div>
  <div class="card"><div class="label">Safe Accepted</div><div class="value green">{safe_accepted}</div></div>
  <div class="card"><div class="label">Safe Rejected</div><div class="value {sr_cls}">{safe_rejected}</div></div>
  <div class="card"><div class="label">Regressions Detected</div><div class="value blue">{regressions_detected}</div></div>
  <div class="card"><div class="label">Regressions Accepted</div><div class="value {ua_cls}">{regressions_accepted}</div></div>
  <div class="card"><div class="label">False Accept Rate</div><div class="value {fa_cls}">{false_accept}%</div></div>
  <div class="card"><div class="label">False Reject Rate</div><div class="value {fr_cls}">{false_reject}%</div></div>
  <div class="card"><div class="label">No-Regression Pass</div><div class="value green">{no_regression}%</div></div>
  <div class="card"><div class="label">Replay Match</div><div class="value green">{replay}%</div></div>
  <div class="card"><div class="label">Est. Verification-Cost Reduction</div><div class="value blue">{speedup}x</div></div>
  <div class="card"><div class="label">Synthetic Proposals Blocked</div><div class="value green">{heavy_avoided}/{total_cases}</div></div>
  <div class="card"><div class="label">Cost Reduction</div><div class="value green">{pct_reduction}%</div></div>
  <div class="card"><div class="label">Cost per Accepted Change</div><div class="value blue">{cost_per_accepted}</div></div>
</div>

<h2>Cost Model (estimated verification-cost units)</h2>
<table>
  <tr><th>Verification Step</th><th>Cost Units</th></tr>
  {cost_table}
</table>
<p style="font-size:0.8rem;color:var(--gray);margin-top:0.5rem;">
  Baseline cost: {baseline_cost} units (all {heavy_baseline} cases x full pipeline)<br>
  Gated cost: {dtl_cost} units ({heavy_dtl} cases x full pipeline + {total_cases} x gate scan)<br>
  Est. verification-cost reduction: {speedup}x under the synthetic benchmark cost model<br>
  Estimated cost per verified accepted change: {cost_per_accepted} units
</p>

<h2>Workflow Comparison</h2>
<table>
  <tr><th>Metric</th><th>Ungated Baseline</th><th>Current Mode</th><th>Improvement</th></tr>
  <tr><td>Heavy verification calls</td><td class="num">{heavy_baseline}</td><td class="num">{heavy_dtl}</td><td class="num">{heavy_avoided} avoided ({pct_reduction}% reduction)</td></tr>
  <tr><td>Estimated cost units</td><td class="num">{baseline_cost}</td><td class="num">{dtl_cost}</td><td class="num">{cost_saved} saved</td></tr>
  <tr><td>Unsafe proposals sent unchecked</td><td class="num">{total_cases} (all sent unchecked)</td><td class="num">{unsafe_accepted}</td><td class="num">{unsafe_blocked_count} blocked before heavier verification</td></tr>
</table>

<h2>Category Breakdown</h2>
<table>
  <tr><th>Category</th><th>Cases</th><th>Blocked</th><th>Passed</th><th>Accuracy</th></tr>
  {category_summary}
</table>

<h2>Gate Decision Errors ({failed_count})</h2>
<p style="font-size:0.8rem;color:var(--gray);margin-bottom:0.5rem;">Errors indicate deterministic gate logic issues, not model quality. This benchmark tests the gate, not a model.</p>
<table>
  <tr><th>Case ID</th><th>Category</th><th>Actual</th><th>Expected</th><th>Reason</th></tr>
  {failed_rows}
</table>

<h2>Example Blocked Unsafe Cases</h2>
{unsafe_examples}

<h2>All Case Results</h2>
<table style="font-size:0.75rem;">
  <tr><th>Case</th><th>Category</th><th>Risk</th><th>Gate</th><th>Expected</th><th>OK</th><th>Heavy</th><th>Regression</th><th>Time</th></tr>
  {case_detail_rows}
</table>

<h2>Benchmark Scope</h2>
<div class="limitation-box">
  <strong>What this benchmark tests (current phase):</strong><br>
  Synthetic RTL proposals | Mutation-generated unsafe/safe variants | ChipGate deterministic rules | No-regression checks | Evidence packs | Replay matching | Transparent cost-model estimate | Multi-mode comparison
</div>
<div style="background:#f3f4f6;border-radius:8px;padding:1rem;margin-top:0.5rem;font-size:0.875rem;color:#374151;">
  <strong>Future phase (not yet implemented):</strong><br>
  Connect a real model as the proposal generator | Freeze a public test set and private holdout | Compare model-only vs model+DTL | Publish results only after fresh holdout testing
</div>

<h2>Categories</h2>
<p>{categories_run}</p>

<div class="meta">
  Benchmark hash: {bench_hash}... | Evidence packs: {evidence_count}<br>
  Replay: python -m chipgate bench --mode {benchmark_mode} --demo
</div>
</body>
</html>"""


# ── Comparison HTML Template ─────────────────────────────────────────────────

_COMPARISON_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DTL-ChipBench Mode Comparison</title>
<style>
  :root {{ --green: #16a34a; --red: #dc2626; --blue: #2563eb; --gray: #6b7280; --bg: #f9fafb; --card-bg: #ffffff; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: #1f2937; line-height: 1.6; padding: 2rem; }}
  h1 {{ font-size: 1.75rem; margin-bottom: 0.25rem; }}
  h2 {{ font-size: 1.25rem; margin: 2rem 0 1rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
  .subtitle {{ color: var(--gray); margin-bottom: 2rem; }}
  .banner {{ background: #1e40af; color: white; border-radius: 8px; padding: 1rem; margin: 1rem 0 2rem; font-size: 0.875rem; }}
  .disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1rem 0 2rem; font-size: 0.875rem; color: #92400e; }}
  .public-wording {{ background: #f3f4f6; border-radius: 8px; padding: 1rem; margin: 1rem 0 1rem; font-size: 0.875rem; color: #374151; font-style: italic; }}
  .limitation-box {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 0 0 2rem; font-size: 0.875rem; color: #92400e; }}
  .key-metric {{ background: #eff6ff; border: 2px solid var(--blue); border-radius: 12px; padding: 1.5rem; margin: 1rem 0 2rem; text-align: center; }}
  .key-metric .title {{ font-size: 0.875rem; color: var(--gray); text-transform: uppercase; }}
  .key-metric .values {{ display: flex; justify-content: center; gap: 2rem; margin-top: 0.5rem; flex-wrap: wrap; }}
  .key-metric .mv {{ text-align: center; }}
  .key-metric .mv .label {{ font-size: 0.75rem; color: var(--gray); }}
  .key-metric .mv .val {{ font-size: 1.5rem; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.875rem; }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
  th {{ background: #f3f4f6; font-weight: 600; position: sticky; top: 0; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .red {{ color: var(--red); font-weight: 600; }}
  .green {{ color: var(--green); font-weight: 600; }}
  .meta {{ font-size: 0.75rem; color: var(--gray); margin-top: 2rem; }}
  @media (max-width: 768px) {{ body {{ padding: 1rem; }} table {{ font-size: 0.75rem; }} }}
</style>
</head>
<body>
<h1>DTL-ChipBench &mdash; Mode Comparison</h1>
<p class="subtitle">Generated {timestamp}</p>

<div class="banner">
  <strong>Model-connected testing requires an external adapter.</strong>
  This public repo does not include private DTL internals.
  The benchmark harness, adapters, and scoring are provided.
  Private DTL internals are not included.
</div>

<div class="disclaimer">
  <strong>Limitation:</strong> {disclaimer}
</div>

<div class="public-wording">
  {public_wording}
</div>

<div class="limitation-box">
  <strong>Model-Free Benchmark:</strong> {limitation}
</div>

<h2>Key Metric: Estimated Cost per Verified Accepted Change</h2>
<div class="key-metric">
  <div class="title">Under the synthetic benchmark cost model</div>
  <div class="values">
    {cpv_rows}
  </div>
</div>

<h2>Mode Comparison Table</h2>
<div style="overflow-x:auto;">
<table>
  <tr>
    <th>Mode</th>
    <th>Source</th>
    <th>Total</th>
    <th>Blocked</th>
    <th>Unsafe Acc.</th>
    <th>Safe Acc.</th>
    <th>Safe Rej.</th>
    <th>Regr. Det.</th>
    <th>Regr. Acc.</th>
    <th>FA Rate</th>
    <th>Heavy Avoided</th>
    <th>Cost Red.</th>
    <th>Cost/Accepted</th>
    <th>Replay</th>
    <th>Evidence</th>
  </tr>
  {mode_rows}
</table>
</div>

<h2>Cost Model (estimated verification-cost units)</h2>
<table>
  <tr><th>Verification Step</th><th>Cost Units</th></tr>
  {cost_table}
</table>

<h2>Benchmark Scope</h2>
<div class="limitation-box">
  <strong>What this benchmark tests (current phase):</strong><br>
  Multi-mode comparison | Synthetic RTL proposals | Mutation-generated unsafe/safe variants | ChipGate deterministic rules | No-regression checks | Evidence packs | Transparent cost-model estimate
</div>
<div style="background:#f3f4f6;border-radius:8px;padding:1rem;margin-top:0.5rem;font-size:0.875rem;color:#374151;">
  <strong>Future phase (not yet implemented):</strong><br>
  Connect a real model as the proposal generator | Freeze a public test set and private holdout | Compare model-only vs model+DTL | Publish results only after fresh holdout testing
</div>

<div class="meta">
  DTL-ChipBench mode comparison | {timestamp}
</div>
</body>
</html>"""