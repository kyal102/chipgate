"""
ChipGate FPGABoardBench — Main benchmark runner.

Orchestrates 6 stages for each design:
  1. RTL safety precheck (existing ChipGate scan)
  2. Board profile check
  3. Pin/constraint validation
  4. FPGA synthesis readiness
  5. Optional board evidence import
  6. Bitstream readiness

Graceful degradation: all external tools are optional.
Missing tools produce *_SKIPPED_TOOL_MISSING statuses.
No external tool is required for unit tests.

Does NOT prove ASIC silicon correctness or hardware deployment safety.
"""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, statuses as st
from .board_profiles import (
    BoardProfile, get_board_profile, list_board_profiles,
    validate_board_profile_name,
)
from .pin_constraints import (
    PinConstraintResult, validate_pin_constraints,
    load_constraints_from_json,
)
from .fpga_board import run_fpga_synthesis, run_place_and_route
from .bitstream_readiness import check_bitstream_readiness
from .scanner import scan_file
from .toolchain import check_toolchain as check_silicon_toolchain


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class FPGADesignResult:
    """Per-design results for FPGABoardBench."""
    design_id: str = ""
    rtl_path: str = ""
    safety_precheck_status: str = ""
    safety_precheck_statuses: List[str] = field(default_factory=list)
    board_profile_status: str = ""
    pin_constraint_status: str = ""
    pin_constraint_checks: List[Dict[str, str]] = field(default_factory=list)
    fpga_synth_status: str = ""
    fpga_synth_cell_count: int = 0
    fpga_synth_wire_count: int = 0
    place_route_status: str = ""
    bitstream_status: str = ""
    board_evidence_status: str = ""
    board_evidence: Dict[str, Any] = field(default_factory=dict)
    overall_status: str = ""
    evidence_record: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "design_id": self.design_id,
            "rtl_path": self.rtl_path,
            "safety_precheck_status": self.safety_precheck_status,
            "safety_precheck_statuses": self.safety_precheck_statuses,
            "board_profile_status": self.board_profile_status,
            "pin_constraint_status": self.pin_constraint_status,
            "pin_constraint_checks": self.pin_constraint_checks,
            "fpga_synth_status": self.fpga_synth_status,
            "fpga_synth_cell_count": self.fpga_synth_cell_count,
            "fpga_synth_wire_count": self.fpga_synth_wire_count,
            "place_route_status": self.place_route_status,
            "bitstream_status": self.bitstream_status,
            "board_evidence_status": self.board_evidence_status,
            "board_evidence": self.board_evidence,
            "overall_status": self.overall_status,
            "evidence_record": self.evidence_record,
        }


@dataclass
class FPGABenchResult:
    """Complete FPGABoardBench result."""
    benchmark_name: str = "fpgabench_v0"
    benchmark_version: str = ""
    timestamp_utc: str = ""
    board_profile: str = "generic_fpga"
    board_profile_info: Dict[str, Any] = field(default_factory=dict)
    designs_tested: int = 0
    safety_precheck_passed: int = 0
    safety_precheck_pass_rate: float = 0.0
    pin_constraint_pass_rate: float = 0.0
    fpga_synth_pass_rate: float = 0.0
    place_route_pass_rate: float = 0.0
    bitstream_ready_rate: float = 0.0
    board_evidence_attached_count: int = 0
    unsafe_enable_events_total: int = 0
    kill_switch_bypass_total: int = 0
    artifact_hash_count: int = 0
    evidence_packs_created: int = 0
    toolchain_coverage: float = 0.0
    toolchain_report: Dict[str, Any] = field(default_factory=dict)
    design_results: List[Dict[str, Any]] = field(default_factory=list)
    overall_status: str = ""
    public_wording: str = ""
    limitation: str = ""

    def to_dict(self) -> dict:
        return {
            "benchmark_name": self.benchmark_name,
            "benchmark_version": self.benchmark_version,
            "timestamp_utc": self.timestamp_utc,
            "board_profile": self.board_profile,
            "board_profile_info": self.board_profile_info,
            "designs_tested": self.designs_tested,
            "safety_precheck_passed": self.safety_precheck_passed,
            "safety_precheck_pass_rate": self.safety_precheck_pass_rate,
            "pin_constraint_pass_rate": self.pin_constraint_pass_rate,
            "fpga_synth_pass_rate": self.fpga_synth_pass_rate,
            "place_route_pass_rate": self.place_route_pass_rate,
            "bitstream_ready_rate": self.bitstream_ready_rate,
            "board_evidence_attached_count": self.board_evidence_attached_count,
            "unsafe_enable_events_total": self.unsafe_enable_events_total,
            "kill_switch_bypass_total": self.kill_switch_bypass_total,
            "artifact_hash_count": self.artifact_hash_count,
            "evidence_packs_created": self.evidence_packs_created,
            "toolchain_coverage": self.toolchain_coverage,
            "toolchain_report": self.toolchain_report,
            "design_results": self.design_results,
            "overall_status": self.overall_status,
            "public_wording": self.public_wording,
            "limitation": self.limitation,
        }


