"""
FormalGate-Lite CLI command — Phase 12.

Usage:
    python -m chipgate formal --demo [--json] [--html FILE]
    python -m chipgate formal [path] [--json] [--html FILE]
    python -m chipgate formal --list-properties
    python -m chipgate formal --toolchain-status

Runs formal safety property checks on DTL-gated RTL designs.  When SBY
(SymbiYosys) is available, real bounded-model-checking is performed; when
it is missing, property generation and readiness analysis are still shown
but tool execution is gracefully skipped.

Does not guarantee silicon correctness, fabrication readiness, timing
signoff, physical safety, real power or real area.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import ci_toolchain, ci_matrix, ci_artifacts, ci_report
from . import formal_properties, formal_runner, formal_parser, formal_report, formal_artifacts

# Colours is defined in __main__.py — import it there.
# We re-import here for use inside this module's own helper functions.
from .__main__ import Colours


# ---------------------------------------------------------------------------
# Public disclaimer / limitation strings
# ---------------------------------------------------------------------------

FORMALATE_PUBLIC_WORDING = (
    "FormalGate-Lite runs bounded-model-checking style formal property checks. "
    "It does not guarantee hardware correctness, silicon readiness, physical safety, "
    "regulatory conformance or experimental validity."
)

FORMALATE_LIMITATION = (
    "FormalGate-Lite uses bounded model checking and may not exhaustively prove "
    "all properties. Absence of a counterexample does not guarantee correctness "
    "under all possible inputs and sequences."
)


# ---------------------------------------------------------------------------
# Helper — colour wrapper (same pattern as __main__._c)
# ---------------------------------------------------------------------------

def _c(code: str, text: str) -> str:
    """Apply colour code to text if stdout is a terminal."""
    if sys.stdout.isatty():
        return f"{code}{text}{Colours.RESET}"
    return text


# ---------------------------------------------------------------------------
# Helper — resolve benchmark directories relative to the package root
# ---------------------------------------------------------------------------

def _pkg_root() -> Path:
    """Return the chipgate package root directory."""
    return Path(__file__).resolve().parent


def _benchmark_dir(name: str) -> Path:
    """Return the path to a benchmark subdirectory, or Path("") if absent."""
    d = _pkg_root() / "benchmarks" / name
    return d if d.is_dir() else Path("")


# ---------------------------------------------------------------------------
# Helper — collect demo designs
# ---------------------------------------------------------------------------

def _collect_demo_designs() -> List[Path]:
    """Return Verilog files from benchmarks/formalgate_v0/designs/."""
    designs_dir = _benchmark_dir("formalgate_v0") / "designs"
    if not designs_dir.is_dir():
        return []
    designs: List[Path] = sorted(designs_dir.glob("*.v")) + sorted(designs_dir.glob("*.sv"))
    return designs


# ---------------------------------------------------------------------------
# Helper — collect fixture property files
# ---------------------------------------------------------------------------

def _collect_fixture_properties() -> List[Path]:
    """Return property files from benchmarks/formalate_v0/properties/."""
    props_dir = _benchmark_dir("formalate_v0") / "properties"
    if not props_dir.is_dir():
        return []
    return sorted(props_dir.glob("*"))


# ---------------------------------------------------------------------------
# Helper — generate default SBY configs and property files for demo designs
# ---------------------------------------------------------------------------

def _generate_demo_artifacts(
    designs: List[Path],
    output_dir: Path,
) -> List[str]:
    """Write generated SBY configs and property files for each demo design.

    Returns a list of written file paths.
    """
    written: List[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write the default properties file once
    props_text = formal_properties.generate_default_properties()
    props_path = output_dir / "default_properties.sv"
    props_path.write_text(props_text, encoding="utf-8")
    written.append(str(props_path))

    # Write an SBY config for each design
    for design in designs:
        rtl_text = design.read_text(encoding="utf-8", errors="replace")
        import re
        match = re.search(r"module\s+(\w+)", rtl_text)
        top_module = match.group(1) if match else "top"

        sby_content = formal_properties.generate_sby_config(
            rtl_path=str(design.name),
            top_module=top_module,
            properties=props_text,
        )
        sby_path = output_dir / f"{design.stem}.sby"
        sby_path.write_text(sby_content, encoding="utf-8")
        written.append(str(sby_path))

    return written


# ---------------------------------------------------------------------------
# Helper — run formal checks on a single design
# ---------------------------------------------------------------------------

def _run_formal_on_design(
    design_path: Path,
    toolchain: dict,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """Run formal property checks on a single design.

    Returns a dict with keys: design, design_path, properties, properties_passed,
    properties_failed, counterexamples, status, tool_available.
    """
    sby_available = toolchain.get("sby", {}).get("found", False)
    yosys_available = toolchain.get("yosys", {}).get("found", False)
    both_available = toolchain.get("both", False)

    # Readiness check (always performed)
    readiness = formal_properties.check_formal_readiness(str(design_path))

    property_results: List[Dict[str, Any]] = []
    counterexamples: List[Dict[str, Any]] = []
    props_passed = 0
    props_failed = 0

    if both_available:
        # Run real formal checks via SBY
        results = formal_runner.run_formal_checks(
            rtl_path=str(design_path),
            timeout_seconds=timeout_seconds,
        )
        for prop_name, fpr in results.items():
            status = "PASSED" if fpr.passed else "FAILED"
            details = ""
            if not fpr.passed and fpr.output:
                # Show first 200 chars of output
                details = fpr.output[:200]
            property_results.append({
                "property": prop_name,
                "status": status,
                "details": details,
            })
            if fpr.passed:
                props_passed += 1
            else:
                props_failed += 1

            # Parse counterexamples from failed output
            if not fpr.passed and fpr.output:
                cex_list = formal_parser.parse_counterexample(fpr.output)
                counterexamples.extend(cex_list)
    else:
        # Tool missing — generate simulated results from readiness analysis
        import re as _re
        props_text = formal_properties.generate_default_properties()
        for m in _re.finditer(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", props_text, _re.MULTILINE):
            prop_name = m.group(1)
            # Use readiness to determine simulated outcome
            if readiness.get("ready", False):
                property_results.append({
                    "property": prop_name,
                    "status": "SKIPPED_TOOL_MISSING",
                    "details": "SBY/Yosys not available — property ready but not checked",
                })
            else:
                property_results.append({
                    "property": prop_name,
                    "status": "SKIPPED_TOOL_MISSING",
                    "details": "Design not formally ready; SBY/Yosys not available",
                })

    # Determine overall design status
    if both_available:
        status = "FORMAL_PASS" if props_failed == 0 and props_passed > 0 else "FORMAL_FAIL"
    elif readiness.get("ready", False):
        status = "FORMAL_SKIPPED_TOOL_MISSING"
    else:
        status = "FORMAL_NOT_READY"

    return {
        "design": design_path.stem,
        "design_path": str(design_path),
        "properties": property_results,
        "properties_passed": props_passed,
        "properties_failed": props_failed,
        "counterexamples": counterexamples,
        "status": status,
        "tool_available": both_available,
        "readiness": readiness,
    }


# ---------------------------------------------------------------------------
# Helper — build the aggregate result dict
# ---------------------------------------------------------------------------

def _build_result_dict(
    mode: str,
    toolchain_status: dict,
    design_results: List[Dict[str, Any]],
    generated_files: List[str],
) -> Dict[str, Any]:
    """Assemble the full FormalGate-Lite result dict."""
    from datetime import datetime, timezone

    all_properties: List[Dict[str, Any]] = []
    all_counterexamples: List[Dict[str, Any]] = []
    all_designs: List[Dict[str, Any]] = []
    total_passed = 0
    total_failed = 0

    for dr in design_results:
        all_properties.extend(dr.get("properties", []))
        all_counterexamples.extend(dr.get("counterexamples", []))
        all_designs.append({
            "design": dr.get("design", ""),
            "status": dr.get("status", ""),
            "properties_passed": dr.get("properties_passed", 0),
            "properties_failed": dr.get("properties_failed", 0),
            "counterexample": (
                all_counterexamples[-1].get("line", "") if all_counterexamples else ""
            ),
        })
        total_passed += dr.get("properties_passed", 0)
        total_failed += dr.get("properties_failed", 0)

    # Overall status
    any_fail = total_failed > 0
    any_pass = total_passed > 0
    any_ready = any(d.get("status") != "FORMAL_NOT_READY" for d in design_results)

    if any_fail:
        overall_status = "FORMAL_FAIL"
    elif any_pass:
        overall_status = "FORMAL_PASS"
    elif any_ready:
        overall_status = "FORMAL_SKIPPED_TOOL_MISSING"
    else:
        overall_status = "FORMAL_NOT_READY"

    # Safety precheck
    safety_passed = all(
        dr.get("readiness", {}).get("ready", False) for dr in design_results
    ) if design_results else False
    safety_issues: List[str] = []
    for dr in design_results:
        for issue in dr.get("readiness", {}).get("issues", []):
            safety_issues.append(f"{dr.get('design', '')}: {issue}")

    # Flatten toolchain status into the expected format for HTML
    tc_flat: Dict[str, Dict[str, Any]] = {}
    for name, info in toolchain_status.items():
        tc_flat[name] = {
            "found": info.get("found", False),
            "path": info.get("path", ""),
            "version": info.get("version", ""),
        }

    return {
        "overall_status": overall_status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "toolchain_status": tc_flat,
        "hygiene": {
            "safety_precheck_passed": safety_passed,
            "summary": (
                "All designs are formally ready." if safety_passed
                else "; ".join(safety_issues) if safety_issues
                else "No designs checked."
            ),
        },
        "stages": [],
        "properties": all_properties,
        "counterexamples": all_counterexamples,
        "designs": all_designs,
        "properties_total": len(all_properties),
        "properties_passed": total_passed,
        "properties_failed": total_failed,
        "generated_files": generated_files,
        "public_wording": FORMALATE_PUBLIC_WORDING,
        "limitation": FORMALATE_LIMITATION,
    }


# ---------------------------------------------------------------------------
# Helper — format toolchain status (formal-specific)
# ---------------------------------------------------------------------------

def _format_formal_toolchain_status(toolchain: dict) -> str:
    """Format formal toolchain status for terminal output."""
    lines = []
    lines.append(_c(Colours.BOLD, "FormalGate-Lite — Toolchain Status"))
    lines.append("")

    for name in ("sby", "yosys"):
        info = toolchain.get(name, {})
        if info.get("found"):
            ver = info.get("version", "")
            ver_str = f" ({ver})" if ver else ""
            lines.append(
                f"  {_c(Colours.GREEN, '[FOUND]')} {name}: {info.get('path', '')}{ver_str}"
            )
        else:
            lines.append(f"  {_c(Colours.YELLOW, '[MISSING]')} {name}")

    both = toolchain.get("both", False)
    if both:
        lines.append(f"\n  {_c(Colours.GREEN, 'SBY + Yosys: READY for formal verification')}")
    else:
        lines.append(f"\n  {_c(Colours.YELLOW, 'SBY + Yosys: NOT READY — formal checks will be skipped')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

def cmd_formal(args) -> int:
    """Run FormalGate-Lite formal safety property checks."""
    from . import __version__

    do_json = getattr(args, "json", False)
    html_path = getattr(args, "html", None)
    demo = getattr(args, "demo", False)
    show_toolchain = getattr(args, "toolchain_status", False)
    list_props = getattr(args, "list_properties", False)
    bench_path = getattr(args, "path", None)

    # --toolchain-status: show and exit
    if show_toolchain:
        # Use formal_runner's dedicated checker for SBY/Yosys
        toolchain = formal_runner.check_formal_toolchain()
        if do_json:
            print(json.dumps(toolchain, indent=2, sort_keys=True))
        else:
            print(_format_formal_toolchain_status(toolchain))
        return 0

    # --list-properties: list available formal properties and exit
    if list_props:
        props_text = formal_properties.generate_default_properties()
        print(_c(Colours.BOLD, "FormalGate-Lite — Available Formal Safety Properties"))
        print(_c(Colours.DIM, f"ChipGate v{__version__}\n"))
        for line in props_text.strip().splitlines():
            if line.startswith("#"):
                print(_c(Colours.DIM, f"  {line}"))
            elif ":" in line and not line.startswith(" "):
                name, body = line.split(":", 1)
                print(f"  {_c(Colours.BOLD, name.strip())}:{body.strip()}")
            else:
                print(f"  {line}")
        return 0

    # Determine toolchain availability
    toolchain = formal_runner.check_formal_toolchain()

    # Collect designs
    if demo:
        designs = _collect_demo_designs()
        if not designs:
            # Fallback: use siliconbench designs if formalgate_v0 doesn't exist
            fallback_dir = _benchmark_dir("siliconbench_v0") / "designs"
            if fallback_dir.is_dir():
                designs = sorted(fallback_dir.glob("*.v")) + sorted(fallback_dir.glob("*.sv"))
        if not designs:
            print(_c(Colours.RED, "No demo designs found."))
            return 1
    elif bench_path:
        bench_p = Path(bench_path)
        if not bench_p.is_dir():
            print(_c(Colours.RED, f"Benchmark directory not found: {bench_path}"))
            return 1
        designs = sorted(bench_p.glob("*.v")) + sorted(bench_p.glob("*.sv"))
        if not designs:
            print(_c(Colours.RED, f"No Verilog files found in: {bench_path}"))
            return 1
    else:
        print(_c(Colours.RED, "No design path specified. Use --demo or provide a path."))
        return 1

    # Collect fixture properties (if formalate_v0 exists)
    fixture_props = _collect_fixture_properties()

    # Generate demo artifacts (SBY configs + property files)
    generated_files: List[str] = []
    if demo:
        artifact_dir = _pkg_root() / "benchmarks" / "formalgate_v0" / "generated"
        generated_files = _generate_demo_artifacts(designs, artifact_dir)
        if generated_files and not do_json:
            print(_c(Colours.DIM, f"Generated {len(generated_files)} artifact(s):"))
            for gf in generated_files:
                print(_c(Colours.DIM, f"  {gf}"))
            print()

    # Run formal checks on each design
    design_results: List[Dict[str, Any]] = []
    for design_path in designs:
        if not do_json:
            print(f"  Checking {_c(Colours.BOLD, design_path.stem)}...")
        result = _run_formal_on_design(design_path, toolchain)
        design_results.append(result)
        if not do_json:
            status = result["status"]
            pp = result["properties_passed"]
            pf = result["properties_failed"]
            if "PASS" in status:
                clr = Colours.GREEN
            elif "FAIL" in status:
                clr = Colours.RED
            else:
                clr = Colours.YELLOW
            print(f"    {_c(clr, f'[{status}]')} {pp} passed, {pf} failed")

    # Build the aggregate result
    result_dict = _build_result_dict(
        mode="demo" if demo else "custom",
        toolchain_status=toolchain,
        design_results=design_results,
        generated_files=generated_files,
    )

    # --json output
    if do_json:
        # Also create evidence via formal_artifacts
        if design_results:
            first_result = design_results[0]
            evidence = formal_artifacts.create_formal_evidence(
                design_path=first_result.get("design_path", ""),
                formal_result=type("obj", (), {
                    "passed": result_dict["properties_failed"] == 0,
                    "output": "",
                })(),
                property_results=[
                    r if isinstance(r, dict) else r.to_dict()
                    for d in design_results
                    for r in d.get("properties", [])
                ],
                toolchain_status=toolchain,
            )
            result_dict["evidence"] = evidence
        print(json.dumps(result_dict, indent=2, default=str))
        return 0 if result_dict["properties_failed"] == 0 else 1

    # Terminal output (non-JSON)
    print()
    print(_c(Colours.BOLD, "FormalGate-Lite"))
    print(_c(Colours.DIM, f"ChipGate v{__version__} | {result_dict['timestamp_utc']}"))
    print()

    # Toolchain summary
    sby_found = toolchain.get("sby", {}).get("found", False)
    yosys_found = toolchain.get("yosys", {}).get("found", False)
    both = toolchain.get("both", False)
    print(f"  Toolchain (SBY + Yosys): {'READY' if both else _c(Colours.YELLOW, 'NOT READY')}")
    print(f"  Designs tested:          {len(designs)}")
    print(f"  Properties checked:      {result_dict['properties_total']}")
    print(f"  Properties passed:       {_c(Colours.GREEN, str(result_dict['properties_passed']))}")
    print(f"  Properties failed:       {_c(Colours.RED, str(result_dict['properties_failed']))}")
    print(f"  Counterexamples found:   {len(result_dict['counterexamples'])}")
    print()

    # Overall status
    overall = result_dict["overall_status"]
    if "PASS" in overall:
        print(f"  Overall: {_c(Colours.GREEN, overall)}")
    elif "FAIL" in overall:
        print(f"  Overall: {_c(Colours.RED, overall)}")
    else:
        print(f"  Overall: {_c(Colours.YELLOW, overall)}")
    print()

    # Design summary table
    if design_results:
        print(_c(Colours.BOLD, "  Design Results:"))
        print(f"  {'Design':<30s} {'Status':<28s} {'Pass':>5s} {'Fail':>5s}")
        print(f"  {'-' * 72}")
        for dr in design_results:
            status = dr["status"]
            if "PASS" in status:
                clr = Colours.GREEN
            elif "FAIL" in status:
                clr = Colours.RED
            else:
                clr = Colours.YELLOW
            print(
                f"  {dr['design']:<30s} {_c(clr, status):<28s} "
                f"{dr['properties_passed']:>5d} {dr['properties_failed']:>5d}"
            )
        print()

    # Generated files
    if generated_files:
        print(_c(Colours.BOLD, "  Generated Artifacts:"))
        for gf in generated_files:
            print(f"    {gf}")
        print()

    # Disclaimer
    print(_c(Colours.DIM, FORMALATE_PUBLIC_WORDING))
    print(_c(Colours.DIM, FORMALATE_LIMITATION))

    # HTML report
    if html_path:
        html_content = formal_report.generate_formal_html(result_dict)
        Path(html_path).write_text(html_content, encoding="utf-8")
        print(_c(Colours.GREEN, f"\nFormalGate-Lite HTML report saved: {html_path}"))

    return 0 if result_dict["properties_failed"] == 0 else 1


# ---------------------------------------------------------------------------
# Subparser builder (called from __main__.build_parser)
# ---------------------------------------------------------------------------

def add_formal_subparser(subparsers) -> None:
    """Add the 'formal' subparser to an argparse subparsers group.

    This is called from ``__main__.build_parser()`` to register the
    FormalGate-Lite command alongside the other CLI subcommands.
    """
    formal_parser = subparsers.add_parser(
        "formal",
        help="Run FormalGate-Lite formal safety property checks",
    )
    formal_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to a formal benchmark directory (optional)",
    )
    formal_parser.add_argument("--demo", action="store_true",
                               help="Run with built-in demo design and fixture properties")
    formal_parser.add_argument("--json", action="store_true",
                               help="Output results as JSON")
    formal_parser.add_argument("--html", metavar="FILE", default=None,
                               help="Generate HTML report to FILE")
    formal_parser.add_argument("--list-properties", action="store_true",
                               help="List available formal properties")
    formal_parser.add_argument("--toolchain-status", action="store_true",
                               help="Show which formal tools are available")
    formal_parser.set_defaults(func=cmd_formal)