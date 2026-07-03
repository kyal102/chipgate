"""
DTL-ChipBench — model-free, deterministic synthetic RTL gate benchmark.

Tests the ChipGate/DTL verification gate itself using deterministic synthetic
RTL proposals and mutation-generated cases. Measures whether unsafe or
regressive chip-design changes are blocked before heavier verification
is needed. This is a model-free benchmark; model-connected testing is
future work.

Supports three benchmark modes:
    - ungated_baseline: Everything goes to heavy verification (no gate).
    - chipgate_only: Deterministic public gates filter obvious unsafe cases.
    - external_dtl: External DTL routes/filters/ranks proposals before ChipGate.
"""

import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import statuses as st
from .scanner import scan_file
from .cost_model import (
    format_cost_report,
    tier_cost,
    baseline_cost,
    dtl_gated_cost,
    speedup_ratio,
    cost_per_verified_accepted,
    VALID_MODES,
    ungated_mode_cost,
    chipgate_only_mode_cost,
    external_dtl_mode_cost,
    format_mode_cost_report,
)
from .noregression import check_regression_from_results
from .bench_cases import BenchCase, generate_all_cases, CATEGORIES


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class CaseResult:
    """Result for a single benchmark case."""
    case_id: str
    category: str
    risk_level: str
    gate_result: str           # "block" or "pass"
    expected_gate_result: str
    gate_correct: bool
    statuses: List[str] = field(default_factory=list)
    heavy_check_decision: str = "required"  # "avoided" or "required"
    regression_status: str = ""  # REGRESSION_DETECTED or NO_REGRESSION_PASS or ""
    expected_regression: str = ""
    regression_correct: bool = True
    findings_count: int = 0
    certificate_hash: str = ""
    replay_command: str = ""
    duration_ms: float = 0.0
    reason: str = ""
    # v0.3.0: adapter metadata
    proposal_id: str = ""
    proposal_source: str = "synthetic"
    adapter_name: str = "synthetic"
    adapter_version: str = ""
    adapter_route_label: str = ""
    adapter_reason: str = ""
    input_hash: str = ""
    output_hash: str = ""