# ── FPGA Toolchain Check ─────────────────────────────────────────────────────

_FPGA_TOOL_DEFS = {
    "yosys": ("yosys", ["--version"], "Yosys"),
    "nextpnr": ("nextpnr-ice40", ["--version"], "nextpnr"),
    "icestorm": ("icepack", ["--version"], "icepack"),
    "verilator": ("verilator", ["--version"], "Verilator"),
    "cocotb": ("cocotb-config", ["--version"], "cocotb"),
    "openFPGALoader": ("openFPGALoader", ["--version"], "openFPGALoader"),
}


def check_fpga_toolchain() -> dict:
    """
    Check FPGA-specific toolchain and return a simple dict.
    Reuses the silicon toolchain logic but adds FPGA-specific tools.
    """
    import shutil
    import subprocess

    report = {}
    for tool_key, (exe_name, version_args, _version_prefix) in _FPGA_TOOL_DEFS.items():
        exe_path = shutil.which(exe_name)
        if exe_path is not None:
            version_line = None
            try:
                result = subprocess.run(
                    [exe_path] + version_args,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0 and result.stdout.strip():
                    version_line = result.stdout.strip().split("\n")[0]
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass
            report[tool_key] = {
                "found": True,
                "path": exe_path,
                "version": version_line,
                "note": f"found at {exe_path}",
            }
        else:
            report[tool_key] = {
                "found": False,
                "path": None,
                "version": None,
                "note": "skipped (not found on PATH)",
            }

    return report


def _toolchain_coverage(tc: dict) -> float:
    """Calculate toolchain coverage as a fraction."""
    if not tc:
        return 0.0
    found = sum(1 for v in tc.values() if v.get("found", False))
    return found / len(tc)


# ── Evidence Record ──────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compute_evidence_hash(evidence: dict) -> str:
    # Exclude timestamp and certificate_hash from hash computation
    # so that evidence records with identical content produce the same hash
    check_data = {k: v for k, v in evidence.items()
                  if k not in ("certificate_hash", "timestamp_utc")}
    return _sha256(json.dumps(check_data, sort_keys=True, default=str))


def _create_evidence_record(
    design_id: str,
    rtl_text: str,
    board_profile: str,
    safety_result: str,
    pin_result: str,
    fpga_synth_result: str,
    place_route_result: str,
    bitstream_result: str,
    board_evidence_result: str,
    tool_versions: Dict[str, Optional[str]],
    replay_command: str,
    constraints_hash: str = "",
) -> dict:
    """Create an evidence record dict for a single design."""
    artifacts = [{"label": "rtl_input", "sha256": _sha256(rtl_text)}]
    if constraints_hash:
        artifacts.append({"label": "constraints", "sha256": constraints_hash})

    report_text = (
        f"{safety_result}|{pin_result}|{fpga_synth_result}|"
        f"{place_route_result}|{bitstream_result}|{board_evidence_result}"
    )
    artifacts.append({"label": "stage_results", "sha256": _sha256(report_text)})

    version_str = "; ".join(
        f"{k}={v}" for k, v in sorted(tool_versions.items()) if v
    )
    if version_str:
        artifacts.append({"label": "tool_versions", "sha256": _sha256(version_str)})

    evidence = {
        "benchmark_name": "fpgabench_v0",
        "benchmark_version": __version__,
        "design_id": design_id,
        "board_profile": board_profile,
        "rtl_hash": _sha256(rtl_text),
        "constraints_hash": constraints_hash,
        "chipgate_safety_result": safety_result,
        "pin_constraint_result": pin_result,
        "fpga_synth_result": fpga_synth_result,
        "place_route_result": place_route_result,
        "bitstream_readiness_result": bitstream_result,
        "board_evidence_result": board_evidence_result,
        "tool_versions": tool_versions,
        "artifact_hashes": artifacts,
        "replay_command": replay_command,
        "public_wording": st.FPGA_PUBLIC_WORDING,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    evidence["certificate_hash"] = _compute_evidence_hash(evidence)
    return evidence


# ── Board Evidence Import ────────────────────────────────────────────────────

def _load_board_evidence(design_dir: str, design_id: str) -> tuple:
    """
    Look for a board-test evidence JSON file in the design directory.

    Expected filename: <design_id>.board_evidence.json

    Returns:
        (status, evidence_dict) tuple
    """
    evidence_path = os.path.join(design_dir, f"{design_id}.board_evidence.json")
    if not os.path.exists(evidence_path):
        return st.BOARD_EVIDENCE_MISSING, {}

    try:
        text = Path(evidence_path).read_text(encoding="utf-8")
        data = json.loads(text)

        # Validate required fields
        required = ["board_profile", "design_id", "test_cycles"]
        for req in required:
            if req not in data:
                return st.BOARD_EVIDENCE_FAIL, {
                    "error": f"Missing required field: {req}",
                    "file": evidence_path,
                }

        # Check for failure indicators
        unsafe_events = data.get("unsafe_enable_events", 0)
        bypasses = data.get("kill_switch_bypasses", 0)
        glitches = data.get("reset_glitches", 0)

        if unsafe_events > 0 or bypasses > 0:
            return st.BOARD_EVIDENCE_FAIL, data

        return st.BOARD_EVIDENCE_ATTACHED, data

    except (json.JSONDecodeError, OSError) as e:
        return st.BOARD_EVIDENCE_FAIL, {
            "error": str(e),
            "file": evidence_path,
        }


# ── Stage Runners ────────────────────────────────────────────────────────────

# Statuses that represent genuine safety hazards (not advisory warnings)
_SAFETY_CRITICAL_FAILS = {
    st.UNSAFE_BYPASS_PATH,
    st.UNGATED_OUTPUT,
    st.UNSAFE_ACCEPTED,
    st.KILL_SWITCH_BYPASS,
    st.SAFE_STATE_VIOLATION,
    st.FAILSAFE_ESCAPED,
}


def _run_safety_precheck(rtl_path: str, allow_unsafe: bool = False) -> tuple:
    """
    Stage 1: RTL safety precheck using ChipGate scanner.

    Uses safety-critical failure detection: only blocks on genuine
    safety hazards (UNSAFE_BYPASS_PATH, UNGATED_OUTPUT, etc.), not
    advisory warnings like NEEDS_HUMAN_REVIEW or ASSERTION_MISSING.

    Returns:
        (status, list_of_statuses, scan_result)
    """
    scan_result = scan_file(rtl_path)
    has_critical_fail = any(
        s in _SAFETY_CRITICAL_FAILS for s in scan_result.statuses
    )

    if has_critical_fail and not allow_unsafe:
        return st.RTL_SCAN_FAIL, scan_result.statuses, scan_result
    elif has_critical_fail and allow_unsafe:
        return st.RTL_SCAN_FAIL, scan_result.statuses, scan_result
    else:
        return st.RTL_SCAN_PASS, scan_result.statuses, scan_result


def _run_board_profile_check(
    profile_name: str,
) -> tuple:
    """
    Stage 2: Validate board profile name.

    Returns:
        (status, profile_info_dict)
    """
    profile = get_board_profile(profile_name)
    if profile is None:
        return st.BOARD_PROFILE_INVALID, {}
    return st.BOARD_PROFILE_VALID, profile.to_dict()


def _run_pin_constraints(
    rtl_text: str,
    board_profile: BoardProfile,
    constraints: Optional[Dict[str, str]] = None,
) -> PinConstraintResult:
    """Stage 3: Pin/constraint validation."""
    return validate_pin_constraints(rtl_text, board_profile, constraints)


def _run_fpga_synthesis_stage(
    rtl_path: str,
    board_profile: BoardProfile,
    work_dir: Optional[str] = None,
) -> tuple:
    """
    Stage 4: FPGA synthesis.

    Returns:
        (status, cell_count, wire_count, synth_result_dict)
    """
    from .fpga_board import run_fpga_synthesis

    result = run_fpga_synthesis(
        rtl_path=rtl_path,
        fpga_family=board_profile.fpga_family,
        work_dir=work_dir,
    )
    return (
        result.status,
        result.cell_count,
        result.wire_count,
        result.to_dict(),
    )


def _run_place_route_stage(
    synth_json_path: str,
    board_profile: BoardProfile,
    work_dir: Optional[str] = None,
) -> tuple:
    """
    Stage 5 (part of synthesis): Place-and-route.

    Returns:
        (status, pnr_result_dict)
    """
    from .fpga_board import run_place_and_route

    result = run_place_and_route(
        synth_json_path=synth_json_path,
        fpga_family=board_profile.fpga_family,
        fpga_device=board_profile.fpga_device,
        package=board_profile.package,
        work_dir=work_dir,
    )
    return result.status, result.to_dict()


# ── Main Benchmark Runner ────────────────────────────────────────────────────

def run_fpgabench(
    benchmark_path: Optional[str] = None,
    demo: bool = False,
    board_profile_name: str = "generic_fpga",
    allow_unsafe: bool = False,
) -> FPGABenchResult:
    """
    Run the FPGABoardBench benchmark.

    Args:
        benchmark_path: Path to benchmark directory with designs and constraints.
                       If None and demo=True, uses built-in demo designs.
        demo: If True, run a built-in demo subset.
        board_profile_name: Name of the board profile to use.
        allow_unsafe: If True, allow unsafe designs to proceed to tool stages.

    Returns:
        FPGABenchResult with complete benchmark results.
    """
    # Get board profile
    profile_status, profile_info = _run_board_profile_check(board_profile_name)
    board_profile = get_board_profile(board_profile_name)
    if board_profile is None:
        board_profile = BoardProfile(
            name="generic_fpga",
            description="Fallback generic profile",
            clock_pin_placeholder="clk",
            reset_pin_placeholder="rst_n",
        )

    # Collect designs
    designs: list = []  # list of (rtl_path, design_id)

    if demo:
        demo_dir = _get_demo_designs_dir()
        if demo_dir:
            for vf in sorted(Path(demo_dir).glob("*.v")):
                designs.append((str(vf), vf.stem))

    if benchmark_path:
        bp = Path(benchmark_path)
        designs_dir = bp / "designs" if (bp / "designs").exists() else bp
        for vf in sorted(Path(designs_dir).glob("*.v")):
            designs.append((str(vf), vf.stem))

    if not designs:
        # Return empty result
        return FPGABenchResult(
            benchmark_version=__version__,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            board_profile=board_profile_name,
            board_profile_info=profile_info,
            public_wording=st.FPGA_PUBLIC_WORDING,
            limitation=st.FPGA_LIMITATION,
        )

    # Check toolchain
    tc_report = check_fpga_toolchain()
    tc_coverage = _toolchain_coverage(tc_report)

    # Collect tool versions for evidence
    tool_versions: Dict[str, Optional[str]] = {}
    for name, info in tc_report.items():
        tool_versions[name] = info.get("version")

    # Process each design
    all_results: List[Dict[str, Any]] = []
    total_hash_count = 0
    evidence_pack_count = 0

    # Shared work directory for synthesis outputs
    shared_work = tempfile.mkdtemp(prefix="chipgate_fpgabench_")

    for rtl_path, design_id in designs:
        dr = FPGADesignResult(design_id=design_id, rtl_path=rtl_path)

        # Read RTL text
        try:
            rtl_text = Path(rtl_path).read_text(encoding="utf-8")
        except OSError:
            dr.safety_precheck_status = st.RTL_SCAN_FAIL
            dr.overall_status = st.FPGA_BENCH_FAIL
            all_results.append(dr.to_dict())
            continue

        # Load constraints if available
        constraints: Optional[Dict[str, str]] = None
        constraints_hash = ""
        constraints_path = os.path.join(os.path.dirname(rtl_path),
                                        f"{design_id}.constraints.json")
        if os.path.exists(constraints_path):
            try:
                constraints = load_constraints_from_json(constraints_path)
                constraints_text = Path(constraints_path).read_text(encoding="utf-8")
                constraints_hash = _sha256(constraints_text)
            except (json.JSONDecodeError, OSError):
                pass

        # ── Stage 1: Safety precheck ─────────────────────────────────────
        safety_status, safety_statuses, _scan = _run_safety_precheck(
            rtl_path, allow_unsafe
        )
        dr.safety_precheck_status = safety_status
        dr.safety_precheck_statuses = safety_statuses

        # ── Stage 2: Board profile ───────────────────────────────────────
        dr.board_profile_status = profile_status

        # ── Stage 3: Pin constraints ─────────────────────────────────────
        pin_result = _run_pin_constraints(rtl_text, board_profile, constraints)
        dr.pin_constraint_status = pin_result.status
        dr.pin_constraint_checks = pin_result.checks

        # ── Stage 4: FPGA synthesis ──────────────────────────────────────
        synth_status, cell_count, wire_count, synth_details = (
            _run_fpga_synthesis_stage(rtl_path, board_profile, shared_work)
        )
        dr.fpga_synth_status = synth_status
        dr.fpga_synth_cell_count = cell_count
        dr.fpga_synth_wire_count = wire_count

        # ── Stage 5: Place-and-route (if synth passed) ──────────────────
        pnr_status = st.PLACE_ROUTE_SKIPPED_TOOL_MISSING
        if synth_status == st.FPGA_SYNTH_PASS:
            # Look for the synth JSON output
            synth_json = os.path.join(shared_work, "fpga_synth.json")
            if os.path.exists(synth_json):
                pr_status, _pr_details = _run_place_route_stage(
                    synth_json, board_profile, shared_work
                )
                pnr_status = pr_status
        dr.place_route_status = pnr_status

        # ── Stage 6: Bitstream readiness ─────────────────────────────────
        bs_result = check_bitstream_readiness(
            rtl_path=rtl_path,
            fpga_family=board_profile.fpga_family,
            work_dir=shared_work,
        )
        dr.bitstream_status = bs_result.status

        # ── Board evidence import ────────────────────────────────────────
        design_dir = os.path.dirname(rtl_path)
        be_status, be_data = _load_board_evidence(design_dir, design_id)
        dr.board_evidence_status = be_status
        dr.board_evidence = be_data

        # ── Overall status ───────────────────────────────────────────────
        if (safety_status == st.RTL_SCAN_PASS
                and dr.pin_constraint_status == st.PIN_CONSTRAINT_PASS):
            dr.overall_status = st.FPGA_BENCH_PASS
        else:
            dr.overall_status = st.FPGA_BENCH_FAIL

        # ── Evidence record ──────────────────────────────────────────────
        replay_cmd = (
            f"python -m chipgate fpga {os.path.dirname(rtl_path)} "
            f"--board-profile {board_profile_name}"
        )
        evidence = _create_evidence_record(
            design_id=design_id,
            rtl_text=rtl_text,
            board_profile=board_profile_name,
            safety_result=safety_status,
            pin_result=dr.pin_constraint_status,
            fpga_synth_result=dr.fpga_synth_status,
            place_route_result=dr.place_route_status,
            bitstream_result=dr.bitstream_status,
            board_evidence_result=dr.board_evidence_status,
            tool_versions=tool_versions,
            replay_command=replay_cmd,
            constraints_hash=constraints_hash,
        )
        dr.evidence_record = evidence
        total_hash_count += len(evidence.get("artifact_hashes", []))
        evidence_pack_count += 1

        all_results.append(dr.to_dict())

    # ── Compute aggregate metrics ─────────────────────────────────────────
    total = len(all_results)
    safety_passed = sum(
        1 for d in all_results
        if d["safety_precheck_status"] == st.RTL_SCAN_PASS
    )
    pin_passed = sum(
        1 for d in all_results
        if d["pin_constraint_status"] == st.PIN_CONSTRAINT_PASS
    )
    synth_passed = sum(
        1 for d in all_results
        if d["fpga_synth_status"] == st.FPGA_SYNTH_PASS
    )
    pnr_passed = sum(
        1 for d in all_results
        if d["place_route_status"] == st.PLACE_ROUTE_PASS
    )
    bs_ready = sum(
        1 for d in all_results
        if d["bitstream_status"] == st.BITSTREAM_READY
    )
    be_attached = sum(
        1 for d in all_results
        if d["board_evidence_status"] == st.BOARD_EVIDENCE_ATTACHED
    )

    unsafe_events_total = sum(
        d.get("board_evidence", {}).get("unsafe_enable_events", 0)
        for d in all_results
    )
    kill_bypass_total = sum(
        d.get("board_evidence", {}).get("kill_switch_bypasses", 0)
        for d in all_results
    )

    # Overall bench status
    has_any_pass = any(
        d["overall_status"] == st.FPGA_BENCH_PASS for d in all_results
    )
    overall = st.FPGA_BENCH_PASS if has_any_pass else st.FPGA_BENCH_FAIL
    if total == 0:
        overall = st.FPGA_BENCH_FAIL

    result = FPGABenchResult(
        benchmark_version=__version__,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        board_profile=board_profile_name,
        board_profile_info=profile_info,
        designs_tested=total,
        safety_precheck_passed=safety_passed,
        safety_precheck_pass_rate=safety_passed / total if total else 0.0,
        pin_constraint_pass_rate=pin_passed / total if total else 0.0,
        fpga_synth_pass_rate=synth_passed / total if total else 0.0,
        place_route_pass_rate=pnr_passed / total if total else 0.0,
        bitstream_ready_rate=bs_ready / total if total else 0.0,
        board_evidence_attached_count=be_attached,
        unsafe_enable_events_total=unsafe_events_total,
        kill_switch_bypass_total=kill_bypass_total,
        artifact_hash_count=total_hash_count,
        evidence_packs_created=evidence_pack_count,
        toolchain_coverage=tc_coverage,
        toolchain_report=tc_report,
        design_results=all_results,
        overall_status=overall,
        public_wording=st.FPGA_PUBLIC_WORDING,
        limitation=st.FPGA_LIMITATION,
    )

    return result


def _get_demo_designs_dir() -> Optional[str]:
    """Return the path to the built-in demo designs directory."""
    # Look for benchmarks/fpgabench_v0/designs relative to this package
    package_dir = Path(__file__).parent.parent
    demo_dir = package_dir / "benchmarks" / "fpgabench_v0" / "designs"
    if demo_dir.exists():
        return str(demo_dir)
    return None


def get_demo_designs() -> List[str]:
    """Return list of built-in demo design RTL file paths."""
    demo_dir = _get_demo_designs_dir()
    if demo_dir is None:
        return []
    return sorted(str(p) for p in Path(demo_dir).glob("*.v"))


def format_fpga_toolchain_status(tc_report: dict) -> str:
    """Format FPGA toolchain status for terminal output."""
    lines = ["ChipGate FPGABoardBench — Toolchain Status", ""]
    for name, info in tc_report.items():
        if info.get("found"):
            status_str = f"found {info.get('path', '')}"
            ver = info.get("version", "")
            if ver:
                status_str += f" ({ver})"
        else:
            status_str = "skipped"
        lines.append(f"  {name.capitalize():<20s} {status_str}")

    found = sum(1 for v in tc_report.values() if v.get("found", False))
    total = len(tc_report)
    lines.append("")
    lines.append(f"  Toolchain coverage: {found}/{total} ({found/total:.0%})")
    lines.append("")
    lines.append(f"  Supported board profiles: {', '.join(list_board_profiles())}")
    return "\n".join(lines)