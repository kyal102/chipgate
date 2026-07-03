"""
ChipGate OpenLanePhysicalBench — Main orchestrator.

Checks whether the tiny public-safe DTL gate design from TinyTapeoutPrep
can survive a more physical ASIC-style flow using OpenLane/OpenROAD-style
readiness checks.

Stages:
  1. Preflight safety check (ChipGate safety scan, TT prep, private leak)
  2. OpenLane/OpenROAD toolchain status
  3. Physical-flow readiness config validation
  4. Optional OpenLane/OpenROAD run (gracefully skipped if tools missing)
  5. Report parsing (DRC, LVS, timing, area, routing)
  6. GDS artifact hashing
  7. Evidence pack generation

Does not guarantee silicon correctness, fabrication readiness, timing signoff,
real power, real area, physical durability, regulatory conformance or
safety-critical deployment.
"""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import __version__, statuses as st
from .drc_lvs_parser import parse_drc_report, parse_lvs_report
from .timing_report_parser import parse_timing_report, parse_area_stats
from .openroad_reports import parse_fixtures_directory
from .gds_artifacts import hash_all_artifacts
from .physical_score import PhysicalMetrics, compute_metrics_from_results


# ── Toolchain binaries to check ──────────────────────────────────────────────

_TOOLCHAIN = [
    ("OpenLane", ["openlane"]),
    ("OpenROAD", ["openroad"]),
    ("Yosys", ["yosys"]),
    ("Magic", ["magic"]),
    ("Netgen", ["netgen"]),
    ("KLayout", ["klayout"]),
    ("STA", ["sta", "opensta"]),
]


# ── Private name detection (re-uses TT pattern) ──────────────────────────────

_PRIVATE_PATTERNS: List[re.Pattern] = [
    re.compile(r"j\x61rvi3", re.IGNORECASE),
    re.compile(r"proprietary", re.IGNORECASE),
    re.compile(r"confidential", re.IGNORECASE),
    re.compile(r"PRIVATE_DTL", re.IGNORECASE),
    re.compile(r"secret[_-]?key", re.IGNORECASE),
    re.compile(r"internal[_-]?only", re.IGNORECASE),
    re.compile(r"not[_-]?for[_-]?public", re.IGNORECASE),
]


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class PhysicalDesignResult:
    """Per-design result for OpenLanePhysicalBench."""
    design_id: str = ""
    top_module: str = ""
    safety_status: str = ""
    openlane_config_status: str = ""
    openroad_run_status: str = ""
    drc_status: str = ""
    lvs_status: str = ""
    timing_status: str = ""
    gds_status: str = ""
    overall_status: str = ""
    drc_result: Dict[str, Any] = field(default_factory=dict)
    lvs_result: Dict[str, Any] = field(default_factory=dict)
    timing_result: Dict[str, Any] = field(default_factory=dict)
    area_stats: Dict[str, Any] = field(default_factory=dict)
    evidence_record: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "design_id": self.design_id,
            "top_module": self.top_module,
            "safety_status": self.safety_status,
            "openlane_config_status": self.openlane_config_status,
            "openroad_run_status": self.openroad_run_status,
            "drc_status": self.drc_status,
            "lvs_status": self.lvs_status,
            "timing_status": self.timing_status,
            "gds_status": self.gds_status,
            "overall_status": self.overall_status,
            "drc_result": self.drc_result,
            "lvs_result": self.lvs_result,
            "timing_result": self.timing_result,
            "area_stats": self.area_stats,
            "evidence_record": self.evidence_record,
        }


@dataclass
class OpenLanePhysicalBenchResult:
    """Top-level result for OpenLanePhysicalBench."""
    benchmark_name: str = "OpenLanePhysicalBench"
    benchmark_version: str = __version__
    timestamp_utc: str = ""
    overall_status: str = st.PHYSICAL_BENCH_PASS
    design_results: List[Dict[str, Any]] = field(default_factory=list)
    toolchain_report: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    manual_review_items: List[str] = field(default_factory=list)
    public_wording: str = ""
    limitation: str = ""
    artifacts_dir: str = ""

    def to_dict(self) -> dict:
        return {
            "benchmark_name": self.benchmark_name,
            "benchmark_version": self.benchmark_version,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "design_results": self.design_results,
            "toolchain_report": self.toolchain_report,
            "metrics": self.metrics,
            "manual_review_items": self.manual_review_items,
            "public_wording": self.public_wording,
            "limitation": self.limitation,
            "artifacts_dir": self.artifacts_dir,
        }


