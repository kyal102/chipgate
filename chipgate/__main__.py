"""
ChipGate CLI entry point.

Usage:
    python -m chipgate --demo
    python -m chipgate scan <file> [--json] [--evidence] [--lint] [--formal] [--safety]
    python -m chipgate lint <file>
    python -m chipgate --list-rules
    python -m chipgate --version
    python -m chipgate bench [--mode MODE] [--adapter FILE] [--compare-modes] [--html FILE]
    python -m chipgate longevity [--demo] [--json] [--html FILE]
    python -m chipgate synth [--demo] [--json] [--html FILE] [--rank] [path]
    python -m chipgate silicon [--demo] [--json] [--html FILE] [--toolchain-status] [path]
    python -m chipgate fpga [--demo] [--json] [--html FILE] [--toolchain-status] [--board-profile NAME] [path]
    python -m chipgate tinytapeout [--demo] [--json] [--html FILE] [path]
    python -m chipgate physical [--demo] [--json] [--html FILE] [--toolchain-status] [--parse-reports DIR] [--allow-unsafe] [path]
    python -m chipgate formal [--demo] [--json] [--html FILE] [--list-properties] [--toolchain-status] [path]
    python -m chipgate ci [--quick] [--full] [--json] [--html FILE] [--toolchain-status]
"""

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import List, Optional

from . import __version__, statuses as st
from .scanner import scan_file, scan_directory
from .lint import run_lint, verilator_available
from .simulation import run_simulation
from .formal import check_formal_readiness, run_formal_verification
from .safety import analyze_safety_patterns
from .evidence import save_evidence_pack, validate_evidence_pack
from .replay import format_replay_script_from_result, generate_replay_commands
from .dtl_gate import get_dtl_gate_reference, get_dtl_fsm_reference, get_gate_structure_docs
from .rules import RULES, Severity
from .cost_model import VALID_MODES


# ── Colours for terminal output ──────────────────────────────────────────────

class Colours:
    """ANSI colour codes for terminal output."""
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def _c(code: str, text: str) -> str:
    """Apply colour code to text if stdout is a terminal."""
    if sys.stdout.isatty():
        return f"{code}{text}{Colours.RESET}"
    return text


def _severity_colour(severity: str) -> str:
    """Return colour code for a severity level."""
    mapping = {
        "critical": Colours.RED,
        "high": Colours.RED,
        "medium": Colours.YELLOW,
        "low": Colours.BLUE,
        "info": Colours.DIM,
    }
    return mapping.get(severity, Colours.RESET)


# ── Output Formatters ────────────────────────────────────────────────────────

def format_human(result) -> str:
    """Format a ScanResult as human-readable terminal output."""
    lines = []
    lines.append(_c(Colours.BOLD, f"ChipGate Scan: {result.file}"))
    lines.append(_c(Colours.DIM, f"Module: {result.module_name or 'unknown'}"))
    lines.append("")

    # Statuses
    for status in result.statuses:
        if status in st.FAIL_STATUSES:
            lines.append(f"  {_c(Colours.RED, '[FAIL]')} {status}")
        elif status in st.PASS_STATUSES:
            lines.append(f"  {_c(Colours.GREEN, '[PASS]')} {status}")
        else:
            lines.append(f"  {_c(Colours.YELLOW, '[INFO]')} {status}")

    lines.append("")

    # Findings
    if result.findings:
        lines.append(_c(Colours.BOLD, "Findings:"))
        for f in result.findings:
            colour = _severity_colour(f.severity)
            loc = f" (line {f.line_number})" if f.line_number else ""
            lines.append(f"  {_c(colour, f'[{f.severity.upper()}]')} {f.rule_id}: {f.description}{loc}")
            if f.detail:
                lines.append(f"         {f.detail}")
    else:
        lines.append(_c(Colours.GREEN, "No findings."))

    # Risky signals
    if result.risky_signals:
        lines.append("")
        lines.append(_c(Colours.BOLD, "Risky signals:") + f" {', '.join(result.risky_signals)}")

    # Required gates
    if result.required_gates:
        lines.append("")
        lines.append(_c(Colours.BOLD, "Required gates:") + f" {', '.join(result.required_gates)}")

    # Replay command
    if result.replay_command:
        lines.append("")
        lines.append(_c(Colours.DIM, f"Replay: {result.replay_command}"))

    # Certificate hash
    if result.certificate_hash:
        lines.append(_c(Colours.DIM, f"Hash: {result.certificate_hash[:16]}..."))

    lines.append("")
    lines.append(_c(Colours.DIM, result.public_wording))

    return "\n".join(lines)


def format_json_output(result) -> str:
    """Format a ScanResult as JSON."""
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_scan(args: argparse.Namespace) -> int:
    """Run scan command."""
    file_path = args.file

    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 1

    # Run core scan
    result = scan_file(file_path)

    # Optional: run lint
    lint_data = None
    if args.lint:
        from .lint import LintResult
        lint_result = run_lint(file_path)
        lint_data = {
            "tool": lint_result.tool,
            "available": lint_result.available,
            "passed": lint_result.passed,
            "warnings": lint_result.warnings,
            "errors": lint_result.errors,
            "command": lint_result.command,
        }
        if not lint_result.available:
            result.statuses.append(st.RTL_LINT_FAIL)
        elif lint_result.passed:
            result.statuses.append(st.RTL_LINT_PASS)
        else:
            result.statuses.append(st.RTL_LINT_FAIL)

    # Optional: formal readiness
    formal_data = None
    if args.formal:
        formal = check_formal_readiness(file_path)
        formal_data = {
            "ready": formal.ready,
            "assertion_count": formal.assertion_count,
            "issues": formal.issues,
            "sby_config": formal.sby_config,
            "tool_available": formal.tool_available,
        }

    # Optional: safety analysis
    safety_data = None
    if args.safety:
        safety = analyze_safety_patterns(file_path)
        safety_data = {
            "safety_score": safety.safety_score,
            "gate_chain_complete": safety.gate_chain_complete,
            "critical_gaps": safety.critical_gaps,
            "patterns": [
                {
                    "pattern_name": p.pattern_name,
                    "present": p.present,
                    "description": p.description,
                    "signals_involved": p.signals_involved,
                }
                for p in safety.patterns
            ],
        }

    # Optional: evidence pack
    if args.evidence:
        evidence_path = save_evidence_pack(
            result,
            include_lint=lint_data,
            include_formal=formal_data,
            include_safety=safety_data,
        )
        result.statuses.append(st.EVIDENCE_PACK_CREATED)

    # Output
    if args.json:
        output = result.to_dict()
        if lint_data:
            output["lint"] = lint_data
        if formal_data:
            output["formal"] = formal_data
        if safety_data:
            output["safety_analysis"] = safety_data
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(format_human(result))
        if args.evidence:
            print(_c(Colours.GREEN, f"Evidence pack saved: {evidence_path}"))
        if lint_data and not lint_data["available"]:
            print(_c(Colours.DIM, "Tip: Install Verilator for external lint checks."))

    return 0 if st.RTL_SCAN_PASS in result.statuses else 2


def cmd_lint(args: argparse.Namespace) -> int:
    """Run lint command."""
    file_path = args.file

    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 1

    lint_result = run_lint(file_path)

    if not lint_result.available:
        print(_c(Colours.YELLOW, "External lint tool not available."))
        print(_c(Colours.DIM, "Running internal scan instead...\n"))
        result = scan_file(file_path)
        print(format_human(result))
        return 0

    print(_c(Colours.BOLD, f"Lint ({lint_result.tool}): {file_path}"))
    print(f"  Command: {lint_result.command}")
    print(f"  Available: {lint_result.available}")
    print(f"  Passed: {_c(Colours.GREEN, 'Yes') if lint_result.passed else _c(Colours.RED, 'No')}")

    if lint_result.warnings:
        print(f"\n  Warnings ({len(lint_result.warnings)}):")
        for w in lint_result.warnings:
            print(f"    {w}")

    if lint_result.errors:
        print(f"\n  Errors ({len(lint_result.errors)}):")
        for e in lint_result.errors:
            print(f"    {e}")

    return 0 if lint_result.passed else 2