@dataclass
class BenchResult:
    """Complete benchmark result for a single mode."""
    benchmark_version: str = "0.1.0"
    timestamp_utc: str = ""
    public_wording: str = st.CHIPBENCH_PUBLIC_WORDING
    disclaimer: str = ""
    benchmark_mode_label: str = "Model-Free DTL Gate Benchmark"
    limitation: str = ""

    # v0.3.0: mode support
    benchmark_mode: str = "chipgate_only"
    adapter_name: str = ""
    proposal_source: str = "synthetic"

    # Counts
    total_cases: int = 0
    unsafe_cases: int = 0
    safe_cases: int = 0
    regression_cases: int = 0

    # Gate results
    unsafe_blocked: int = 0
    unsafe_accepted: int = 0
    safe_accepted: int = 0
    safe_rejected: int = 0
    regressions_detected: int = 0
    regressions_accepted: int = 0

    # Metrics
    false_accept_rate: float = 0.0
    false_reject_rate: float = 0.0
    no_regression_pass_rate: float = 0.0
    replay_match_rate: float = 100.0
    heavy_checks_baseline: int = 0
    heavy_checks_dtl: int = 0
    heavy_checks_avoided: int = 0
    estimated_baseline_cost: int = 0
    estimated_dtl_cost: int = 0
    estimated_speedup_ratio: float = 0.0
    cost_per_verified_accepted: float = 0.0

    # Case results
    case_results: List[CaseResult] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)

    # Evidence
    evidence_packs_created: int = 0
    benchmark_hash: str = ""
    replay_command: str = ""

    # v0.3.0: holdout info
    holdout_cases_included: int = 0

    def to_dict(self) -> dict:
        d = {
            "benchmark_version": self.benchmark_version,
            "timestamp_utc": self.timestamp_utc,
            "public_wording": self.public_wording,
            "disclaimer": self.disclaimer,
            "benchmark_mode_label": self.benchmark_mode_label,
            "benchmark_mode": self.benchmark_mode,
            "adapter_name": self.adapter_name,
            "proposal_source": self.proposal_source,
            "limitation": self.limitation,
            "total_cases": self.total_cases,
            "unsafe_cases": self.unsafe_cases,
            "safe_cases": self.safe_cases,
            "regression_cases": self.regression_cases,
            "unsafe_blocked": self.unsafe_blocked,
            "unsafe_accepted": self.unsafe_accepted,
            "safe_accepted": self.safe_accepted,
            "safe_rejected": self.safe_rejected,
            "regressions_detected": self.regressions_detected,
            "regressions_accepted": self.regressions_accepted,
            "false_accept_rate": round(self.false_accept_rate, 2),
            "false_reject_rate": round(self.false_reject_rate, 2),
            "no_regression_pass_rate": round(self.no_regression_pass_rate, 2),
            "replay_match_rate": round(self.replay_match_rate, 2),
            "heavy_checks_baseline": self.heavy_checks_baseline,
            "heavy_checks_dtl": self.heavy_checks_dtl,
            "heavy_checks_avoided": self.heavy_checks_avoided,
            "estimated_baseline_cost": self.estimated_baseline_cost,
            "estimated_dtl_cost": self.estimated_dtl_cost,
            "estimated_speedup_ratio": round(self.estimated_speedup_ratio, 2),
            "cost_per_verified_accepted": round(self.cost_per_verified_accepted, 2),
            "evidence_packs_created": self.evidence_packs_created,
            "benchmark_hash": self.benchmark_hash,
            "replay_command": self.replay_command,
            "categories_run": self.categories,
            "holdout_cases_included": self.holdout_cases_included,
            "cost_model": {
                "dtl_scan": tier_cost("dtl_scan"),
                "lint": tier_cost("lint"),
                "simulation": tier_cost("simulation"),
                "formal": tier_cost("formal"),
                "synthesis": tier_cost("synthesis"),
            },
        }
        # Limit case results in summary output
        d["case_results_summary"] = [
            {
                "case_id": cr.case_id,
                "category": cr.category,
                "gate_result": cr.gate_result,
                "expected": cr.expected_gate_result,
                "correct": cr.gate_correct,
                "heavy_check": cr.heavy_check_decision,
                "proposal_source": cr.proposal_source,
            }
            for cr in self.case_results
        ]
        return d

    def to_full_dict(self) -> dict:
        """Full output with all case details."""
        d = self.to_dict()
        d["case_results_full"] = [
            {
                "case_id": cr.case_id,
                "category": cr.category,
                "risk_level": cr.risk_level,
                "gate_result": cr.gate_result,
                "expected_gate_result": cr.expected_gate_result,
                "gate_correct": cr.gate_correct,
                "statuses": cr.statuses,
                "heavy_check_decision": cr.heavy_check_decision,
                "regression_status": cr.regression_status,
                "expected_regression": cr.expected_regression,
                "regression_correct": cr.regression_correct,
                "findings_count": cr.findings_count,
                "certificate_hash": cr.certificate_hash,
                "duration_ms": round(cr.duration_ms, 2),
                "reason": cr.reason,
                "proposal_id": cr.proposal_id,
                "proposal_source": cr.proposal_source,
                "adapter_name": cr.adapter_name,
                "adapter_route_label": cr.adapter_route_label,
                "adapter_reason": cr.adapter_reason,
                "input_hash": cr.input_hash,
                "output_hash": cr.output_hash,
            }
            for cr in self.case_results
        ]
        return d


@dataclass
class ComparisonResult:
    """Result of comparing multiple benchmark modes."""
    timestamp_utc: str = ""
    public_wording: str = st.CHIPBENCH_PUBLIC_WORDING
    limitation: str = st.CHIPBENCH_LIMITATION
    modes: Dict[str, BenchResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "timestamp_utc": self.timestamp_utc,
            "public_wording": self.public_wording,
            "limitation": self.limitation,
            "modes": {},
        }
        for mode, result in self.modes.items():
            d["modes"][mode] = result.to_dict()
            # Add the key metric
            d["modes"][mode]["estimated_cost_per_verified_accepted_change"] = round(
                result.cost_per_verified_accepted, 2
            )
        return d


# ── Mode-specific Runners ────────────────────────────────────────────────────

