"""
ChipGate MutationBench — Static HTML report.

Generates a self-contained, dependency-free HTML report for MutationBench.
No JavaScript. Shows summary cards, per-category tables, escaped
mutation details, rule-hardening recommendations, and limitation disclaimers.

Does not guarantee silicon correctness, fabrication readiness,
timing signoff, physical safety, real power or real area.
"""

from typing import Any, Dict


def _sc(status: str) -> str:
    s = status.upper()
    if "PASS" in s and "FAIL" not in s:
        return "pass"
    if "FAIL" in s:
        return "fail"
    if "ESCAPED" in s or "DRIFT" in s:
        return "skip"
    return "neutral"


def generate_mutation_html(data: Dict[str, Any]) -> str:
    """Generate a static HTML report for MutationBench results.

    Args:
        data: Dict from MutationBenchResult.to_dict().

    Returns:
        Complete HTML string.
    """
    overall = data.get("overall_status", "N/A")
    ts = data.get("timestamp_utc", "")
    m = data.get("metrics", {})
    classification = data.get("classification", {})
    per_cat = data.get("per_category", {})
    escaped_list = data.get("escaped_mutations", [])
    review_items = data.get("review_items", [])

    total = m.get("mutations_generated", 0)
    detected = m.get("mutations_detected", 0)
    escaped = m.get("mutations_escaped", 0)

    # Summary cards
    cards = (
        f'<div class="card"><div class="label">Overall</div>'
        f'<div class="value {_sc(overall)}">{overall}</div></div>\n'
        f'<div class="card"><div class="label">Seed Designs</div>'
        f'<div class="value">{m.get("seed_designs_tested", 0)}</div></div>\n'
        f'<div class="card"><div class="label">Mutations</div>'
        f'<div class="value">{total}</div></div>\n'
        f'<div class="card"><div class="label">Detected</div>'
        f'<div class="value pass">{detected}</div></div>\n'
        f'<div class="card"><div class="label">Escaped</div>'
        f'<div class="value {"fail" if escaped > 0 else "pass"}">{escaped}</div></div>\n'
        f'<div class="card"><div class="label">Detection Rate</div>'
        f'<div class="value">{m.get("mutation_detection_rate", 0):.1%}</div></div>\n'
        f'<div class="card"><div class="label">Bypass Rate</div>'
        f'<div class="value">{m.get("unsafe_bypass_detection_rate", 0):.1%}</div></div>\n'
        f'<div class="card"><div class="label">Replay Match</div>'
        f'<div class="value pass">{m.get("replay_match_rate", 0):.1%}</div></div>\n'
    )

    # Critical safety rates
    critical_rows = ""
    for key in [
        "kill_switch_mutation_detection_rate",
        "timeout_mutation_detection_rate",
        "reset_mutation_detection_rate",
        "fsm_escape_detection_rate",
        "shadow_signal_detection_rate",
        "private_leak_detection_rate",
    ]:
        label = key.replace("_mutation_detection_rate", "").replace("_", " ").title()
        rate = m.get(key, 0)
        cls = "pass" if rate >= 1.0 else ("fail" if rate < 0.95 else "skip")
        critical_rows += (
            f'<tr><td>{label}</td>'
            f'<td class="{cls}">{rate:.0%}</td></tr>\n'
        )

    # Per-category table
    cat_rows = ""
    for cat, info in sorted(per_cat.items()):
        is_critical = info.get("critical", False)
        crit_tag = " (critical)" if is_critical else ""
        det = info.get("detected", 0)
        tot = max(info.get("total", 1), 1)
        rate = det / tot
        cls = "pass" if rate >= 0.95 else ("fail" if rate < 0.5 else "skip")
        cat_rows += (
            f'<tr><td><strong>{cat}</strong>{crit_tag}</td>'
            f'<td>{tot}</td>'
            f'<td class="{cls}">{det}</td>'
            f'<td>{rate:.0%}</td></tr>\n'
        )

    # Escaped mutations
    escaped_rows = ""
    for em in escaped_list:
        mid = em.get("mutation_id", "?")
        cat = em.get("category", "?")
        statuses_str = ", ".join(em.get("blocking_statuses", []))
        cls = "fail"
        escaped_rows += (
            f'<tr><td class="mono">{mid}</td>'
            f'<td>{cat}</td>'
            f'<td>{statuses_str or "none"}</td>'
            f'<td class="{cls}">ESCAPED</td></tr>\n'
        )

    # Review / rule-hardening recommendations
    review_html = ""
    for item in review_items:
        review_html += f'<li class="fail">{item}</li>\n'

    # Artifact hashes section
    artifact_hashes = data.get("artifact_hashes", [])
    artifact_rows = ""
    for ah in artifact_hashes[:20]:  # Show first 20
        label = ah.get("label", "?")
        sha = ah.get("sha256", "?")
        artifact_rows += (
            f'<tr><td class="mono">{label}</td>'
            f'<td class="mono">{sha}</td></tr>\n'
        )
    if len(artifact_hashes) > 20:
        artifact_rows += (
            f'<tr><td colspan="2">... and {len(artifact_hashes) - 20} more</td></tr>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MutationBench Report</title>
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
.mono {{ font-family: monospace; font-size: 0.75rem; }}
.disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1.5rem 0; font-size: 0.85rem; color: #92400e; }}
.disclaimer strong {{ color: #92400e; }}
ul {{ padding-left: 1.5rem; }}
li {{ margin: 0.2rem 0; }}
.critical {{ font-weight: 700; }}
</style>
</head>
<body>

<h1>MutationBench Report</h1>
<p class="meta">{ts} | ChipGate v{data.get("benchmark_version", "")}</p>

<div class="disclaimer">
<strong>Public Disclaimer:</strong> {data.get("public_wording", "This report is generated by MutationBench for informational purposes only. It does not constitute a security guarantee.")}
</div>

<div class="cards">{cards}</div>

<h2>Critical Safety Mutation Detection Rates</h2>
<table>
<tr><th>Mutation Category</th><th>Rate</th></tr>
{critical_rows}
</table>

<h2>Per-Category Results</h2>
<table>
<tr><th>Category</th><th>Total</th><th>Detected</th><th>Rate</th></tr>
{cat_rows}
</table>

<h2>Escaped Mutations</h2>
{"<table><tr><th>Mutation ID</th><th>Category</th><th>Detected Statuses</th><th>Status</th></tr>" + escaped_rows + "</table>" if escaped_rows else '<p class="skip">No escaped mutations.</p>'}

{"<h2>Rule-Hardening Recommendations</h2><ul>" + review_html + "</ul>" if review_items else ""}

{"<h2>Artifact Hashes</h2><table><tr><th>Label</th><th>SHA-256</th></tr>" + artifact_rows + "</table>" if artifact_rows else ""}

<div class="disclaimer">
<strong>Limitation:</strong> {data.get("limitation", "MutationBench generates known-unsafe RTL variants and checks whether ChipGate detects them. Passing does not prove the design is secure, fabrication-ready, timing-closed or fully verified.")}
</div>

</body>
</html>"""
    return html