def cmd_demo(_args: argparse.Namespace) -> int:
    """Run the demo command."""
    print(_c(Colours.BOLD, "ChipGate Demo"))
    print(_c(Colours.DIM, "Version " + __version__))
    print()

    # Show the unsafe example
    print(_c(Colours.RED, "=" * 60))
    print(_c(Colours.RED, "EXAMPLE 1: Unsafe Actuator (should FAIL)"))
    print(_c(Colours.RED, "=" * 60))
    print()
    unsafe_code = textwrap.dedent("""\
        module unsafe_actuator (
            input  clk,
            input  ai_output,
            output reg actuator_enable
        );
            always @(posedge clk) begin
                actuator_enable <= ai_output;
            end
        endmodule""")
    print(_c(Colours.DIM, unsafe_code))
    print()

    # Write temp file and scan
    unsafe_path = Path("/tmp/chipgate_demo_unsafe.v")
    unsafe_path.write_text(unsafe_code)

    result_unsafe = scan_file(str(unsafe_path), generate_replay=False)
    print(format_human(result_unsafe))

    # Show the safe example
    print()
    print(_c(Colours.GREEN, "=" * 60))
    print(_c(Colours.GREEN, "EXAMPLE 2: Safe DTL Gate (should PASS)"))
    print(_c(Colours.GREEN, "=" * 60))
    print()
    safe_code = textwrap.dedent("""\
        module safe_dtl_gate (
            input  clk,
            input  rst_n,
            input  ai_output,
            input  verifier_ok,
            input  policy_ok,
            input  kill_switch,
            output reg actuator_enable
        );
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    actuator_enable <= 1'b0;
                end else begin
                    actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
                end
            end
        endmodule""")
    print(_c(Colours.DIM, safe_code))
    print()

    safe_path = Path("/tmp/chipgate_demo_safe.v")
    safe_path.write_text(safe_code)

    result_safe = scan_file(str(safe_path), generate_replay=False)
    print(format_human(result_safe))

    # Show DTL gate reference
    print()
    print(_c(Colours.BLUE, "=" * 60))
    print(_c(Colours.BLUE, "DTL HARDWARE GATE STRUCTURE"))
    print(_c(Colours.BLUE, "=" * 60))
    print()
    print(textwrap.dedent("""\
        AI/proposed output
                |
        policy_ok?
        verifier_ok?
        sensor_ok?
        timeout_ok?
        kill_switch clear?
                |
        actuator_enable"""))

    print()
    print(_c(Colours.DIM, "ChipGate verifies hardware logic before AI outputs reach the physical world."))
    print(_c(Colours.DIM, result_safe.public_wording))

    return 0


def cmd_list_rules(_args: argparse.Namespace) -> int:
    """List all rules."""
    print(_c(Colours.BOLD, f"ChipGate Rules (v{__version__})"))
    print(f"{'Rule ID':<10} {'Severity':<10} Description")
    print("-" * 80)
    for rule in RULES:
        colour = _severity_colour(rule.severity.value)
        print(f"{rule.rule_id:<10} {_c(colour, rule.severity.value.upper()):<10} {rule.description}")
        if rule.rationale:
            print(f"{'':10} {'':10} {rule.rationale}")
            print()
    return 0


# ── Bench Command ────────────────────────────────────────────────────────────

def _resolve_adapter(adapter_arg: Optional[str]):
    """Resolve adapter from CLI argument."""
    if adapter_arg is None:
        return None

    adapter_path = Path(adapter_arg)

    if adapter_path.suffix == ".jsonl":
        from .adapters.jsonl_adapter import JSONLAdapter
        return JSONLAdapter(str(adapter_path))
    else:
        # Try importing as a Python module
        import importlib.util
        spec = importlib.util.spec_from_file_location("custom_adapter", str(adapter_path))
        if spec is None or spec.loader is None:
            print(f"Error: Cannot load adapter from {adapter_arg}", file=sys.stderr)
            sys.exit(1)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Look for an adapter class
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and hasattr(attr, 'get_proposal'):
                try:
                    return attr()
                except Exception:
                    continue
        print(f"Error: No adapter class found in {adapter_arg}", file=sys.stderr)
        sys.exit(1)


def cmd_bench(args: argparse.Namespace) -> int:
    """Run DTL-ChipBench benchmark."""
    from .bench import run_benchmark, run_benchmark_demo, compare_modes
    from .bench_report import generate_html_report, generate_comparison_html_report
    from .bench_cases import generate_all_cases

    is_demo = getattr(args, "demo", False)
    is_compare = getattr(args, "compare_modes", False)
    mode = getattr(args, "mode", "chipgate_only")
    adapter_arg = getattr(args, "adapter", None)
    html_path = getattr(args, "html", None)
    do_json = getattr(args, "json", False)
    do_evidence = getattr(args, "evidence", False)

    # Resolve adapter
    adapter = _resolve_adapter(adapter_arg)

    # --compare-modes: run all three modes and generate comparison
    if is_compare:
        cases = generate_all_cases() if not is_demo else [
            c for c in generate_all_cases()
            if c.case_id in ["UA-001", "MV-001", "MP-001", "MK-001", "TB-001",
                             "SD-001", "SD-002", "SF-001", "FP-001", "FN-001",
                             "RG-001", "RG-004"]
        ]

        output_dir = str(Path(html_path).parent) if html_path else None
        comparison = compare_modes(
            cases=cases,
            adapter=adapter,
            output_dir=output_dir,
            evidence=do_evidence,
        )

        # HTML report (always generated if --html is set)
        if html_path:
            html_content = generate_comparison_html_report(comparison)
            Path(html_path).write_text(html_content, encoding="utf-8")
            if not do_json:
                print(_c(Colours.GREEN, f"\nComparison HTML report saved: {html_path}"))

        # JSON output (pure JSON — no human-readable prefix/suffix)
        if do_json:
            print(json.dumps(comparison.to_dict(), indent=2, sort_keys=True))
        else:
            # Print comparison summary
            print(_c(Colours.BOLD, "DTL-ChipBench — Mode Comparison"))
            print(_c(Colours.DIM, f"Version {__version__}"))
            print()

            for mode_name, result in comparison.modes.items():
                _print_mode_summary(mode_name, result)

            print()
            print(_c(Colours.DIM, comparison.public_wording))
            print(_c(Colours.DIM, comparison.limitation))
        return 0

    # Single-mode run
    if is_demo:
        if mode != "chipgate_only" and adapter is None:
            print(_c(Colours.DIM, f"Note: --demo with --mode {mode} uses 12 representative cases"))
        result = run_benchmark_demo() if mode == "chipgate_only" and adapter is None \
            else run_benchmark(mode=mode, adapter=adapter)
        # Override demo to use 12 cases if not chipgate_only
        if mode != "chipgate_only":
            demo_ids = {"UA-001", "MV-001", "MP-001", "MK-001", "TB-001",
                        "SD-001", "SD-002", "SF-001", "FP-001", "FN-001",
                        "RG-001", "RG-004"}
            all_cases = generate_all_cases()
            result = run_benchmark(
                cases=[c for c in all_cases if c.case_id in demo_ids],
                mode=mode, adapter=adapter,
            )
    else:
        result = run_benchmark(
            mode=mode,
            adapter=adapter,
            evidence=do_evidence,
        )

    # HTML report (always generated if --html is set)
    if html_path:
        html_content = generate_html_report(result)
        Path(html_path).write_text(html_content, encoding="utf-8")
        if not do_json:
            print(_c(Colours.GREEN, f"\nHTML report saved: {html_path}"))

    # JSON output (pure JSON — no human-readable prefix/suffix)
    if do_json:
        print(json.dumps(result.to_full_dict(), indent=2, sort_keys=True))
    else:
        # Print summary
        _print_mode_summary(mode, result)

        # Public wording and limitation
        print()
        print(_c(Colours.DIM, result.public_wording))
        print(_c(Colours.DIM, result.disclaimer))
        if result.limitation:
            print(_c(Colours.DIM, result.limitation))

    return 0 if result.false_accept_rate == 0 else 2


def _print_mode_summary(mode: str, result) -> None:
    """Print a summary for a single benchmark mode."""
    mode_label = result.benchmark_mode_label
    print(_c(Colours.BOLD, f"Mode: {mode_label}"))
    if result.adapter_name:
        print(_c(Colours.DIM, f"  Adapter: {result.adapter_name} ({result.proposal_source})"))
    print()
    print(f"  Total cases:              {result.total_cases}")
    print(f"  Unsafe blocked:           {_c(Colours.GREEN, str(result.unsafe_blocked))}")
    print(f"  Unsafe accepted:          {_c(Colours.RED if result.unsafe_accepted > 0 else Colours.GREEN, str(result.unsafe_accepted))}")
    print(f"  Safe accepted:            {_c(Colours.GREEN, str(result.safe_accepted))}")
    print(f"  Safe rejected:            {_c(Colours.RED if result.safe_rejected > 0 else Colours.GREEN, str(result.safe_rejected))}")
    print(f"  Regressions detected:     {result.regressions_detected}")
    print(f"  Regressions accepted:     {_c(Colours.RED if result.regressions_accepted > 0 else Colours.GREEN, str(result.regressions_accepted))}")
    print(f"  False accept rate:        {result.false_accept_rate:.1f}%")
    print(f"  False reject rate:        {result.false_reject_rate:.1f}%")
    print(f"  No-regression pass rate:  {result.no_regression_pass_rate:.1f}%")
    print(f"  Replay match rate:        {result.replay_match_rate:.1f}%")
    print()
    print(_c(Colours.BOLD, "  Cost Model (estimated verification-cost units):"))
    print(f"  Heavy checks (baseline):  {result.heavy_checks_baseline}")
    print(f"  Heavy checks (gated):     {result.heavy_checks_dtl}")
    print(f"  Heavy checks avoided:     {_c(Colours.GREEN, str(result.heavy_checks_avoided))}")
    print(f"  Baseline cost:            {result.estimated_baseline_cost} units")
    print(f"  Mode cost:                {result.estimated_dtl_cost} units")
    if result.estimated_speedup_ratio > 0:
        print(f"  Est. verification-cost reduction: {_c(Colours.BLUE, f'{result.estimated_speedup_ratio:.2f}x')} under the synthetic benchmark cost model")
    cpv = result.cost_per_verified_accepted
    if cpv != float("inf"):
        print(f"  Est. cost per verified accepted change: {cpv:.0f} units")
    else:
        print(f"  Est. cost per verified accepted change: N/A (no accepted changes)")
    print()


# ── Longevity Command ──────────────────────────────────────────────────