def _process_single_case(
    case: BenchCase,
    proposed_rtl: str,
    tmp_dir: str,
    benchmark_mode: str,
    proposal: Optional[Any] = None,
) -> CaseResult:
    """
    Process a single benchmark case through the gate.

    Args:
        case: The benchmark case definition.
        proposed_rtl: The RTL to evaluate (from adapter or built-in).
        tmp_dir: Temp directory for writing RTL files.
        benchmark_mode: Current benchmark mode.
        proposal: Optional ProposalResult from an adapter.

    Returns:
        CaseResult with gate decision and metrics.
    """
    t0 = time.monotonic()

    # Write proposed RTL to temp file
    case_file = os.path.join(tmp_dir, f"{case.case_id}.v")
    with open(case_file, "w") as f:
        f.write(proposed_rtl)

    input_hash = hashlib.sha256(proposed_rtl.encode()).hexdigest()

    # Determine whether to scan based on mode
    if benchmark_mode == "ungated_baseline":
        # Ungated: everything passes to heavy verification
        scan_result = None
        gate_result = "pass"
    else:
        # chipgate_only or external_dtl: scan with ChipGate
        try:
            scan_result = scan_file(case_file, generate_replay=True)
        except Exception:
            scan_result = None

        if scan_result and st.RTL_SCAN_PASS in scan_result.statuses:
            gate_result = "pass"
        else:
            gate_result = "block"

    t1 = time.monotonic()
    duration_ms = (t1 - t0) * 1000

    # Check if gate decision matches expectation
    gate_correct = (gate_result == case.expected_gate_result)

    # Heavy check decision
    if gate_result == "block":
        heavy_decision = "avoided"
    else:
        heavy_decision = "required"

    # Regression check (if baseline exists)
    regression_status = ""
    regression_correct = True
    if case.rtl_before:
        base_file = os.path.join(tmp_dir, f"{case.case_id}_base.v")
        with open(base_file, "w") as f:
            f.write(case.rtl_before)
        try:
            base_scan = scan_file(base_file, generate_replay=False)
            reg = check_regression_from_results(case.case_id, base_scan,
                                                 scan_result or base_scan)
            regression_status = reg.status
            if case.expected_regression_result:
                regression_correct = (reg.status == (
                    st.REGRESSION_DETECTED if case.expected_regression_result == "regression"
                    else st.NO_REGRESSION_PASS
                ))
        except Exception:
            regression_status = "error"

    # Count findings
    findings_count = len(scan_result.findings) if scan_result else 0

    # Certificate hash
    cert_hash = scan_result.certificate_hash if scan_result else ""

    output_hash = hashlib.sha256(
        (proposed_rtl + gate_result).encode()
    ).hexdigest()

    # Adapter metadata
    prop_id = ""
    prop_source = "synthetic"
    adapter_nm = "synthetic"
    adapter_ver = ""
    adapter_route = ""
    adapter_rsn = ""
    if proposal is not None:
        prop_id = proposal.proposal_id
        prop_source = proposal.proposal_source
        adapter_nm = proposal.adapter_name
        adapter_ver = proposal.adapter_version
        adapter_route = proposal.route_label or ""
        adapter_rsn = proposal.reason or ""

    cr = CaseResult(
        case_id=case.case_id,
        category=case.category,
        risk_level=case.risk_level,
        gate_result=gate_result,
        expected_gate_result=case.expected_gate_result,
        gate_correct=gate_correct,
        statuses=scan_result.statuses if scan_result else [],
        heavy_check_decision=heavy_decision,
        regression_status=regression_status,
        expected_regression=case.expected_regression_result or "",
        regression_correct=regression_correct,
        findings_count=findings_count,
        certificate_hash=cert_hash,
        replay_command=scan_result.replay_command if scan_result else "",
        duration_ms=duration_ms,
        reason=case.reason,
        proposal_id=prop_id,
        proposal_source=prop_source,
        adapter_name=adapter_nm,
        adapter_version=adapter_ver,
        adapter_route_label=adapter_route,
        adapter_reason=adapter_rsn,
        input_hash=input_hash,
        output_hash=output_hash,
    )
    return cr


