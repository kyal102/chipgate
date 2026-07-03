"""
ChipGate no-regression checker.

Compares a proposed RTL change against a known safe baseline to detect
whether the change introduces a regression (removes required gates,
removes reset, removes kill_switch, etc.).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set

from .scanner import scan_file, ScanResult


@dataclass
class RegressionResult:
    """Result of a regression check."""
    case_id: str
    is_regression: bool
    status: str  # REGRESSION_DETECTED or NO_REGRESSION_PASS
    removed_gates: List[str] = field(default_factory=list)
    added_gates: List[str] = field(default_factory=list)
    removed_features: List[str] = field(default_factory=list)
    detail: str = ""


def check_regression(
    baseline_rtl: str,
    proposed_rtl: str,
    case_id: str,
    tmp_dir: str = "/tmp/chipbench_regressions",
) -> RegressionResult:
    """
    Compare a proposed RTL design against a baseline.

    Writes both to temp files, scans each, then compares the
    gate coverage and safety features.
    """
    import os
    import tempfile

    os.makedirs(tmp_dir, exist_ok=True)

    # Write baseline
    base_path = os.path.join(tmp_dir, f"{case_id}_baseline.v")
    with open(base_path, "w") as f:
        f.write(baseline_rtl)

    # Write proposed
    prop_path = os.path.join(tmp_dir, f"{case_id}_proposed.v")
    with open(prop_path, "w") as f:
        f.write(proposed_rtl)

    base_result = scan_file(base_path, generate_replay=False)
    prop_result = scan_file(prop_path, generate_replay=False)

    return _compare_results(case_id, base_result, prop_result)


def check_regression_from_results(
    case_id: str,
    baseline_result: ScanResult,
    proposed_result: ScanResult,
) -> RegressionResult:
    """Compare two already-computed scan results for regression."""
    return _compare_results(case_id, baseline_result, proposed_result)


def _compare_results(
    case_id: str,
    baseline: ScanResult,
    proposed: ScanResult,
) -> RegressionResult:
    """Core comparison logic."""
    from . import statuses as st

    removed_gates = []
    added_gates = []
    removed_features = []
    is_regression = False

    # Check if baseline had SAFETY_GATE_PRESENT but proposed does not
    base_has_gate = st.SAFETY_GATE_PRESENT in baseline.statuses
    prop_has_gate = st.SAFETY_GATE_PRESENT in proposed.statuses

    if base_has_gate and not prop_has_gate:
        removed_gates.append("safety_gate_chain")
        is_regression = True

    # Check for UNGATED_OUTPUT appearing in proposed but not baseline
    base_ungated = st.UNGATED_OUTPUT in baseline.statuses
    prop_ungated = st.UNGATED_OUTPUT in proposed.statuses

    if not base_ungated and prop_ungated:
        removed_gates.append("actuator_gating")
        is_regression = True

    # Compare risky signals
    base_risky = set(baseline.risky_signals)
    prop_risky = set(proposed.risky_signals)
    new_risky = prop_risky - base_risky
    if new_risky:
        removed_features.append(f"new_risky_signals: {', '.join(sorted(new_risky))}")
        is_regression = True

    # Check if baseline passed but proposed fails
    base_pass = st.RTL_SCAN_PASS in baseline.statuses
    prop_pass = st.RTL_SCAN_PASS in proposed.statuses
    if base_pass and not prop_pass:
        removed_features.append("overall_scan_pass")
        is_regression = True

    # Check for new critical findings in proposed
    base_critical = {f.rule_id for f in baseline.findings if f.severity == "critical"}
    prop_critical = {f.rule_id for f in proposed.findings if f.severity == "critical"}
    new_critical = prop_critical - base_critical
    if new_critical:
        removed_features.append(f"new_critical_findings: {', '.join(sorted(new_critical))}")
        is_regression = True

    # Check for improvement (gates added)
    if not base_has_gate and prop_has_gate:
        added_gates.append("safety_gate_chain")

    if base_ungated and not prop_ungated:
        added_gates.append("actuator_gating")

    status = st.REGRESSION_DETECTED if is_regression else st.NO_REGRESSION_PASS

    detail = ""
    if is_regression:
        parts = []
        if removed_gates:
            parts.append(f"Removed gates: {', '.join(removed_gates)}")
        if removed_features:
            parts.append(f"Issues: {'; '.join(removed_features)}")
        detail = "; ".join(parts)
    elif added_gates:
        detail = f"Improvement detected: {', '.join(added_gates)}"
    else:
        detail = "No change in safety status"

    return RegressionResult(
        case_id=case_id,
        is_regression=is_regression,
        status=status,
        removed_gates=removed_gates,
        added_gates=added_gates,
        removed_features=removed_features,
        detail=detail,
    )