def cmd_longevity(args: argparse.Namespace) -> int:
    """Run LongevityBench stress/reliability benchmark."""
    from .longevity import run_longevity_benchmark, run_longevity_demo
    from .reliability_metrics import LONGEVITY_PUBLIC_WORDING, LONGEVITY_LIMITATION

    is_demo = getattr(args, "demo", False)
    do_json = getattr(args, "json", False)
    html_path = getattr(args, "html", None)

    if is_demo:
        result = run_longevity_demo()
    else:
        result = run_longevity_benchmark()

    if do_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(_c(Colours.BOLD, "LongevityBench"))
        print(_c(Colours.DIM, f"Version {__version__}"))
        print()
        print(f"  Total cycles:             {result.total_cycles:,}")
        print(f"  Unsafe enable events:     {_c(Colours.GREEN if result.unsafe_enable_events == 0 else Colours.RED, str(result.unsafe_enable_events))}")
        print(f"  Kill-switch bypasses:     {_c(Colours.GREEN if result.kill_switch_bypass_count == 0 else Colours.RED, str(result.kill_switch_bypass_count))}")
        print(f"  Timeout bypasses:         {result.timeout_bypass_count}")
        print(f"  Reset events:             {result.reset_events}")
        print(f"  Reset recovery pass rate: {result.reset_recovery_pass_rate:.1f}%")
        print(f"  Fault injection cases:    {result.fault_injection_cases}")
        print(f"  Faults detected:          {_c(Colours.GREEN, str(result.faults_detected))}")
        print(f"  Faults survived:          {result.faults_survived}")
        print(f"  FSM escape traps:         {_c(Colours.GREEN if result.fsm_escape_traps == 0 else Colours.RED, str(result.fsm_escape_traps))}")
        print(f"  High toggle warnings:     {result.high_toggle_warning_count}")
        print(f"  Replay match rate:        {_c(Colours.GREEN, f'{result.replay_match_rate:.0f}%')}")
        print()
        print(_c(Colours.DIM, LONGEVITY_PUBLIC_WORDING))
        print(_c(Colours.DIM, LONGEVITY_LIMITATION))

    if html_path:
        # Simple HTML for now
        html_content = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>LongevityBench Report</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; color: #1f2937; }}