def _compute_aggregate_metrics(result: BenchResult) -> None:
    """Compute aggregate metrics from individual case results."""
    # Unsafe blocked / accepted
    for cr in result.case_results:
        if cr.expected_gate_result == "block":
            if cr.gate_result == "block":
                result.unsafe_blocked += 1
            else:
                result.unsafe_accepted += 1
        else:
            if cr.gate_result == "pass":
                result.safe_accepted += 1
            else:
                result.safe_rejected += 1

    # Regressions
    result.regressions_detected = sum(
        1 for cr in result.case_results
        if cr.regression_status == st.REGRESSION_DETECTED
    )
    result.regressions_accepted = sum(
        1 for cr in result.case_results
        if cr.regression_status == st.REGRESSION_DETECTED and cr.gate_result == "pass"
    )

    # False accept/reject rates
    if result.unsafe_cases > 0:
        result.false_accept_rate = (result.unsafe_accepted / result.unsafe_cases) * 100
    if result.safe_cases > 0:
        result.false_reject_rate = (result.safe_rejected / result.safe_cases) * 100

    # No-regression pass rate
    reg_cases = [cr for cr in result.case_results if cr.regression_status]
    if reg_cases:
        no_reg = sum(1 for cr in reg_cases
                     if cr.regression_status == st.NO_REGRESSION_PASS)
        result.no_regression_pass_rate = (no_reg / len(reg_cases)) * 100

    # Heavy checks
    result.heavy_checks_baseline = result.total_cases
    if result.benchmark_mode == "ungated_baseline":
        result.heavy_checks_dtl = result.total_cases
        result.heavy_checks_avoided = 0
    else:
        result.heavy_checks_dtl = result.safe_accepted + result.safe_rejected
        result.heavy_checks_avoided = result.heavy_checks_baseline - result.heavy_checks_dtl

    # Cost model — mode-aware
    result.estimated_baseline_cost = baseline_cost(result.total_cases)

    if result.benchmark_mode == "ungated_baseline":
        result.estimated_dtl_cost = baseline_cost(result.total_cases)
    elif result.benchmark_mode == "chipgate_only":
        result.estimated_dtl_cost = chipgate_only_mode_cost(
            result.total_cases,
            result.unsafe_blocked,
            result.safe_accepted + result.safe_rejected,
        )
    elif result.benchmark_mode == "external_dtl":
        # For external_dtl, the adapter may have pre-filtered some cases
        # that never reached ChipGate. Those are counted separately.
        dtl_pre_filtered = sum(
            1 for cr in result.case_results
            if cr.adapter_route_label in ("blocked", "safety_gate_missing",
                                           "unsafe_path", "rejected")
        )
        result.estimated_dtl_cost = external_dtl_mode_cost(
            result.total_cases,
            dtl_pre_filtered,
            result.unsafe_blocked,
            result.safe_accepted + result.safe_rejected,
        )

    if result.estimated_dtl_cost > 0:
        result.estimated_speedup_ratio = speedup_ratio(
            result.estimated_baseline_cost, result.estimated_dtl_cost
        )
    result.cost_per_verified_accepted = cost_per_verified_accepted(
        result.estimated_dtl_cost, result.safe_accepted
    )

    # Replay match (deterministic benchmark — always 100% unless drift)
    all_correct = all(cr.gate_correct for cr in result.case_results)
    result.replay_match_rate = 100.0 if all_correct else 0.0

    # Benchmark hash — include mode
    bench_data = json.dumps({
        "version": result.benchmark_version,
        "mode": result.benchmark_mode,
        "total": result.total_cases,
        "blocked": result.unsafe_blocked,
        "accepted": result.safe_accepted,
        "speedup": result.estimated_speedup_ratio,
    }, sort_keys=True)
    result.benchmark_hash = hashlib.sha256(bench_data.encode()).hexdigest()


# ── Main Benchmark Runners ───────────────────────────────────────────────────