# ── Public API ───────────────────────────────────────────────────────────────

def run_physical_bench(
    demo: bool = True,
    benchmark_path: Optional[str] = None,
    allow_unsafe: bool = False,
    parse_reports_path: Optional[str] = None,
) -> OpenLanePhysicalBenchResult:
    """Run the full OpenLanePhysicalBench pipeline.

    Args:
        demo: If True, use built-in demo designs and fixtures.
        benchmark_path: Path to benchmark directory with designs/, configs/, fixtures/.
        allow_unsafe: If True, allow unsafe designs to proceed (for testing).
        parse_reports_path: If set, only parse reports from this fixtures dir.

    Returns:
        OpenLanePhysicalBenchResult with all results.
    """
    result = OpenLanePhysicalBenchResult()
    result.timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result.public_wording = st.PHYSICAL_PUBLIC_WORDING
    result.limitation = st.PHYSICAL_LIMITATION

    # Check toolchain
    result.toolchain_report = check_toolchain_status()

    # If parse_reports_path is given, just parse reports and return
    if parse_reports_path:
        parsed = parse_fixtures_directory(parse_reports_path)
        _attach_parsed_to_result(result, parsed)
        result.overall_status = st.PHYSICAL_BENCH_PASS
        return result

    # Determine source paths
    if demo:
        base = Path(__file__).parent.parent / "benchmarks" / "openlanephysical_v0"
    elif benchmark_path:
        base = Path(benchmark_path)
    else:
        base = Path(__file__).parent.parent / "benchmarks" / "openlanephysical_v0"

    designs_dir = base / "designs"
    configs_dir = base / "configs"
    fixtures_dir = base / "fixtures"

    # Create output directory
    if demo:
        out = Path(tempfile.mkdtemp(prefix="chipgate_physical_"))
    elif benchmark_path:
        out = Path(benchmark_path)
    else:
        out = Path(tempfile.mkdtemp(prefix="chipgate_physical_"))
    out.mkdir(parents=True, exist_ok=True)
    result.artifacts_dir = str(out)

    # Collect designs
    designs = _collect_designs(designs_dir, demo)
    configs = _collect_configs(configs_dir, demo)

    # Process each design
    for design_path, design_id, verilog_content in designs:
        dr = _process_design(
            design_id=design_id,
            verilog_content=verilog_content,
            config_content=_get_config_for_design(design_id, configs),
            fixtures_dir=str(fixtures_dir),
            allow_unsafe=allow_unsafe,
        )
        result.design_results.append(dr.to_dict())

    # Compute metrics
    metrics = compute_metrics_from_results(
        design_results=result.design_results,
        toolchain_report=result.toolchain_report,
        evidence_packs=sum(
            1 for d in result.design_results
            if d.get("evidence_record", {}).get("created", False)
        ),
    )
    result.metrics = metrics.to_dict()

    # Collect manual review items
    for d in result.design_results:
        ev = d.get("evidence_record", {})
        for item in ev.get("manual_review_items", []):
            if item not in result.manual_review_items:
                result.manual_review_items.append(item)

    # Overall status
    has_fail = any(
        d.get("overall_status") in (st.PHYSICAL_BENCH_FAIL, st.UNSAFE_BLOCKED)
        for d in result.design_results
    )
    result.overall_status = (
        st.PHYSICAL_BENCH_FAIL if has_fail else st.PHYSICAL_BENCH_PASS
    )

    # Save evidence JSON
    evidence_path = out / "physical_evidence.json"
    evidence_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    return result


def check_toolchain_status() -> Dict[str, Dict[str, Any]]:
    """Check availability of OpenLane/OpenROAD toolchain tools.

    Returns a dict mapping tool name to {"found": bool, "path": str,
    "version": str, "note": str}.
    """
    report = {}
    for name, binaries in _TOOLCHAIN:
        found_exe = None
        for bin_name in binaries:
            exe = shutil.which(bin_name)
            if exe is not None:
                found_exe = exe
                break

        if found_exe:
            version = _get_version(found_exe)
            report[name] = {
                "found": True,
                "path": found_exe,
                "version": version,
            }
        else:
            report[name] = {
                "found": False,
                "path": "",
                "version": "",
                "note": "not found in PATH",
            }
    return report