h1 {{ font-size: 1.5rem; }} h2 {{ font-size: 1.1rem; margin-top: 1.5rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.5rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px,1fr)); gap: 1rem; margin: 1rem 0; }}
.card {{ background: #f9fafb; border-radius: 8px; padding: 1rem; }}
.card .label {{ font-size: 0.75rem; color: #6b7280; text-transform: uppercase; }}
.card .value {{ font-size: 1.75rem; font-weight: 700; }}
.green {{ color: #16a34a; }} .red {{ color: #dc2626; }} .blue {{ color: #2563eb; }}
.disclaimer {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: 0.875rem; color: #92400e; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.8rem; }}
th, td {{ padding: 0.4rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
th {{ background: #f3f4f6; font-weight: 600; }}
</style></head><body>
<h1>LongevityBench Report</h1>
<p style="color:#6b7280;">Version {__version__} | {result.timestamp_utc}</p>
<div class="disclaimer">{LONGEVITY_LIMITATION}</div>
<div class="cards">
<div class="card"><div class="label">Total Cycles</div><div class="value blue">{result.total_cycles:,}</div></div>
<div class="card"><div class="label">Unsafe Enables</div><div class="value {'green' if result.unsafe_enable_events == 0 else 'red'}">{result.unsafe_enable_events}</div></div>
<div class="card"><div class="label">Kill-Switch Bypasses</div><div class="value {'green' if result.kill_switch_bypass_count == 0 else 'red'}">{result.kill_switch_bypass_count}</div></div>
<div class="card"><div class="label">Faults Detected</div><div class="value green">{result.faults_detected}/{result.fault_injection_cases}</div></div>
<div class="card"><div class="label">Reset Recovery</div><div class="value blue">{result.reset_recovery_pass_rate:.1f}%</div></div>
<div class="card"><div class="label">Replay Match</div><div class="value green">{result.replay_match_rate:.0f}%</div></div>
</div>
<h2>Category Results</h2>
<table><tr><th>Category</th><th>Cycles</th><th>Unsafe</th><th>KS Bypass</th><th>Timeout</th><th>Resets</th><th>Faults</th><th>Detected</th><th>Status</th></tr>"""
        for cat, cr in result.category_results.items():
            status = "PASS" if ("LONGEVITY_PASS" in cr.get("statuses", [])) else "FAIL"
            cls = "green" if status == "PASS" else "red"
            html_content += f"<tr><td>{cat}</td><td>{cr['total_cycles']:,}</td><td>{cr['unsafe_enable_events']}</td><td>{cr['kill_switch_bypass_count']}</td><td>{cr['timeout_bypass_count']}</td><td>{cr['reset_events']}</td><td>{cr['fault_injection_cases']}</td><td>{cr['faults_detected']}</td><td class='{cls}'>{status}</td></tr>\n"
        html_content += "</table></body></html>"
        Path(html_path).write_text(html_content, encoding="utf-8")
        if not do_json:
            print(_c(Colours.GREEN, f"\nLongevityBench HTML report saved: {html_path}"))

    return 0


# ── synth subcommand ────────────────────────────────────────────────────────

def cmd_synth(args) -> int:
    """Run ChipSynthBench (PPA proxy benchmark)."""
    from .synthbench import run_synthbench
    from .synth_report import generate_synthbench_html

    do_json = getattr(args, "json", False)
    do_rank = getattr(args, "rank", False)
    html_path = getattr(args, "html", None)
    demo = getattr(args, "demo", False)
    bench_path = getattr(args, "path", None)

    result = run_synthbench(benchmark_path=bench_path, demo=demo)

    if do_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        # Human-readable summary
        print(_c(Colours.BOLD, "ChipSynthBench"))
        print(_c(Colours.DIM, f"Version {result.benchmark_version} | {result.timestamp_utc}"))
        print()

        # Summary cards
        print(f"  Candidates tested:    {result.total_candidates}")
        print(f"  Safe improved designs: {_c(Colours.GREEN, str(result.safe_improved_designs))}")
        print(f"  Unsafe rejected:       {_c(Colours.RED, str(result.unsafe_improvements_rejected))}")
        print(f"  Regressions detected:  {_c(Colours.RED, str(result.regressions_detected))}")
        print(f"  Eligible for ranking:  {result.eligible_for_ranking}")
        print()

        # Best tradeoff
        if result.best_tradeoff_candidate:
            print(f"  Best tradeoff: {_c(Colours.GREEN, result.best_tradeoff_candidate)}")
            print(f"    Area proxy improvement:    {_c(Colours.GREEN, f'{result.area_proxy_improvement_pct:.1f}%')}")
            print(f"    Timing-depth proxy improvement: {_c(Colours.GREEN, f'{result.timing_depth_improvement_pct:.1f}%')}")
            print(f"    Power proxy improvement:    {_c(Colours.GREEN, f'{result.power_proxy_improvement_pct:.1f}%')}")
        else:
            print(f"  Best tradeoff: {_c(Colours.RED, 'None')}")
        print()
        print(f"  Replay match: {_c(Colours.GREEN, f'{result.replay_match_rate:.0f}%')}")
        print()

        # Status
        if result.safe_improved_designs > 0:
            print(f"  Status: {_c(Colours.GREEN, 'SYNTHBENCH_PASS')}")
        else:
            print(f"  Status: {_c(Colours.RED, 'SYNTHBENCH_FAIL')}")
        print()

        # Public wording
        print(_c(Colours.DIM, result.public_wording))

        # Rank output
        if do_rank:
            print()
            print(_c(Colours.BOLD, "Candidate Rankings:"))
            for i, ds in enumerate(result.ranked_candidates, 1):
                if ds.is_best_tradeoff:
                    marker = " *BEST*"
                elif ds.can_rank:
                    marker = ""
                else:
                    marker = " (disqualified)"
                score_display = (
                    f"{ds.safe_improvement_score:.4f}"
                    if ds.safe_improvement_score != float("-inf")
                    else "N/A"
                )
                safety = "PASS" if ds.safety_pass else "FAIL"
                print(f"  #{i} {ds.candidate_id}: score={score_display} safety={safety}{marker}")

        # HTML report
        if html_path:
            html_content = generate_synthbench_html(result)
            Path(html_path).write_text(html_content, encoding="utf-8")
            print(_c(Colours.GREEN, f"\nChipSynthBench HTML report saved: {html_path}"))

    return 0


# ── silicon subcommand ──────────────────────────────────────────────────────

def cmd_silicon(args) -> int:
    """Run SiliconReadinessBench."""
    from .siliconbench import run_siliconbench
    from .silicon_report import generate_silicon_html
    from .toolchain import check_toolchain, format_toolchain_status

    do_json = getattr(args, "json", False)
    html_path = getattr(args, "html", None)
    demo = getattr(args, "demo", False)
    show_toolchain = getattr(args, "toolchain_status", False)
    bench_path = getattr(args, "path", None)

    # --toolchain-status: just show and exit
    if show_toolchain:
        report = check_toolchain()
        if do_json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            print(format_toolchain_status(report))
        return 0

    # Run the benchmark
    result = run_siliconbench(benchmark_path=bench_path, demo=demo)

    if do_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(_c(Colours.BOLD, "SiliconReadinessBench"))
        print(_c(Colours.DIM, f"Version {result.benchmark_version} | {result.timestamp_utc}"))
        print()

        # Toolchain summary
        tc = result.toolchain_report
        found_count = sum(1 for v in tc.values() if v.get("found", False))
        total_count = len(tc)
        print(f"  Toolchain coverage:     {found_count}/{total_count} "
              f"({result.toolchain_coverage:.0%})")
        for name, info in tc.items():
            status_str = "found" if info.get("found") else "skipped"
            print(f"    {name:<16s} {status_str}")
        print()

        # Summary cards
        print(f"  Designs tested:          {result.designs_tested}")
        print(f"  Safety precheck passed:  {_c(Colours.GREEN, str(result.safety_precheck_passed))}")
        print(f"  Lint pass rate:          {result.lint_pass_rate:.0%}")
        print(f"  Synthesis pass rate:     {result.synthesis_pass_rate:.0%}")
        print(f"  Formal pass rate:        {result.formal_pass_rate:.0%}")
        print(f"  FPGA flow pass rate:     {result.fpga_flow_pass_rate:.0%}")
        print(f"  ASIC flow ready rate:    {result.asic_flow_ready_rate:.0%}")
        print(f"  Evidence packs created:  {result.evidence_packs_created}")
        print(f"  Artifact hashes:         {result.artifact_hash_count}")
        print(f"  Replay match rate:       {_c(Colours.GREEN, f'{result.replay_match_rate:.0f}%')}")
        print()

        # Overall status
        if result.overall_status == st.SILICON_READINESS_PASS:
            print(f"  Overall: {_c(Colours.GREEN, 'SILICON_READINESS_PASS')}")
        else:
            print(f"  Overall: {_c(Colours.RED, 'SILICON_READINESS_FAIL')}")
        print()

        # Design table
        if result.design_results:
            print(_c(Colours.BOLD, "  Design Results:"))
            print(f"  {'Design':<30s} {'Safety':<8s} {'Lint':<8s} {'Synth':<8s} "
                  f"{'Formal':<8s} {'FPGA':<8s} {'ASIC':<8s} {'Overall':<16s}")
            print(f"  {'-' * 96}")
            for d in result.design_results:
                did = d["design_id"]
                sp = _c(Colours.GREEN, "PASS") if d["safety_precheck_status"] == st.RTL_SCAN_PASS else _c(Colours.RED, "FAIL")
                print(f"  {did:<30s} {sp:<8s} {_short_status(d['lint_status']):<8s} "
                      f"{_short_status(d['synthesis_status']):<8s} {_short_status(d['formal_status']):<8s} "
                      f"{_short_status(d['fpga_flow_status']):<8s} {_short_status(d['asic_flow_status']):<8s} "
                      f"{_short_status(d['overall_status']):<16s}")
            print()

        # Public wording
        print(_c(Colours.DIM, result.public_wording))
        print(_c(Colours.DIM, result.limitation))

        # HTML report
        if html_path:
            html_content = generate_silicon_html(result.to_dict())
            Path(html_path).write_text(html_content, encoding="utf-8")
            print(_c(Colours.GREEN, f"\nSiliconReadinessBench HTML report saved: {html_path}"))

    return 0


# ── fpga subcommand ────────────────────────────────────────────────────────

def cmd_fpga(args) -> int:
    """Run FPGABoardBench."""
    from .fpgabench import run_fpgabench, check_fpga_toolchain, format_fpga_toolchain_status
    from .fpga_report import generate_fpga_html

    do_json = getattr(args, "json", False)
    html_path = getattr(args, "html", None)
    demo = getattr(args, "demo", False)
    show_toolchain = getattr(args, "toolchain_status", False)
    bench_path = getattr(args, "path", None)
    board_profile = getattr(args, "board_profile", "generic_fpga")
    allow_unsafe = getattr(args, "allow_unsafe", False)

    # --toolchain-status: just show and exit
    if show_toolchain:
        report = check_fpga_toolchain()
        if do_json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_fpga_toolchain_status(report))
        return 0

    # Run the benchmark
    result = run_fpgabench(
        benchmark_path=bench_path,
        demo=demo,
        board_profile_name=board_profile,
        allow_unsafe=allow_unsafe,
    )

    if do_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(_c(Colours.BOLD, "FPGABoardBench"))
        print(_c(Colours.DIM, f"Version {result.benchmark_version} | {result.timestamp_utc} | Board: {result.board_profile}"))
        print()

        # Toolchain summary
        tc = result.toolchain_report
        found_count = sum(1 for v in tc.values() if v.get("found", False))
        total_count = len(tc)
        print(f"  Toolchain coverage:        {found_count}/{total_count} ({result.toolchain_coverage:.0%})")
        for name, info in tc.items():
            status_str = "found" if info.get("found") else "skipped"
            print(f"    {name:<20s} {status_str}")
        print()

        # Summary cards
        print(f"  Designs tested:            {result.designs_tested}")
        print(f"  Safety precheck passed:    {_c(Colours.GREEN, str(result.safety_precheck_passed))}")
        print(f"  Safety pass rate:          {result.safety_precheck_pass_rate:.0%}")
        print(f"  Pin constraint pass rate:  {result.pin_constraint_pass_rate:.0%}")
        print(f"  FPGA synth pass rate:      {result.fpga_synth_pass_rate:.0%}")
        print(f"  Place-route pass rate:     {result.place_route_pass_rate:.0%}")
        print(f"  Bitstream ready rate:      {result.bitstream_ready_rate:.0%}")
        print(f"  Board evidence attached:   {result.board_evidence_attached_count}")
        print(f"  Evidence packs created:    {result.evidence_packs_created}")
        print(f"  Artifact hashes:           {result.artifact_hash_count}")
        print()

        # Overall status
        if result.overall_status == st.FPGA_BENCH_PASS:
            print(f"  Overall: {_c(Colours.GREEN, 'FPGA_BENCH_PASS')}")
        else:
            print(f"  Overall: {_c(Colours.RED, 'FPGA_BENCH_FAIL')}")
        print()

        # Design table
        if result.design_results:
            print(_c(Colours.BOLD, "  Design Results:"))
            print(f"  {'Design':<35s} {'Safety':<8s} {'Pin':<8s} {'Synth':<8s} "
                  f"{'PnR':<8s} {'Bitstrm':<8s} {'BrdEv':<8s} {'Overall':<16s}")
            print(f"  {'-' * 100}")
            for d in result.design_results:
                did = d["design_id"]
                sp = _c(Colours.GREEN, "PASS") if d["safety_precheck_status"] == st.RTL_SCAN_PASS else _c(Colours.RED, "FAIL")
                print(f"  {did:<35s} {sp:<8s} {_short_status(d['pin_constraint_status']):<8s} "
                      f"{_short_status(d['fpga_synth_status']):<8s} {_short_status(d['place_route_status']):<8s} "
                      f"{_short_status(d['bitstream_status']):<8s} {_short_status(d['board_evidence_status']):<8s} "
                      f"{_short_status(d['overall_status']):<16s}")
            print()

        # Public wording
        print(_c(Colours.DIM, result.public_wording))
        print(_c(Colours.DIM, result.limitation))

        # HTML report
        if html_path:
            html_content = generate_fpga_html(result.to_dict())
            Path(html_path).write_text(html_content, encoding="utf-8")
            print(_c(Colours.GREEN, f"\nFPGABoardBench HTML report saved: {html_path}"))

    return 0


def _short_status(status: str) -> str:
    """Shorten a status for table display."""
    s = status.upper()
    if "SKIPPED" in s:
        return _c(Colours.DIM, "SKIP")
    if "PASS" in s and "FAIL" not in s:
        return _c(Colours.GREEN, "PASS")
    if "FAIL" in s:
        return _c(Colours.RED, "FAIL")
    if "BLOCKED" in s:
        return _c(Colours.YELLOW, "BLOCK")
    return _c(Colours.DIM, s[:8])


# ── Argument Parser ──────────────────────────────────────────────────────────

def cmd_tinytapeout(args) -> int:
    """Run TinyTapeoutPrep."""
    from .tinytapeout_prep import run_tinytapeout_prep
    from .tt_report import generate_tinytapeout_html

    do_json = getattr(args, "json", False)
    html_path = getattr(args, "html", None)
    demo = getattr(args, "demo", False)
    gen_template = getattr(args, "generate_template", False)
    sub_check = getattr(args, "submission_check", False)
    output_dir = getattr(args, "path", None)

    result = run_tinytapeout_prep(demo=demo, benchmark_path=output_dir, output_dir=output_dir)

    if do_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str))
    else:
        print(_c(Colours.BOLD, "TinyTapeoutPrep"))
        print(_c(Colours.DIM, f"Version {result.benchmark_version} | {result.timestamp_utc}"))
        print()
        print(f"  Designs generated:        {result.designs_generated}")
        print(f"  Wrappers created:         {result.wrappers_generated}")
        print(f"  Pinout valid:             {_c(Colours.GREEN, str(result.pinout_checks_passed))}")
        print(f"  Submission checks passed: {result.submission_checks_passed}")
        print(f"  Safety properties:        {result.safety_properties_count}")
        print(f"  Private leaks:            {_c(Colours.RED if result.private_leak_count > 0 else Colours.GREEN, str(result.private_leak_count))}")
        print(f"  Testbenches:              {result.testbench_count}")
        print(f"  Evidence packs:           {result.evidence_packs_created}")
        print(f"  Manual review items:      {result.manual_review_items_count}")
        print()
        if result.overall_status == st.TINYTAPEOUT_PREP_PASS:
            print(f"  Overall: {_c(Colours.GREEN, 'TINYTAPEOUT_PREP_PASS')}")
        else:
            print(f"  Overall: {_c(Colours.RED, 'TINYTAPEOUT_PREP_FAIL')}")

        # Design table
        if result.design_results:
            print()
            print(_c(Colours.BOLD, "  Design Results:"))
            print(f"  {'Design':<35s} {'Wrapper':<8s} {'Pinout':<8s} {'SubChk':<8s} {'Safety':<8s} {'Overall':<16s}")
            print(f"  {'-' * 90}")
            for d in result.design_results:
                did = d["design_id"]
                print(f"  {did:<35s} {_short_status(d['wrapper_status']):<8s} "
                      f"{_short_status(d['pinout_status']):<8s} "
                      f"{_short_status(d['submission_check_status']):<8s} "
                      f"{_short_status(d['safety_result']):<8s} "
                      f"{_short_status(d['overall_status']):<16s}")
            print()

        # Pinout summary
        print(_c(Colours.BOLD, "  Pinout:"))
        for pin, sig in sorted(result.pinout.items()):
            print(f"    {pin:<14s} -> {sig}")
        print()

        # Manual review items
        if result.manual_review_items:
            print(_c(Colours.BOLD, "  Manual Review Items:"))
            for item in result.manual_review_items:
                print(f"    - {item}")
            print()

    if html_path:
        html = generate_tinytapeout_html(result.to_dict())
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML report saved: {html_path}")

    return 0


def cmd_physical(args) -> int:
    """Run OpenLanePhysicalBench."""
    from .openlane_physical import run_physical_bench, check_toolchain_status
    from .physical_report import generate_physical_html

    do_json = getattr(args, "json", False)
    html_path = getattr(args, "html", None)
    demo = getattr(args, "demo", False)
    tc_status = getattr(args, "toolchain_status", False)
    parse_reports = getattr(args, "parse_reports", None)
    allow_unsafe = getattr(args, "allow_unsafe", False)
    bench_path = getattr(args, "path", None)

    # Toolchain status only
    if tc_status:
        tc = check_toolchain_status()
        print(_c(Colours.BOLD, "OpenLane/OpenROAD Toolchain Status"))
        print()
        for name, info in tc.items():
            if info.get("found"):
                ver = info.get("version", "")
                ver_str = f" ({ver})" if ver else ""
                print(f"  {name:<12s} {_c(Colours.GREEN, 'found')}  {info.get('path', '')}{ver_str}")
            else:
                print(f"  {name:<12s} {_c(Colours.YELLOW, 'skipped')}  {info.get('note', '')}")
        return 0

    # Parse reports only
    if parse_reports:
        from .openroad_reports import parse_fixtures_directory
        parsed = parse_fixtures_directory(parse_reports)
        if do_json:
            print(json.dumps(parsed.to_dict(), indent=2, sort_keys=True))
        else:
            print(_c(Colours.BOLD, f"Parsed {parsed.parsed_count} reports from {parse_reports}"))
            print(f"  DRC:  {parsed.drc.to_dict() if parsed.drc else 'N/A'}")
            print(f"  LVS:  {parsed.lvs.to_dict() if parsed.lvs else 'N/A'}")
            print(f"  Timing: {parsed.timing.to_dict() if parsed.timing else 'N/A'}")
            print(f"  Area: {parsed.area_stats}")
            print(f"  Skipped: {parsed.skipped_count}")
        return 0

    # Full bench run
    result = run_physical_bench(
        demo=demo,
        benchmark_path=bench_path,
        allow_unsafe=allow_unsafe,
    )

    if do_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str))
    else:
        print(_c(Colours.BOLD, "OpenLanePhysicalBench"))
        print(_c(Colours.DIM, f"Version {result.benchmark_version} | {result.timestamp_utc}"))
        print()
        m = result.metrics
        print(f"  Designs tested:          {m.get('designs_tested', 0)}")
        print(f"  Config pass rate:        {m.get('openlane_config_pass_rate', 0):.0%}")
        print(f"  OpenROAD pass rate:      {m.get('openroad_run_pass_rate', 0):.0%}")
        print(f"  DRC violations:          {m.get('drc_violation_count', 0)}")
        print(f"  LVS mismatches:          {m.get('lvs_mismatch_count', 0)}")
        print(f"  Worst negative slack:    {m.get('worst_negative_slack', 0):.2f} ns")
        print(f"  GDS artifacts:           {m.get('gds_artifact_count', 0)}")
        print(f"  Artifact hashes:         {m.get('artifact_hash_count', 0)}")
        print(f"  Toolchain coverage:      {m.get('toolchain_coverage', 0):.0%}")
        print(f"  Evidence packs:          {m.get('evidence_packs_created', 0)}")
        print(f"  Manual review items:     {m.get('manual_review_items', 0)}")
        print()

        if result.overall_status == st.PHYSICAL_BENCH_PASS:
            print(f"  Overall: {_c(Colours.GREEN, 'PHYSICAL_BENCH_PASS')}")
        else:
            print(f"  Overall: {_c(Colours.RED, 'PHYSICAL_BENCH_FAIL')}")
        print()

        # Design table
        if result.design_results:
            print(_c(Colours.BOLD, "  Design Results:"))
            hdr = f"  {'Design':<38s} {'Safety':<10s} {'OLCfg':<12s} {'DRC':<12s} {'LVS':<12s} {'GDS':<12s} {'Overall':<20s}"
            print(hdr)
            print(f"  {'-' * 120}")
            for d in result.design_results:
                did = d.get("design_id", "?")
                print(f"  {did:<38s} {_short_status(d.get('safety_status', '')):<10s} "
                      f"{_short_status(d.get('openlane_config_status', '')):<12s} "
                      f"{_short_status(d.get('drc_status', '')):<12s} "
                      f"{_short_status(d.get('lvs_status', '')):<12s} "
                      f"{_short_status(d.get('gds_status', '')):<12s} "
                      f"{_short_status(d.get('overall_status', '')):<20s}")
            print()

        # Manual review items
        if result.manual_review_items:
            print(_c(Colours.BOLD, "  Manual Review Items:"))
            for item in result.manual_review_items:
                print(f"    - {item}")
            print()

    if html_path:
        html = generate_physical_html(result.to_dict())
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML report saved: {html_path}")

    return 0


def cmd_formal(args) -> int:
    """Run FormalGate-Lite."""
    from .formalgate_bench import run_formal_bench, check_formal_toolchain_status, list_formal_properties
    from .formalgate_report import generate_formal_html

    do_json = getattr(args, "json", False)
    html_path = getattr(args, "html", None)
    demo = getattr(args, "demo", False)
    tc_status = getattr(args, "toolchain_status", False)
    list_props = getattr(args, "list_properties", False)
    bench_path = getattr(args, "path", None)

    # List properties only
    if list_props:
        props = list_formal_properties()
        print(_c(Colours.BOLD, "FormalGate-Lite — Available Formal Properties"))
        print(_c(Colours.DIM, f"ChipGate v{__version__}\n"))
        for p in props:
            pid = p.get("id", "?")
            desc = p.get("description", "")
            cat = p.get("category", "")
            print(f"  {pid:<40s} [{cat}] {desc}")
        print(f"\n  {len(props)} properties total")
        return 0

    # Toolchain status only
    if tc_status:
        tc = check_formal_toolchain_status()
        print(_c(Colours.BOLD, "FormalGate-Lite — Toolchain Status"))
        print(_c(Colours.DIM, f"ChipGate v{__version__}\n"))
        for name, info in tc.items():
            if info.get("found"):
                ver = info.get("version", "")
                ver_str = f" ({ver})" if ver else ""
                print(f"  {name:<16s} {_c(Colours.GREEN, 'found')}  {info.get('path', '')}{ver_str}")
            else:
                print(f"  {name:<16s} {_c(Colours.YELLOW, 'skipped')}  {info.get('note', '')}")
        return 0

    # Full bench run
    result = run_formal_bench(
        demo=demo,
        benchmark_path=bench_path,
    )

    if do_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str))
    else:
        print(_c(Colours.BOLD, "FormalGate-Lite"))
        print(_c(Colours.DIM, f"Version {result.benchmark_version} | {result.timestamp_utc}"))
        print()
        m = result.metrics
        print(f"  Designs tested:          {m.get('designs_tested', 0)}")
        print(f"  Properties checked:      {m.get('properties_checked', 0)}")
        print(f"  Property pass rate:      {m.get('property_pass_rate', 0):.0%}")
        print(f"  Property fail rate:      {m.get('property_fail_rate', 0):.0%}")
        print(f"  Property skipped rate:   {m.get('property_skipped_rate', 0):.0%}")
        print(f"  Counterexamples found:  {m.get('counterexample_count', 0)}")
        print(f"  Evidence packs:          {m.get('evidence_packs_created', 0)}")
        print(f"  Manual review items:     {m.get('manual_review_items', 0)}")
        print()

        if result.overall_status == st.FORMAL_PROPERTY_PASS:
            print(f"  Overall: {_c(Colours.GREEN, 'FORMAL_PROPERTY_PASS')}")
        else:
            print(f"  Overall: {_c(Colours.RED, str(result.overall_status))}")
        print()

        # Design table
        if result.design_results:
            print(_c(Colours.BOLD, "  Design Results:"))
            hdr = f"  {'Design':<38s} {'Safety':<10s} {'Props':<8s} {'Pass':<6s} {'Fail':<6s} {'Skip':<6s} {'Overall':<24s}"
            print(hdr)
            print(f"  {'-' * 110}")
            for d in result.design_results:
                did = d.get("design_id", "?")
                print(f"  {did:<38s} {_short_status(d.get('safety_status', '')):<10s} "
                      f"{d.get('properties_checked', 0):<8d} "
                      f"{d.get('properties_passed', 0):<6d} "
                      f"{d.get('properties_failed', 0):<6d} "
                      f"{d.get('properties_skipped', 0):<6d} "
                      f"{_short_status(d.get('overall_status', '')):<24s}")
            print()

        # Manual review items
        if result.manual_review_items:
            print(_c(Colours.BOLD, "  Manual Review Items:"))
            for item in result.manual_review_items:
                print(f"    - {item}")
            print()

    if html_path:
        html = generate_formal_html(result.to_dict())
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML report saved: {html_path}")

    return 0


def cmd_mutation(args: argparse.Namespace) -> int:
    """Run MutationBench stress-test."""
    from .mutationbench import run_mutation_bench, generate_mutation_count
    from .mutators import get_mutation_names
    from .mutation_catalog import list_categories

    do_json = getattr(args, "json", False)
    html_path = getattr(args, "html", None)
    do_demo = getattr(args, "demo", False)
    list_mutators_flag = getattr(args, "list_mutators", False)
    bench_path = getattr(args, "path", None)
    generate_count = getattr(args, "generate", None)
    seed_path = getattr(args, "seed", None)

    if list_mutators_flag:
        print(_c(Colours.BOLD, "MutationBench — Available Mutation Categories"))
        print(_c(Colours.DIM, f"ChipGate v{__version__}\n"))
        for cat in list_categories():
            criticality = cat.get("criticality", "medium")
            tag = _c(Colours.RED, "[CRITICAL]") if criticality == "critical" else ""
            print(f"  - {cat['name']:30s} {cat['description'][:50]} {tag}")
        print(f"\n  Total: {len(list_categories())} categories")
        return 0

    # Generate-only mode (no scanning)
    if generate_count is not None and not do_demo:
        mutations = generate_mutation_count(
            count=generate_count,
            seed_path=seed_path,
        )
        print(_c(Colours.BOLD, "MutationBench — Generate Mode"))
        print(f"  Mutations generated: {len(mutations)}")
        print(_c(Colours.DIM, "Generated files saved to benchmarks/mutationbench_v0/generated/"))
        if do_json:
            print(json.dumps(mutations, indent=2, default=str))
        return 0

    result = run_mutation_bench(
        demo=do_demo,
        benchmark_path=bench_path,
        seed=seed_path,
        count=generate_count or 1000,
    )

    if do_json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return 0 if not result.metrics.get("mutations_escaped", 0) else 1

    # Terminal output — matches spec demo format
    m = result.metrics
    det = m.get("mutations_detected", 0)
    esc = m.get("mutations_escaped", 0)
    gen = m.get("mutations_generated", 0)
    det_rate = m.get("mutation_detection_rate", 0)
    bypass_rate = m.get("unsafe_bypass_detection_rate", 0)
    ks_rate = m.get("kill_switch_mutation_detection_rate", 0)
    to_rate = m.get("timeout_mutation_detection_rate", 0)
    rs_rate = m.get("reset_mutation_detection_rate", 0)
    replay = m.get("replay_match_rate", 0)

    if do_demo:
        print(_c(Colours.BOLD, "MutationBench Demo"))
        print()
        print(f"Seed designs: {result.seed_designs_tested}")
        print(f"Mutations generated: {gen}")
        print(f"Mutations detected: {_c(Colours.GREEN, str(det))}")
        print(f"Mutations escaped: {_c(Colours.RED, str(esc))}")
        print(f"Critical unsafe bypasses detected: {bypass_rate:.0%}")
        print(f"Kill-switch mutations detected: {ks_rate:.0%}")
        print(f"Timeout mutations detected: {to_rate:.0%}")
        print(f"Reset mutations detected: {rs_rate:.0%}")
        print(f"Replay match: {replay:.0%}")
        print()
        if esc > 0:
            status_text = "MUTATIONBENCH_PASS_WITH_REVIEW"
            print(f"Status: {_c(Colours.YELLOW, status_text)}")
            print("Escaped mutations require rule hardening.")
        else:
            print(f"Status: {_c(Colours.GREEN, result.overall_status)}")
    else:
        print(_c(Colours.BOLD, "MutationBench"))
        print(_c(Colours.DIM, f"ChipGate v{__version__} | {result.timestamp_utc}"))
        print()
        print(f"  Seed designs tested: {result.seed_designs_tested}")
        print(f"  Mutations generated: {gen}")
        print(f"  Mutations detected:  {_c(Colours.GREEN, str(det))}")
        print(f"  Mutations escaped:   {_c(Colours.RED, str(esc))}")
        print(f"  Detection rate:      {det_rate:.1%}")
        print()
        print(f"  Overall: {_c(Colours.GREEN if 'PASS' in result.overall_status else Colours.RED, result.overall_status)}")
        if result.review_items:
            for item in result.review_items:
                print(f"  {_c(Colours.YELLOW, '[REVIEW]')} {item}")

    print(_c(Colours.DIM, result.public_wording))

    if html_path:
        from .mutation_report import generate_mutation_html
        html = generate_mutation_html(result.to_dict())
        Path(html_path).write_text(html, encoding="utf-8")
        print(_c(Colours.GREEN, f"\nHTML report saved: {html_path}"))

    return 0 if "PASS" in result.overall_status else 1


def cmd_ci(args: argparse.Namespace) -> int:
    """Run RealToolchainCI pipeline."""
    from .ci_matrix import run_ci
    from .ci_artifacts import create_artifact_manifest
    from .ci_report import generate_ci_html
    from .ci_toolchain import detect_toolchain

    # Toolchain status only
    if getattr(args, "toolchain_status", False):
        tc = detect_toolchain()
        print(_c(Colours.BOLD, "ChipGate CI — Toolchain Status"))
        print(_c(Colours.DIM, f"ChipGate v{__version__}\n"))
        for name, info in tc.items():
            if info.get("found"):
                ver = info.get("version", "")
                ver_str = f" ({ver})" if ver else ""
                print(f"  {_c(Colours.GREEN, '[FOUND]')} {name}: {info.get('path', '')}{ver_str}")
            else:
                print(f"  {_c(Colours.YELLOW, '[MISSING]')} {name}")
        found = sum(1 for v in tc.values() if v.get("found"))
        missing = sum(1 for v in tc.values() if not v.get("found"))
        print(f"\n  {found} found, {missing} missing")
        return 0

    mode = "full" if getattr(args, "full", False) else "quick"
    result = run_ci(mode=mode)

    # Terminal output
    print(_c(Colours.BOLD, f"ChipGate CI — {mode.upper()} Mode"))
    print(_c(Colours.DIM, f"ChipGate v{__version__} | {result.timestamp_utc}\n"))
    overall = result.overall_status
    if overall == st.CI_PASS:
        print(_c(Colours.GREEN, f"  Overall: {overall}"))
    elif overall == st.CI_FAIL:
        print(_c(Colours.RED, f"  Overall: {overall}"))
    else:
        print(_c(Colours.YELLOW, f"  Overall: {overall}"))

    print(f"  Tests: {result.python_tests_passed} passed, {result.python_tests_failed} failed")
    print(f"  Tools: {result.toolchain_tools_found} found, {result.toolchain_tools_missing} missing")
    print(f"  Stages: {len(result.stages)}")
    print(f"  Demos: {len(result.demo_results)}")

    # Hygiene summary
    if result.hygiene:
        h = result.hygiene
        all_pass = h.get("passed", False)
        if all_pass:
            print(f"  Hygiene: {_c(Colours.GREEN, 'PASS')}")
        else:
            print(f"  Hygiene: {_c(Colours.RED, 'FAIL')}")
            for issue in h.get("issues", []):
                print(f"    - {issue}")

    # Stage results
    for s in result.stages:
        name = s.get("stage_name", "?")
        status = s.get("status", "?")
        if "PASS" in status:
            clr = Colours.GREEN
        elif "FAIL" in status:
            clr = Colours.RED
        else:
            clr = Colours.YELLOW
        dur = s.get("duration_seconds", 0)
        print(f"  {_c(clr, f'[{status}]')} {name} ({dur:.1f}s)")

    # Demo results
    for d in result.demo_results:
        cmd = d.get("command", "?")
        ds = d.get("status", "?")
        if ds == st.CI_PASS:
            clr = Colours.GREEN
        else:
            clr = Colours.RED
        print(f"  {_c(clr, f'[{ds}]')} {cmd}")

    # Disclaimer
    print(f"\n{_c(Colours.DIM, st.CI_PUBLIC_WORDING)}")

    # JSON output
    if getattr(args, "json", False):
        data = result.to_dict()
        manifest = create_artifact_manifest(data)
        data["artifact_manifest"] = manifest
        print("\n--- JSON ---")
        print(json.dumps(data, indent=2, default=str))

    # HTML output
    html_path = getattr(args, "html", None)
    if html_path:
        html = generate_ci_html(result.to_dict())
        Path(html_path).write_text(html, encoding="utf-8")
        print(f"\nHTML report saved to {html_path}")

    return 0 if overall in (st.CI_PASS, st.CI_PARTIAL) else 1


def cmd_passport(args: argparse.Namespace) -> int:
    """Handle the 'passport' subcommand.

    DTL Verified Design Passport does not prove that a design is safe,
    correct, certified, fabrication-ready, commercially validated or
    production-ready.
    """
    from .design_passport import (
        run_demo as _run_demo,
        run_passport_pipeline,
        verify_passport_file,
        export_badge_for_passport,
        run_replay_for_artifact,
    )
    from .passport_report import generate_passport_json_report

    # --demo mode
    if getattr(args, "demo", False):
        html_path = getattr(args, "html", None)
        result = _run_demo(output_json=None, output_html=html_path)
        p = result["passport"]
        badge = result["badge"]

        print(f"Passport ID : {p['passport_id']}")
        print(f"Artifact    : {p['artifact_id']} ({p['artifact_type']})")
        print(f"Risk Level  : {p['risk_level']}")
        print(f"Status      : {p['passport_status']}")
        print(f"Export      : {p['export_decision']}")
        print(f"Badge       : {badge.get('badge', '?')}")
        print(f"Gates Run   : {len(p.get('gates_run', []))}")
        print(f"Gates Passed: {len(p.get('gates_passed', []))}")
        print(f"Gates Failed: {len(p.get('gates_failed', []))}")

        if getattr(args, "json", False):
            print("\n--- JSON ---")
            print(generate_passport_json_report(result))
        return 0

    # --verify-passport mode
    verify_path = getattr(args, "verify_passport", None)
    if verify_path:
        vr = verify_passport_file(verify_path)
        print(f"Replay Match : {vr.get('replay_match', False)}")
        print(f"Replay Status: {vr.get('replay_status', '?')}")
        if vr.get("errors"):
            for e in vr["errors"]:
                print(f"  Error: {e}")
        return 0 if vr.get("replay_match") else 1

    # --export-badge mode
    export_dir = getattr(args, "export_badge", None)
    if export_dir:
        # Need a passport file to load
        artifact_path = getattr(args, "artifact", None)
        if not artifact_path:
            print("Error: --export-badge requires --artifact <passport.json>")
            return 1
        badge_out = export_badge_for_passport(artifact_path, export_dir)
        if "error" in badge_out:
            print(f"Error: {badge_out['error']}")
            return 1
        print(f"Badge: {badge_out.get('badge', '?')}")
        if badge_out.get("json_path"):
            print(f"JSON : {badge_out['json_path']}")
        if badge_out.get("svg_path"):
            print(f"SVG  : {badge_out['svg_path']}")
        return 0

    # --replay mode
    if getattr(args, "replay", False):
        artifact_path = getattr(args, "artifact", None)
        content = ""
        if artifact_path and os.path.isfile(artifact_path):
            from .passport_artifacts import read_artifact_content
            content = read_artifact_content(artifact_path)
        result = run_replay_for_artifact(
            artifact_id="replay_001",
            file_path=artifact_path or "",
            content=content,
        )
        r = result.get("replay", {})
        print(f"Replay Match : {r.get('replay_match', False)}")
        print(f"Replay Status: {r.get('replay_status', '?')}")
        return 0 if r.get("replay_match") else 1

    # --create-passport or --artifact mode
    artifact_path = getattr(args, "artifact", None)
    if artifact_path:
        from .passport_artifacts import read_artifact_content
        content = read_artifact_content(artifact_path)
        html_path = getattr(args, "html", None)
        result = run_passport_pipeline(
            artifact_id=os.path.basename(artifact_path),
            file_path=artifact_path,
            content=content,
            output_html=html_path,
        )
        p = result["passport"]
        badge = result["badge"]
        print(f"Passport ID : {p['passport_id']}")
        print(f"Artifact    : {p['artifact_id']} ({p['artifact_type']})")
        print(f"Risk Level  : {p['risk_level']}")
        print(f"Status      : {p['passport_status']}")
        print(f"Export      : {p['export_decision']}")
        print(f"Badge       : {badge.get('badge', '?')}")

        if getattr(args, "json", False):
            print("\n--- JSON ---")
            print(generate_passport_json_report(result))
        return 0

    # No specific mode selected -- show help
    print("Use --demo to run a passport demonstration.")
    print("Use --artifact <file> to create a passport for a file.")
    print("Use --verify-passport <file.json> to verify a passport.")
    print("Use --export-badge <dir> --artifact <file.json> to export badge.")
    print("Use --replay --artifact <file> to build and replay a passport.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chipgate",
        description="ChipGate catches unsafe RTL before it becomes silicon.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan subcommand
    scan_parser = subparsers.add_parser("scan", help="Scan a Verilog file for safety issues")
    scan_parser.add_argument("file", help="Path to Verilog/SystemVerilog file")
    scan_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    scan_parser.add_argument("--evidence", action="store_true", help="Generate evidence pack JSON file")
    scan_parser.add_argument("--lint", action="store_true", help="Run external lint (Verilator) if available")
    scan_parser.add_argument("--formal", action="store_true", help="Check formal verification readiness")
    scan_parser.add_argument("--safety", action="store_true", help="Run safety pattern analysis")
    scan_parser.set_defaults(func=cmd_scan)

    # lint subcommand
    lint_parser = subparsers.add_parser("lint", help="Run external lint on a Verilog file")
    lint_parser.add_argument("file", help="Path to Verilog/SystemVerilog file")
    lint_parser.set_defaults(func=cmd_lint)

    # bench subcommand
    bench_parser = subparsers.add_parser(
        "bench",
        help="Run DTL-ChipBench (model-free synthetic gate benchmark)",
    )
    bench_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to benchmark cases directory (optional, uses built-in cases if omitted)",
    )
    bench_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    bench_parser.add_argument("--html", metavar="FILE", default=None,
                              help="Generate HTML report to FILE")
    bench_parser.add_argument("--evidence", action="store_true",
                              help="Generate evidence records for each case")
    bench_parser.add_argument("--demo", action="store_true",
                              help="Run demo subset (12 cases)")
    bench_parser.add_argument("--mode", choices=VALID_MODES, default="chipgate_only",
                              help="Benchmark mode (default: chipgate_only)")
    bench_parser.add_argument("--adapter", metavar="FILE", default=None,
                              help="Path to JSONL proposals or Python adapter module")
    bench_parser.add_argument("--compare-modes", action="store_true",
                              help="Run all three modes and compare results")
    # Legacy compat
    bench_parser.add_argument("--compare-baseline", action="store_true",
                              help="(Legacy) Compare DTL-gated vs ungated baseline")
    bench_parser.set_defaults(func=cmd_bench)

    # longevity subcommand
    longevity_parser = subparsers.add_parser(
        "longevity",
        help="Run LongevityBench (RTL-level reliability and stress benchmark)",
    )
    longevity_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    longevity_parser.add_argument("--html", metavar="FILE", default=None,
                                  help="Generate HTML report to FILE")
    longevity_parser.add_argument("--demo", action="store_true",
                                  help="Run demo subset")
    longevity_parser.set_defaults(func=cmd_longevity)

    # synth subcommand (ChipSynthBench / PPA-Bench)
    synth_parser = subparsers.add_parser(
        "synth",
        help="Run ChipSynthBench (PPA proxy candidate benchmark)",
    )
    synth_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to synthbench directory (optional, uses built-in candidates if omitted)",
    )
    synth_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    synth_parser.add_argument("--html", metavar="FILE", default=None,
                              help="Generate HTML report to FILE")
    synth_parser.add_argument("--rank", action="store_true",
                              help="Show ranked candidate list")
    synth_parser.add_argument("--demo", action="store_true",
                              help="Run demo subset (7 candidates)")
    synth_parser.set_defaults(func=cmd_synth)

    # silicon subcommand (SiliconReadinessBench)
    silicon_parser = subparsers.add_parser(
        "silicon",
        help="Run SiliconReadinessBench (tool-flow readiness checks)",
    )
    silicon_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to siliconbench directory (optional, uses built-in designs if omitted)",
    )
    silicon_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    silicon_parser.add_argument("--html", metavar="FILE", default=None,
                                help="Generate HTML report to FILE")
    silicon_parser.add_argument("--demo", action="store_true",
                                help="Run demo subset (4 built-in designs)")
    silicon_parser.add_argument("--toolchain-status", action="store_true",
                                help="Show toolchain status and exit")
    silicon_parser.add_argument("--allow-unsafe", action="store_true",
                                help="Allow unsafe designs to proceed to tool stages")
    silicon_parser.set_defaults(func=cmd_silicon)

    # fpga subcommand (FPGABoardBench)
    fpga_parser = subparsers.add_parser(
        "fpga",
        help="Run FPGABoardBench (FPGA-oriented readiness checks)",
    )
    fpga_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to fpgabench directory (optional, uses built-in designs if omitted)",
    )
    fpga_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    fpga_parser.add_argument("--html", metavar="FILE", default=None,
                              help="Generate HTML report to FILE")
    fpga_parser.add_argument("--demo", action="store_true",
                              help="Run demo subset (4 built-in designs)")
    fpga_parser.add_argument("--toolchain-status", action="store_true",
                              help="Show FPGA toolchain status and exit")
    fpga_parser.add_argument("--board-profile", metavar="NAME", default="generic_fpga",
                              help="Board profile to use (default: generic_fpga)")
    fpga_parser.add_argument("--allow-unsafe", action="store_true",
                              help="Allow unsafe designs to proceed to tool stages")
    fpga_parser.set_defaults(func=cmd_fpga)

    # tinytapeout subcommand (TinyTapeoutPrep)
    tt_parser = subparsers.add_parser(
        "tinytapeout",
        help="Run TinyTapeoutPrep (open-silicon submission preparation)",
    )
    tt_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to output directory (optional, uses temp directory if omitted)",
    )
    tt_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    tt_parser.add_argument("--html", metavar="FILE", default=None,
                            help="Generate HTML report to FILE")
    tt_parser.add_argument("--demo", action="store_true",
                            help="Run demo: generate and validate TT artifacts")
    tt_parser.add_argument("--generate-template", action="store_true",
                            help="Generate template artifacts only (no validation)")
    tt_parser.add_argument("--submission-check", action="store_true",
                            help="Run submission readiness checks on existing artifacts")
    tt_parser.set_defaults(func=cmd_tinytapeout)

    # physical subcommand (OpenLanePhysicalBench)
    phys_parser = subparsers.add_parser(
        "physical",
        help="Run OpenLanePhysicalBench (ASIC physical-flow readiness checks)",
    )
    phys_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to openlanephysical benchmark directory (optional, uses built-in if omitted)",
    )
    phys_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    phys_parser.add_argument("--html", metavar="FILE", default=None,
                             help="Generate HTML report to FILE")
    phys_parser.add_argument("--demo", action="store_true",
                             help="Run demo subset (built-in designs)")
    phys_parser.add_argument("--toolchain-status", action="store_true",
                             help="Show OpenLane/OpenROAD toolchain status and exit")
    phys_parser.add_argument("--parse-reports", metavar="DIR", default=None,
                             help="Only parse report fixtures from DIR")
    phys_parser.add_argument("--allow-unsafe", action="store_true",
                             help="Allow unsafe designs to proceed to tool stages")
    phys_parser.set_defaults(func=cmd_physical)

    # formal subcommand (FormalGate-Lite)
    formal_parser = subparsers.add_parser(
        "formal",
        help="Run FormalGate-Lite formal safety property checks",
    )
    formal_parser.add_argument("path", nargs="?", default=None,
                                help="Path to formal benchmark directory (optional, uses built-in designs if omitted)")
    formal_parser.add_argument("--demo", action="store_true",
                              help="Run with built-in demo designs")
    formal_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    formal_parser.add_argument("--html", metavar="FILE", default=None,
                              help="Generate HTML report to FILE")
    formal_parser.add_argument("--list-properties", action="store_true",
                              help="List all available formal properties and exit")
    formal_parser.add_argument("--toolchain-status", action="store_true",
                              help="Show which formal tools are available and exit")
    formal_parser.set_defaults(func=cmd_formal)

    # ci subcommand (RealToolchainCI)
    ci_parser = subparsers.add_parser(
        "ci",
        help="Run RealToolchainCI (Python tests + optional real toolchain checks)",
    )
    ci_parser.add_argument("--quick", action="store_true",
                             help="Quick mode: Python tests + hygiene + demos (default)")
    ci_parser.add_argument("--full", action="store_true",
                             help="Full mode: quick + real Verilator/Yosys/Sby/OpenLane/OpenROAD")
    ci_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    ci_parser.add_argument("--html", metavar="FILE", default=None,
                             help="Generate HTML report to FILE")
    ci_parser.add_argument("--toolchain-status", action="store_true",
                             help="Show CI toolchain status and exit")
    ci_parser.set_defaults(func=cmd_ci)

    # mutation subcommand (MutationBench)
    mutation_parser = subparsers.add_parser(
        "mutation",
        help="Stress-test ChipGate with unsafe RTL mutations",
    )
    mutation_parser.add_argument("path", nargs="?", default=None,
                                help="Path to mutation benchmark directory")
    mutation_parser.add_argument("--demo", action="store_true",
                              help="Run built-in mutation demo")
    mutation_parser.add_argument("--generate", type=int, default=None,
                              nargs="?", const=1000,
                              help="Number of mutations to generate (generate-only mode)")
    mutation_parser.add_argument("--seed", metavar="FILE", default=None,
                              help="Path to a seed design file")
    mutation_parser.add_argument("--json", action="store_true",
                              help="Output results as JSON")
    mutation_parser.add_argument("--html", metavar="FILE", default=None,
                              help="Generate HTML report to FILE")
    mutation_parser.add_argument("--list-mutators", action="store_true",
                              help="List all mutation categories and exit")
    mutation_parser.set_defaults(func=cmd_mutation)

    # passport subcommand (DTL Verified Design Passport)
    passport_parser = subparsers.add_parser(
        "passport",
        help="DTL Verified Design Passport: verification records for artifacts",
    )
    passport_parser.add_argument("--demo", action="store_true",
                                 help="Run passport demo with built-in RTL artifact")
    passport_parser.add_argument("--json", action="store_true",
                                 help="Output results as JSON")
    passport_parser.add_argument("--html", metavar="FILE", default=None,
                                 help="Generate HTML report to FILE")
    passport_parser.add_argument("--artifact", metavar="PATH", default=None,
                                 help="Path to artifact file for passport creation")
    passport_parser.add_argument("--create-passport", action="store_true",
                                 help="Create a new passport for the artifact")
    passport_parser.add_argument("--verify-passport", metavar="FILE", default=None,
                                 help="Verify an existing passport JSON file")
    passport_parser.add_argument("--export-badge", metavar="DIR", default=None,
                                 help="Export badge files to directory")
    passport_parser.add_argument("--replay", action="store_true",
                                 help="Build passport and replay it for stability check")
    passport_parser.set_defaults(func=cmd_passport)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the ChipGate CLI."""
    parser = build_parser()

    if argv is None:
        argv = sys.argv[1:]

    if "--list-rules" in argv:
        return cmd_list_rules(argparse.Namespace())

    # Subcommand-specific --demo handling
    if len(argv) >= 2 and argv[0] == "bench" and "--demo" in argv:
        parsed = parser.parse_args(argv)
        return cmd_bench(argparse.Namespace(
            demo=True,
            mode=getattr(parsed, "mode", "chipgate_only"),
            adapter=getattr(parsed, "adapter", None),
            html=getattr(parsed, "html", None),
            json=getattr(parsed, "json", False),
            evidence=getattr(parsed, "evidence", False),
            compare_modes=getattr(parsed, "compare_modes", False),
        ))

    if len(argv) >= 2 and argv[0] == "longevity" and "--demo" in argv:
        parsed = parser.parse_args(argv)
        return cmd_longevity(argparse.Namespace(
            demo=True,
            html=getattr(parsed, "html", None),
            json=getattr(parsed, "json", False),
        ))

    if len(argv) >= 2 and argv[0] == "synth" and "--demo" in argv:
        parsed = parser.parse_args(argv)
        return cmd_synth(argparse.Namespace(
            demo=True,
            path=None,
            html=getattr(parsed, "html", None),
            json=getattr(parsed, "json", False),
            rank=getattr(parsed, "rank", False),
        ))

    if len(argv) >= 2 and argv[0] == "silicon" and "--demo" in argv:
        parsed = parser.parse_args(argv)
        return cmd_silicon(argparse.Namespace(
            demo=True,
            path=None,
            html=getattr(parsed, "html", None),
            json=getattr(parsed, "json", False),
            toolchain_status=False,
            allow_unsafe=False,
        ))

    if len(argv) >= 2 and argv[0] == "fpga" and "--demo" in argv:
        parsed = parser.parse_args(argv)
        return cmd_fpga(argparse.Namespace(
            demo=True,
            path=None,
            html=getattr(parsed, "html", None),
            json=getattr(parsed, "json", False),
            toolchain_status=False,
            board_profile="generic_fpga",
            allow_unsafe=False,
        ))

    if len(argv) >= 2 and argv[0] == "tinytapeout" and "--demo" in argv:
        parsed = parser.parse_args(argv)
        return cmd_tinytapeout(argparse.Namespace(
            demo=True,
            path=None,
            html=getattr(parsed, "html", None),
            json=getattr(parsed, "json", False),
            generate_template=False,
            submission_check=False,
        ))

    if len(argv) >= 2 and argv[0] == "physical" and "--demo" in argv:
        parsed = parser.parse_args(argv)
        return cmd_physical(argparse.Namespace(
            demo=True,
            path=None,
            html=getattr(parsed, "html", None),
            json=getattr(parsed, "json", False),
            toolchain_status=False,
            parse_reports=None,
            allow_unsafe=False,
        ))

    if len(argv) >= 2 and argv[0] == "ci":
        parsed = parser.parse_args(argv)
        mode = "full" if "--full" in argv else "quick"
        return cmd_ci(argparse.Namespace(
            quick=mode == "quick",
            full=mode == "full",
            html=getattr(parsed, "html", None),
            json=getattr(parsed, "json", False),
            toolchain_status=getattr(parsed, "toolchain_status", False),
        ))

    # General --demo (only when no subcommand)
    known_commands = {"scan", "lint", "bench", "longevity", "synth", "silicon",
                      "fpga", "tinytapeout", "physical", "formal", "ci", "mutation",
                      "passport"}
    if "--demo" in argv and (not argv or argv[0] not in known_commands):
        return cmd_demo(argparse.Namespace())

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())