def run_benchmark(
    cases: Optional[List[BenchCase]] = None,
    evidence: bool = False,
    compare_baseline: bool = False,
    mode: str = "chipgate_only",
    adapter=None,
    output_dir: Optional[str] = None,
) -> BenchResult:
    """
    Run the DTL-ChipBench benchmark in a specific mode.

    Args:
        cases: List of BenchCase to run. If None, uses the standard 100+ cases.
        evidence: If True, generate evidence records for each case.
        compare_baseline: (Legacy) compare against ungated baseline workflow.
        mode: Benchmark mode — "ungated_baseline", "chipgate_only", or "external_dtl".
        adapter: Optional adapter instance for external_dtl mode.
        output_dir: Optional directory to save results and evidence packs.

    Returns:
        BenchResult with all metrics computed.
    """
    from . import __version__

    if mode not in VALID_MODES:
        raise ValueError(f"Unknown mode: {mode}. Must be one of: {VALID_MODES}")

    if cases is None:
        cases = generate_all_cases()

    # Mode labels
    mode_labels = {
        "ungated_baseline": "Ungated Baseline (no gate)",
        "chipgate_only": "ChipGate-Only (deterministic public gates)",
        "external_dtl": "External DTL Connected (adapter-supplied proposals)",
    }

    adapter_name = ""
    proposal_source = "built-in synthetic"
    if adapter is not None:
        adapter_name = adapter.name
        proposal_source = adapter.source_label

    result = BenchResult(
        benchmark_version=__version__,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        public_wording=st.CHIPBENCH_PUBLIC_WORDING,
        disclaimer=(
            "These are estimated verification-cost units under the synthetic "
            "benchmark cost model. They do not represent real-world EDA cost, "
            "GPU time, or monetary cost."
        ),
        benchmark_mode_label=mode_labels.get(mode, mode),
        limitation=st.CHIPBENCH_LIMITATION,
        benchmark_mode=mode,
        adapter_name=adapter_name,
        proposal_source=proposal_source,
    )

    # Set up output directory
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        evidence_dir = os.path.join(output_dir, "evidence_packs")
        os.makedirs(evidence_dir, exist_ok=True)
    else:
        tmp_dir = tempfile.mkdtemp(prefix="chipbench_")
        evidence_dir = tmp_dir

    # Count by expectation
    result.unsafe_cases = sum(1 for c in cases if c.expected_gate_result == "block")
    result.safe_cases = sum(1 for c in cases if c.expected_gate_result == "pass")
    result.regression_cases = sum(1 for c in cases if c.rtl_before)
    result.total_cases = len(cases)

    # Track categories
    seen_cats = set()
    for c in cases:
        seen_cats.add(c.category)
    result.categories = sorted(seen_cats)

    # Load holdout cases if present
    holdout_dir = Path(output_dir) / ".." / "chipbench_holdout" if output_dir else None
    holdout_cases = _load_holdout_cases(holdout_dir)
    result.holdout_cases_included = len(holdout_cases)
    all_cases = cases + holdout_cases

    # Generate proposals via adapter
    from .adapters.base import ProposalInput
    proposals = {}
    if adapter is not None:
        for case in all_cases:
            inp = ProposalInput(
                case_id=case.case_id,
                rtl_before=case.rtl_before,
                mutation_set=[(case.category, case.reason)],
                risk_level=case.risk_level,
            )
            proposals[case.case_id] = adapter.get_proposal(inp)

    # Run each case
    for case in all_cases:
        proposal = proposals.get(case.case_id)
        proposed_rtl = proposal.proposed_rtl if proposal else case.rtl_after

        cr = _process_single_case(
            case=case,
            proposed_rtl=proposed_rtl,
            tmp_dir=evidence_dir,
            benchmark_mode=mode,
            proposal=proposal,
        )
        result.case_results.append(cr)

        # Generate evidence record if requested
        if evidence:
            _save_case_evidence_v2(case, cr, evidence_dir, mode, adapter_name, proposal_source)
            result.evidence_packs_created += 1

    # Compute aggregate metrics
    _compute_aggregate_metrics(result)

    # Replay command
    result.replay_command = f"python -m chipgate bench --mode {mode} --demo"

    # Save mode result JSON if output_dir specified
    if output_dir:
        mode_file = os.path.join(output_dir, f"mode_{mode}.json")
        with open(mode_file, "w") as f:
            json.dump(result.to_full_dict(), f, indent=2, sort_keys=True)

    return result


def run_benchmark_demo() -> BenchResult:
    """Run a small demo subset of the benchmark (12 representative cases)."""
    all_cases = generate_all_cases()
    demo_ids = ["UA-001", "MV-001", "MP-001", "MK-001", "TB-001",
                "SD-001", "SD-002", "SF-001", "FP-001", "FN-001",
                "RG-001", "RG-004"]
    demo_cases = [c for c in all_cases if c.case_id in demo_ids]
    return run_benchmark(cases=demo_cases, mode="chipgate_only")


def compare_modes(
    cases: Optional[List[BenchCase]] = None,
    adapter=None,
    output_dir: Optional[str] = None,
    evidence: bool = False,
) -> ComparisonResult:
    """
    Run all three benchmark modes and compare results.

    Args:
        cases: List of BenchCase to run. If None, uses standard cases.
        adapter: Optional adapter for external_dtl mode.
        output_dir: Optional directory to save results.
        evidence: If True, generate evidence records.

    Returns:
        ComparisonResult with all three mode results.
    """
    if cases is None:
        cases = generate_all_cases()

    comparison = ComparisonResult(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )

    # Mode A: Ungated baseline
    comparison.modes["ungated_baseline"] = run_benchmark(
        cases=cases, mode="ungated_baseline",
        output_dir=output_dir, evidence=evidence,
    )

    # Mode B: ChipGate-only
    comparison.modes["chipgate_only"] = run_benchmark(
        cases=cases, mode="chipgate_only",
        output_dir=output_dir, evidence=evidence,
    )

    # Mode C: External DTL (if adapter provided)
    if adapter is not None:
        comparison.modes["external_dtl"] = run_benchmark(
            cases=cases, mode="external_dtl",
            adapter=adapter, output_dir=output_dir, evidence=evidence,
        )

    # Save comparison report
    if output_dir:
        comp_file = os.path.join(output_dir, "comparison_report.json")
        with open(comp_file, "w") as f:
            json.dump(comparison.to_dict(), f, indent=2, sort_keys=True)

    return comparison