# ── Internal helpers ─────────────────────────────────────────────────────────

def _get_version(exe_path: str) -> str:
    """Get version string from a tool binary."""
    try:
        result = subprocess.run(
            [exe_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0][:120]
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _collect_designs(
    designs_dir: Path, demo: bool,
) -> List[Tuple[Path, str, str]]:
    """Collect design files from the designs directory.

    Returns list of (path, design_id, verilog_content).
    """
    designs = []
    if not designs_dir.is_dir():
        if demo:
            return _demo_designs()
        return designs

    for f in sorted(designs_dir.iterdir()):
        if f.suffix in (".v", ".sv") and f.is_file():
            content = f.read_text(encoding="utf-8", errors="replace")
            designs.append((f, f.stem, content))
    return designs


def _demo_designs() -> List[Tuple[Path, str, str]]:
    """Return built-in demo designs as (path, id, content) tuples."""
    designs = []

    # Design 1: Safe physical DTL gate
    safe_v = _DEMO_SAFE_DTL_GATE_PHYSICAL
    designs.append((Path("tiny_dtl_gate_physical.v"),
                     "tiny_dtl_gate_physical", safe_v))

    # Design 2: Unsafe direct output
    unsafe_v = _DEMO_UNSAFE_DIRECT_OUTPUT_PHYSICAL
    designs.append((Path("unsafe_direct_output_physical.v"),
                     "unsafe_direct_output_physical", unsafe_v))

    return designs


def _collect_configs(configs_dir: Path, demo: bool) -> Dict[str, str]:
    """Collect config files from configs directory.

    Returns dict of design_id -> config_content.
    """
    configs = {}
    if not configs_dir.is_dir():
        if demo:
            configs["tiny_dtl_gate_physical"] = _DEMO_OPENLANE_CONFIG
            configs["bad_config"] = _DEMO_BAD_OPENLANE_CONFIG
        return configs

    for f in sorted(configs_dir.iterdir()):
        if f.suffix in (".json", ".tcl", ".config", ".yaml"):
            content = f.read_text(encoding="utf-8", errors="replace")
            configs[f.stem] = content
    return configs


def _get_config_for_design(design_id: str, configs: Dict[str, str]) -> str:
    """Get config content for a design by ID or prefix match."""
    # Exact match
    if design_id in configs:
        return configs[design_id]
    # Prefix match
    for cfg_id, content in configs.items():
        if design_id.startswith(cfg_id) or cfg_id.startswith(design_id.replace("_physical", "")):
            return content
    return ""


def _process_design(
    design_id: str,
    verilog_content: str,
    config_content: str,
    fixtures_dir: str,
    allow_unsafe: bool,
) -> PhysicalDesignResult:
    """Process a single design through all physical flow stages."""
    dr = PhysicalDesignResult(design_id=design_id)

    # Extract top module name
    mod_match = re.search(r"module\s+(\w+)", verilog_content)
    dr.top_module = mod_match.group(1) if mod_match else design_id

    # ── Stage 1: Preflight safety check ──────────────────────────────────
    safety_ok, safety_status = _preflight_safety(verilog_content)
    dr.safety_status = safety_status

    if not safety_ok and not allow_unsafe:
        dr.overall_status = st.PHYSICAL_BENCH_FAIL
        dr.openlane_config_status = st.UNSAFE_BLOCKED
        dr.drc_status = st.UNSAFE_BLOCKED
        dr.lvs_status = st.UNSAFE_BLOCKED
        dr.timing_status = st.UNSAFE_BLOCKED
        dr.gds_status = st.UNSAFE_BLOCKED
        dr.evidence_record = _build_evidence_record(
            dr, verilog_content, config_content, fixtures_dir,
            manual_extra=["Design blocked: failed safety preflight"],
        )
        return dr

    # ── Stage 2: OpenLane config check ───────────────────────────────────
    config_ok, config_issues = _check_openlane_config(
        verilog_content, config_content, dr.top_module
    )
    if config_ok:
        dr.openlane_config_status = st.OPENLANE_CONFIG_PASS
    else:
        dr.openlane_config_status = st.OPENLANE_CONFIG_FAIL

    # ── Stage 3: OpenROAD run (gracefully skipped if tools missing) ───────
    or_status = _check_openroad_run()
    dr.openroad_run_status = or_status

    # ── Stage 4: Parse fixture reports ───────────────────────────────────
    drc_result, lvs_result, timing_result, area_result = (
        _parse_fixture_reports(fixtures_dir, design_id)
    )
    dr.drc_result = drc_result
    dr.lvs_result = lvs_result
    dr.timing_result = timing_result
    dr.area_stats = area_result

    # Classify DRC
    if not drc_result:
        dr.drc_status = st.DRC_SKIPPED_NO_REPORT
    elif drc_result.get("clean", False):
        dr.drc_status = st.DRC_CLEAN
    else:
        dr.drc_status = st.DRC_VIOLATIONS_FOUND

    # Classify LVS
    if not lvs_result:
        dr.lvs_status = st.LVS_SKIPPED_NO_REPORT
    elif lvs_result.get("clean", False):
        dr.lvs_status = st.LVS_CLEAN
    else:
        dr.lvs_status = st.LVS_MISMATCH_FOUND

    # Classify timing
    if not timing_result:
        dr.timing_status = st.TIMING_REPORT_SKIPPED
    elif timing_result.get("pass_status", False):
        dr.timing_status = st.TIMING_REPORT_PASS
    else:
        dr.timing_status = st.TIMING_REPORT_FAIL

    # ── Stage 5: GDS artifact hashing ────────────────────────────────────
    gds_path = str(Path(fixtures_dir) / f"{design_id}.gds") if fixtures_dir else ""
    gds_hash = hash_all_artifacts(
        rtl_content=verilog_content,
        wrapper_content="",
        config_content=config_content,
        pinout_content="",
        report_fixtures={
            "drc": json.dumps(drc_result) if drc_result else "",
            "lvs": json.dumps(lvs_result) if lvs_result else "",
            "timing": json.dumps(timing_result) if timing_result else "",
        },
        replay_command=f"python -m chipgate physical {fixtures_dir} --json",
        gds_path=gds_path if Path(gds_path).exists() else None,
    )

    if gds_hash.gds_found:
        dr.gds_status = st.GDS_HASH_CREATED
    else:
        dr.gds_status = st.GDS_MISSING

    # ── Build evidence record ────────────────────────────────────────────
    manual_extra = list(config_issues)
    if dr.openroad_run_status == st.OPENROAD_SKIPPED_TOOL_MISSING:
        manual_extra.append("OpenROAD run skipped: tool not installed")
    if dr.drc_status == st.DRC_SKIPPED_NO_REPORT:
        manual_extra.append("DRC report not available: run official OpenLane flow for DRC results")
    if dr.lvs_status == st.LVS_SKIPPED_NO_REPORT:
        manual_extra.append("LVS report not available: run official OpenLane flow for LVS results")
    if dr.timing_status == st.TIMING_REPORT_SKIPPED:
        manual_extra.append("Timing report not available: run OpenROAD STA for timing results")
    if not gds_hash.gds_found:
        manual_extra.append("GDS file not available: run official OpenLane flow for GDS output")
    if manual_extra:
        manual_extra.insert(0, st.NEEDS_OFFICIAL_OPENLANE_RUN)

    dr.evidence_record = _build_evidence_record(
        dr, verilog_content, config_content, fixtures_dir,
        gds_hash=gds_hash, manual_extra=manual_extra,
    )

    # ── Overall status ───────────────────────────────────────────────────
    fail_statuses = {
        st.PHYSICAL_BENCH_FAIL, st.UNSAFE_BLOCKED,
        st.OPENLANE_CONFIG_FAIL, st.DRC_VIOLATIONS_FOUND,
        st.LVS_MISMATCH_FOUND, st.TIMING_REPORT_FAIL,
    }
    has_fail = dr.safety_status in fail_statuses or dr.openlane_config_status in fail_statuses
    dr.overall_status = st.PHYSICAL_BENCH_FAIL if has_fail else st.PHYSICAL_BENCH_PASS

    return dr


def _preflight_safety(verilog: str) -> Tuple[bool, str]:
    """Run preflight safety checks on Verilog content.

    Checks:
    - No private name leakage
    - Safety signals present (kill_switch, timeout, verifier_ok, etc.)
    - No unguarded actuator output

    Returns (passed, status_string).
    """
    # Check for private names
    for pattern in _PRIVATE_PATTERNS:
        if pattern.search(verilog):
            return False, st.TT_PRIVATE_LEAK_DETECTED

    # Check for safety signals
    required_safety = ["kill_switch", "timeout", "reset", "verifier_ok", "policy_ok"]
    found = sum(1 for sig in required_safety if sig in verilog)
    if found < 3:
        return False, st.TT_SAFETY_PROPERTY_MISSING

    # Check for actuator gating
    if "actuator_enable" in verilog:
        has_kill = "kill_switch" in verilog
        if not has_kill:
            return False, st.UNGATED_OUTPUT

    return True, st.SAFETY_GATE_PRESENT


def _check_openlane_config(
    verilog: str, config_content: str, top_module: str,
) -> Tuple[bool, List[str]]:
    """Validate OpenLane-style config readiness.

    Checks:
    - Top module exists
    - Verilog source exists (non-empty)
    - Config is valid JSON or TCL
    - Clock/reset documented
    - No private paths in config
    - No private names in config
    - Config is non-empty and reproducible

    Returns (passed, list_of_issues).
    """
    issues = []

    if not top_module:
        issues.append("Top module name not found in Verilog")

    if not verilog.strip():
        issues.append("Verilog source is empty")

    if not config_content.strip():
        issues.append("OpenLane config is empty")
    else:
        # Check for private paths
        for pattern in _PRIVATE_PATTERNS:
            if pattern.search(config_content):
                issues.append(f"Private name detected in config: {pattern.pattern}")
        # Check for private paths (absolute paths to private dirs)
        if re.search(r"/home/.*?/private|/opt/.*?/internal", config_content):
            issues.append("Private path detected in config")

    # Check clock/reset documented
    if not verilog.strip():
        pass  # already caught above
    else:
        has_clk = "clk" in verilog.lower() or "clock" in verilog.lower()
        if not has_clk:
            issues.append("Clock signal not documented in design")

    return len(issues) == 0, issues


def _check_openroad_run() -> str:
    """Check if OpenROAD is available for a dry-run.

    Returns OPENROAD_RUN_PASS if tool found, OPENROAD_SKIPPED_TOOL_MISSING otherwise.
    """
    exe = shutil.which("openroad")
    if exe:
        return st.OPENROAD_RUN_PASS
    return st.OPENROAD_SKIPPED_TOOL_MISSING


def _parse_fixture_reports(
    fixtures_dir: str, design_id: str,
) -> Tuple[Dict, Dict, Dict, Dict]:
    """Parse fixture reports for a design.

    Returns (drc_result, lvs_result, timing_result, area_result) as dicts.
    """
    fix = Path(fixtures_dir)
    drc_result = {}
    lvs_result = {}
    timing_result = {}
    area_result = {}

    if not fix.is_dir():
        return drc_result, lvs_result, timing_result, area_result

    # Try to find and parse DRC report
    drc_files = sorted(fix.glob("drc_*"))
    if drc_files:
        try:
            text = drc_files[0].read_text(encoding="utf-8", errors="replace")
            drc_result = parse_drc_report(text, str(drc_files[0])).to_dict()
        except Exception:
            drc_result = {"clean": None, "parser_note": "parse_error", "violation_count": 0}

    # Try to find and parse LVS report
    lvs_files = sorted(fix.glob("lvs_*"))
    if lvs_files:
        try:
            text = lvs_files[0].read_text(encoding="utf-8", errors="replace")
            lvs_result = parse_lvs_report(text, str(lvs_files[0])).to_dict()
        except Exception:
            lvs_result = {"clean": None, "parser_note": "parse_error", "mismatch_count": 0}

    # Try to find and parse timing report
    timing_files = sorted(fix.glob("timing_*"))
    if timing_files:
        try:
            text = timing_files[0].read_text(encoding="utf-8", errors="replace")
            timing_result = parse_timing_report(text, str(timing_files[0])).to_dict()
        except Exception:
            timing_result = {"pass_status": None, "parser_note": "parse_error", "worst_negative_slack": 0.0}

    # Try to find and parse area stats
    area_files = sorted(fix.glob("area_*"))
    if area_files:
        try:
            text = area_files[0].read_text(encoding="utf-8", errors="replace")
            area_result = parse_area_stats(text, str(area_files[0]))
        except Exception:
            area_result = {"parser_note": "parse_error"}

    return drc_result, lvs_result, timing_result, area_result


def _build_evidence_record(
    dr: PhysicalDesignResult,
    verilog_content: str,
    config_content: str,
    fixtures_dir: str,
    gds_hash: Optional[Any] = None,
    manual_extra: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build an evidence record for a design."""
    import json as _json

    artifact_hashes = []
    if gds_hash:
        artifact_hashes = [a.to_dict() for a in gds_hash.artifact_hashes]

    manual_items = list(manual_extra) if manual_extra else []

    # Add NEEDS_MANUAL_REVIEW if there are manual items
    if manual_items and st.NEEDS_MANUAL_REVIEW not in manual_items:
        manual_items.append(st.NEEDS_MANUAL_REVIEW)

    record = {
        "benchmark_name": "OpenLanePhysicalBench",
        "benchmark_version": __version__,
        "design_id": dr.design_id,
        "top_module_name": dr.top_module,
        "rtl_hash": hashlib.sha256(verilog_content.encode("utf-8")).hexdigest()[:32],
        "config_hash": (hashlib.sha256(config_content.encode("utf-8")).hexdigest()[:32]
                        if config_content else ""),
        "chipgate_safety_result": dr.safety_status,
        "openlane_config_result": dr.openlane_config_status,
        "openroad_result": dr.openroad_run_status,
        "drc_result": dr.drc_status,
        "lvs_result": dr.lvs_status,
        "timing_result": dr.timing_status,
        "gds_result": dr.gds_status,
        "artifact_hashes": artifact_hashes,
        "artifact_hash_count": len(artifact_hashes),
        "manual_review_items": manual_items,
        "replay_command": f"python -m chipgate physical {fixtures_dir} --json",
        "public_wording": st.PHYSICAL_PUBLIC_WORDING,
    }

    # Certificate hash
    record["certificate_hash"] = hashlib.sha256(
        _json.dumps(record, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:32]

    record["created"] = True
    return record


# ── Demo design Verilog sources ──────────────────────────────────────────────

_DEMO_SAFE_DTL_GATE_PHYSICAL = """\
// ChipGate TinyTapeoutPrep - Physical Flow DTL Gate
// Public-safe minimal DTL safety gate for OpenLane physical readiness.
// This is NOT a real tapeout design.

module tiny_dtl_gate_physical (
    input  wire clk,
    input  wire rst_n,
    input  wire ai_output,
    input  wire verifier_ok,
    input  wire policy_ok,
    input  wire sensor_ok,
    input  wire timeout,
    input  wire kill_switch,
    input  wire reset,
    output wire actuator_enable,
    output wire status_out,
    output wire diag_0,
    output wire diag_1,
    output wire diag_2
);

    // DTL safety gate: all conditions must be met
    wire gate = ai_output & verifier_ok & policy_ok & sensor_ok;
    wire safe = ~timeout & ~kill_switch & ~reset & rst_n;

    assign actuator_enable = gate & safe;

    // Diagnostic outputs
    assign status_out = safe;
    assign diag_0 = gate;
    assign diag_1 = verifier_ok & policy_ok;
    assign diag_2 = sensor_ok & ~timeout;

endmodule
"""

_DEMO_UNSAFE_DIRECT_OUTPUT_PHYSICAL = """\
// UNSAFE design for testing - direct output with no safety gating
module unsafe_direct_output_physical (
    input  wire clk,
    input  wire rst_n,
    input  wire ai_output,
    output wire actuator_enable
);

    // UNSAFE: direct output, no safety gating
    assign actuator_enable = ai_output;

endmodule
"""

_DEMO_OPENLANE_CONFIG = """\
{
    "DESIGN_NAME": "tiny_dtl_gate_physical",
    "VERILOG_FILES": ["dir/src/tiny_dtl_gate_physical.v"],
    "CLOCK_PERIOD": 10.0,
    "CLOCK_PORT": "clk",
    "FP_PDN_VPITCH": 153.6,
    "FP_PDN_HPITCH": 153.6,
    "VDD_NETS": ["vdd"],
    "GND_NETS": ["gnd"],
    "RUN_CTS": false
}
"""

_DEMO_BAD_OPENLANE_CONFIG = """\
{
    "DESIGN_NAME": "",
    "VERILOG_FILES": [],
    "CLOCK_PERIOD": 0,
    "PRIVATE_DTL_INTERNAL": true
}
"""