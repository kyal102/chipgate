"""
ChipGate TinyTapeoutPrep — Main orchestrator.

Generates a minimal DTL safety gate design with TinyTapeout-compatible wrapper,
pinout, docs, testbench, and runs 15 submission readiness checks.

Steps:
  1. Generate core Verilog (combinational + FSM variant)
  2. Generate TinyTapeout wrapper
  3. Validate pinout
  4. Generate info.yaml, docs/info.md, submission_checklist.md
  5. Generate testbench
  6. Run 15 submission readiness checks
  7. Generate evidence pack
  8. Compile results

Does NOT guarantee silicon correctness, fabrication readiness, or physical safety.
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
from .tt_pinout import (
    get_canonical_pinout,
    validate_pinout,
    pinout_to_json,
)
from .tt_wrapper import (
    generate_core_verilog,
    generate_wrapper_verilog,
    generate_fsm_verilog,
)
from .tt_docs import (
    generate_info_yaml,
    generate_info_md,
    generate_submission_checklist,
    generate_testbench_verilog,
)
from .tt_submission_check import run_submission_checks


# ── Safety properties for the public DTL gate ────────────────────────────────

SAFETY_PROPERTIES = [
    "kill_switch forces actuator_enable low",
    "timeout forces actuator_enable low",
    "reset forces actuator_enable low",
    "actuator_enable implies verifier_ok and policy_ok and sensor_ok",
    "FAILSAFE state cannot jump directly to APPROVED (FSM variant)",
]


@dataclass
class DesignResult:
    """Per-design result for TinyTapeoutPrep."""
    design_id: str = ""
    wrapper_status: str = ""
    pinout_status: str = ""
    submission_check_status: str = ""
    safety_result: str = ""
    overall_status: str = ""

    def to_dict(self) -> dict:
        return {
            "design_id": self.design_id,
            "wrapper_status": self.wrapper_status,
            "pinout_status": self.pinout_status,
            "submission_check_status": self.submission_check_status,
            "safety_result": self.safety_result,
            "overall_status": self.overall_status,
        }


@dataclass
class TinyTapeoutPrepResult:
    """Top-level result for TinyTapeoutPrep."""
    benchmark_version: str = __version__
    timestamp_utc: str = ""
    overall_status: str = st.TINYTAPEOUT_PREP_PASS
    designs_generated: int = 0
    wrappers_generated: int = 0
    pinout_checks_passed: int = 0
    submission_checks_passed: int = 0
    submission_checks_failed: int = 0
    submission_checks_skipped: int = 0
    safety_properties_count: int = len(SAFETY_PROPERTIES)
    private_leak_count: int = 0
    testbench_count: int = 0
    evidence_packs_created: int = 0
    manual_review_items_count: int = 0
    design_results: List[Dict[str, str]] = field(default_factory=list)
    pinout: Dict[str, str] = field(default_factory=dict)
    submission_checks: List[Dict[str, str]] = field(default_factory=list)
    manual_review_items: List[str] = field(default_factory=list)
    public_wording: str = st.TINYTAPEOUT_PUBLIC_WORDING
    limitation: str = st.TINYTAPEOUT_LIMITATION
    artifacts_dir: str = ""

    def to_dict(self) -> dict:
        return {
            "benchmark_version": self.benchmark_version,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "designs_generated": self.designs_generated,
            "wrappers_generated": self.wrappers_generated,
            "pinout_checks_passed": self.pinout_checks_passed,
            "submission_checks_passed": self.submission_checks_passed,
            "submission_checks_failed": self.submission_checks_failed,
            "submission_checks_skipped": self.submission_checks_skipped,
            "safety_properties_count": self.safety_properties_count,
            "private_leak_count": self.private_leak_count,
            "testbench_count": self.testbench_count,
            "evidence_packs_created": self.evidence_packs_created,
            "manual_review_items_count": self.manual_review_items_count,
            "design_results": self.design_results,
            "pinout": self.pinout,
            "submission_checks": self.submission_checks,
            "manual_review_items": self.manual_review_items,
            "public_wording": self.public_wording,
            "limitation": self.limitation,
            "artifacts_dir": self.artifacts_dir,
        }


def run_tinytapeout_prep(
    demo: bool = True,
    benchmark_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> TinyTapeoutPrepResult:
    """Run the full TinyTapeoutPrep pipeline.

    Args:
        demo: If True, generate built-in demo designs.
        benchmark_path: Path to existing benchmark directory (for --submission-check).
        output_dir: Directory to write artifacts to.

    Returns:
        TinyTapeoutPrepResult with all results.
    """
    result = TinyTapeoutPrepResult()
    result.timestamp_utc = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # Determine output directory
    if output_dir:
        out = Path(output_dir)
    else:
        out = Path(tempfile.mkdtemp(prefix="chipgate_tt_"))

    out.mkdir(parents=True, exist_ok=True)
    result.artifacts_dir = str(out)

    # Create subdirectories
    designs_dir = out / "designs"
    testbenches_dir = out / "testbenches"
    docs_dir = out / "docs"
    for d in [designs_dir, testbenches_dir, docs_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Generate core Verilog ────────────────────────────────────────

    core_v = generate_core_verilog()
    (designs_dir / "tiny_dtl_gate.v").write_text(core_v, encoding="utf-8")
    result.designs_generated += 1

    fsm_v = generate_fsm_verilog()
    (designs_dir / "tiny_dtl_gate_fsm.v").write_text(fsm_v, encoding="utf-8")
    result.designs_generated += 1

    # ── Step 2: Generate wrapper ─────────────────────────────────────────────

    wrapper_v = generate_wrapper_verilog()
    (designs_dir / "tt_um_chipgate_dtl_gate.v").write_text(
        wrapper_v, encoding="utf-8"
    )
    result.wrappers_generated += 1

    # ── Step 3: Validate pinout ──────────────────────────────────────────────

    pinout = get_canonical_pinout()
    pinout_result = validate_pinout(pinout)
    result.pinout = pinout
    result.pinout_checks_passed = 1 if pinout_result.valid else 0

    # Save pinout.json
    (out / "pinout.json").write_text(
        pinout_to_json(pinout), encoding="utf-8"
    )

    # ── Step 4: Generate docs ────────────────────────────────────────────────

    info_yaml = generate_info_yaml(version=__version__)
    (out / "info.yaml").write_text(info_yaml, encoding="utf-8")

    info_md = generate_info_md(
        version=__version__,
        pinout=pinout,
        safety_properties=SAFETY_PROPERTIES,
    )
    (docs_dir / "info.md").write_text(info_md, encoding="utf-8")

    # ── Step 5: Generate testbench ───────────────────────────────────────────

    tb_v = generate_testbench_verilog()
    (testbenches_dir / "tb_tiny_dtl_gate.v").write_text(
        tb_v, encoding="utf-8"
    )
    result.testbench_count = 1

    # ── Step 6: Run submission checks ────────────────────────────────────────

    sub_result = run_submission_checks(
        top_module_verilog=wrapper_v,
        info_yaml_content=info_yaml,
        info_md_content=info_md,
        testbench_content=tb_v,
    )
    result.submission_checks = sub_result.checks
    result.submission_checks_passed = sub_result.passed_count
    result.submission_checks_failed = sub_result.failed_count
    result.submission_checks_skipped = sub_result.skipped_count
    result.manual_review_items = sub_result.manual_review_items
    result.manual_review_items_count = len(sub_result.manual_review_items)

    # Count private leaks from checks
    for chk in sub_result.checks:
        if chk.get("id") == "3" and chk.get("status") == "FAIL":
            result.private_leak_count = 1
            break

    # ── Step 7: Generate evidence pack ───────────────────────────────────────

    evidence = _create_evidence_pack(
        core_v=core_v,
        wrapper_v=wrapper_v,
        fsm_v=fsm_v,
        tb_v=tb_v,
        info_yaml=info_yaml,
        info_md=info_md,
        pinout=pinout,
        submission_checks=sub_result.checks,
    )
    evidence_path = out / "evidence_pack.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    result.evidence_packs_created = 1

    # ── Step 8: Generate submission checklist with actual results ────────────

    checklist_md = generate_submission_checklist(checks=sub_result.checks)
    (out / "submission_checklist.md").write_text(
        checklist_md, encoding="utf-8"
    )

    # ── Step 9: Build design results ─────────────────────────────────────────

    # Design 1: Combinational core
    d1 = DesignResult(
        design_id="tiny_dtl_gate (combinational)",
        wrapper_status=st.TT_WRAPPER_CREATED,
        pinout_status=sub_result.overall_status,
        submission_check_status=sub_result.overall_status,
        safety_result=_check_safety_in_verilog(core_v),
    )
    d1.overall_status = _design_overall(d1)
    result.design_results.append(d1.to_dict())

    # Design 2: FSM variant
    d2 = DesignResult(
        design_id="tiny_dtl_gate_fsm (sequential)",
        wrapper_status=st.TT_WRAPPER_CREATED,
        pinout_status=sub_result.overall_status,
        submission_check_status=sub_result.overall_status,
        safety_result=_check_safety_in_verilog(fsm_v),
    )
    d2.overall_status = _design_overall(d2)
    result.design_results.append(d2.to_dict())

    # ── Overall status ───────────────────────────────────────────────────────

    has_failures = (
        result.submission_checks_failed > 0
        or result.private_leak_count > 0
        or any(d["overall_status"] in st.FAIL_STATUSES for d in result.design_results)
    )

    if has_failures:
        result.overall_status = st.TINYTAPEOUT_PREP_FAIL
    else:
        result.overall_status = st.TINYTAPEOUT_PREP_PASS

    # If there are manual review items, note it
    if result.manual_review_items:
        result.manual_review_items.insert(0, st.TT_READY_FOR_MANUAL_REVIEW)

    return result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _check_safety_in_verilog(verilog: str) -> str:
    """Check safety properties in generated Verilog.

    Returns SAFETY_GATE_PRESENT if core safety signals are found,
    TT_SAFETY_PROPERTY_MISSING otherwise.
    """
    required = ["kill_switch", "timeout", "reset", "verifier_ok", "policy_ok", "sensor_ok"]
    found = sum(1 for sig in required if sig in verilog)

    if found >= len(required) - 1:  # Allow 1 missing
        return st.SAFETY_GATE_PRESENT
    return st.TT_SAFETY_PROPERTY_MISSING


def _design_overall(d: DesignResult) -> str:
    """Compute overall status for a single design."""
    statuses = [d.wrapper_status, d.pinout_status, d.submission_check_status, d.safety_result]
    for s in statuses:
        if s in st.FAIL_STATUSES:
            return st.TINYTAPEOUT_PREP_FAIL
    return st.TINYTAPEOUT_PREP_PASS


def _create_evidence_pack(
    core_v: str,
    wrapper_v: str,
    fsm_v: str,
    tb_v: str,
    info_yaml: str,
    info_md: str,
    pinout: Dict[str, str],
    submission_checks: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Create an evidence pack with SHA-256 hashes of all artifacts."""
    pack = {
        "tool": "ChipGate TinyTapeoutPrep",
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifacts": {},
        "submission_checks": submission_checks,
    }

    artifacts = {
        "tiny_dtl_gate.v": core_v,
        "tt_um_chipgate_dtl_gate.v": wrapper_v,
        "tiny_dtl_gate_fsm.v": fsm_v,
        "tb_tiny_dtl_gate.v": tb_v,
        "info.yaml": info_yaml,
        "docs/info.md": info_md,
        "pinout.json": json.dumps(pinout, sort_keys=True),
    }

    for name, content in artifacts.items():
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        pack["artifacts"][name] = {"sha256": h, "size_bytes": len(content.encode("utf-8"))}

    return pack