# ── Evidence ──────────────────────────────────────────────────────────────────

def _save_case_evidence(
    case: BenchCase,
    cr: CaseResult,
    scan_result,
    tmp_dir: str,
):
    """Legacy evidence record (v0.2.0 compat)."""
    evidence = {
        "case_id": case.case_id,
        "category": case.category,
        "risk_level": case.risk_level,
        "input_hash": hashlib.sha256(case.rtl_after.encode()).hexdigest(),
        "gate_result": cr.gate_result,
        "expected_gate_result": cr.expected_gate_result,
        "gate_correct": cr.gate_correct,
        "statuses": cr.statuses,
        "heavy_check_decision": cr.heavy_check_decision,
        "regression_status": cr.regression_status,
        "certificate_hash": cr.certificate_hash,
        "replay_command": cr.replay_command,
        "findings_count": cr.findings_count,
        "public_wording": st.CHIPBENCH_PUBLIC_WORDING,
    }
    evidence_path = os.path.join(tmp_dir, f"{case.case_id}.evidence.json")
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2, sort_keys=True)


def _save_case_evidence_v2(
    case: BenchCase,
    cr: CaseResult,
    evidence_dir: str,
    benchmark_mode: str,
    adapter_name: str,
    proposal_source: str,
):
    """Save v0.3.0 evidence record with mode and adapter metadata."""
    evidence = {
        "benchmark_mode": benchmark_mode,
        "adapter_name": adapter_name,
        "proposal_source": proposal_source,
        "case_id": case.case_id,
        "category": case.category,
        "risk_level": case.risk_level,
        "proposal_id": cr.proposal_id,
        "input_hash": cr.input_hash,
        "output_hash": cr.output_hash,
        "gate_result": cr.gate_result,
        "expected_gate_result": cr.expected_gate_result,
        "gate_correct": cr.gate_correct,
        "statuses": cr.statuses,
        "heavy_check_decision": cr.heavy_check_decision,
        "no_regression_result": cr.regression_status,
        "cost_model_result": {
            "heavy_check_decision": cr.heavy_check_decision,
        },
        "certificate_hash": cr.certificate_hash,
        "replay_command": cr.replay_command,
        "findings_count": cr.findings_count,
        "adapter_route_label": cr.adapter_route_label,
        "adapter_reason": cr.adapter_reason,
        "public_wording": st.CHIPBENCH_PUBLIC_WORDING,
    }
    # Certificate hash for the evidence pack itself
    evidence["certificate_hash"] = hashlib.sha256(
        json.dumps(evidence, sort_keys=True).encode()
    ).hexdigest()

    evidence_path = os.path.join(evidence_dir, f"{cr.case_id}.evidence.json")
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2, sort_keys=True)


# ── Holdout Support ──────────────────────────────────────────────────────────

def _load_holdout_cases(holdout_dir: Optional[Path]) -> List[BenchCase]:
    """
    Load private holdout cases if the holdout directory exists.

    Holdout cases follow the same BenchCase format but are loaded from
    a separate directory that is not committed to the public repo.

    If the directory is missing, returns an empty list (skip cleanly).
    """
    if holdout_dir is None or not holdout_dir.exists():
        return []

    holdout_cases = []
    for v_file in sorted(holdout_dir.glob("*.v")):
        case_id = f"HOLDOUT-{v_file.stem}"
        rtl = v_file.read_text(encoding="utf-8")
        # Holdout cases are treated as "unknown" — no expected result
        holdout_cases.append(BenchCase(
            case_id=case_id,
            category="holdout",
            risk_level="unknown",
            rtl_before="",
            rtl_after=rtl,
            expected_gate_result="pass",  # Will be measured, not asserted
            expected_heavy_check_needed=True,
            reason="Private holdout case",
        ))

    return holdout_cases