"""DTL Verified Design Passport — Policy Engine.

Handles risk level assignment, gate selection based on artifact type,
export policy decisions, and validation rules.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .passport_schema import (
    ALL_ARTIFACT_TYPES,
    ARTIFACT_ASIC_REVIEW_PACK,
    ARTIFACT_CHEMISTRY_FORMULA,
    ARTIFACT_CLAIM_SET,
    ARTIFACT_CODE,
    ARTIFACT_DOCUMENT,
    ARTIFACT_PHYSICS_EQUATION,
    ARTIFACT_RISCV_TRACE,
    ARTIFACT_RTL,
    ARTIFACT_ROBOTICS_CONTROL_DEMO,
    ARTIFACT_SOC_DESIGN,
    ARTIFACT_SUPPLY_CHAIN_POLICY_DEMO,
    ARTIFACT_UNKNOWN,
    EXPORT_BLOCKED,
    EXPORT_NEEDS_REVIEW,
    EXPORT_UNSUPPORTED,
    GATE_ASIC_BENCH,
    GATE_CHIPGATE,
    GATE_CLAIMGATE,
    GATE_CLAIMLINT,
    GATE_DTL_ACCEL,
    GATE_ELEMENTGATE,
    GATE_EVIDENCEPACK,
    GATE_RISCV_DEMO,
    GATE_REPLAYGATE,
    GATE_SOC_SAFETY,
    GATE_UNITGATE,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_SAFETY_CRITICAL,
    RISK_UNKNOWN,
)


# ---------------------------------------------------------------------------
# Artifact type to risk level mapping
# ---------------------------------------------------------------------------

ARTIFACT_RISK_MAP: Dict[str, str] = {
    ARTIFACT_DOCUMENT: RISK_LOW,
    ARTIFACT_CLAIM_SET: RISK_LOW,
    ARTIFACT_CODE: RISK_MEDIUM,
    ARTIFACT_RTL: RISK_HIGH,
    ARTIFACT_RISCV_TRACE: RISK_HIGH,
    ARTIFACT_SOC_DESIGN: RISK_HIGH,
    ARTIFACT_ASIC_REVIEW_PACK: RISK_HIGH,
    ARTIFACT_ROBOTICS_CONTROL_DEMO: RISK_SAFETY_CRITICAL,
    ARTIFACT_SUPPLY_CHAIN_POLICY_DEMO: RISK_MEDIUM,
    ARTIFACT_PHYSICS_EQUATION: RISK_MEDIUM,
    ARTIFACT_CHEMISTRY_FORMULA: RISK_MEDIUM,
    ARTIFACT_UNKNOWN: RISK_UNKNOWN,
}


# ---------------------------------------------------------------------------
# Artifact type to gate mapping
# ---------------------------------------------------------------------------

ARTIFACT_GATE_MAP: Dict[str, List[str]] = {
    ARTIFACT_DOCUMENT: [GATE_CLAIMGATE, GATE_CLAIMLINT, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_CLAIM_SET: [GATE_CLAIMGATE, GATE_CLAIMLINT, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_CODE: [GATE_CHIPGATE, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_RTL: [GATE_CHIPGATE, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_RISCV_TRACE: [GATE_RISCV_DEMO, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_SOC_DESIGN: [GATE_SOC_SAFETY, GATE_CHIPGATE, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_ASIC_REVIEW_PACK: [GATE_ASIC_BENCH, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_ROBOTICS_CONTROL_DEMO: [GATE_CHIPGATE, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_SUPPLY_CHAIN_POLICY_DEMO: [GATE_CLAIMGATE, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_PHYSICS_EQUATION: [GATE_UNITGATE, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_CHEMISTRY_FORMULA: [GATE_ELEMENTGATE, GATE_EVIDENCEPACK, GATE_REPLAYGATE],
    ARTIFACT_UNKNOWN: [],
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def assign_risk_level(artifact_type: str) -> str:
    """Assign a risk level based on artifact type.

    If the artifact type is not recognised, returns RISK_UNKNOWN.
    """
    return ARTIFACT_RISK_MAP.get(artifact_type, RISK_UNKNOWN)


def select_gates(artifact_type: str, requested_gates: List[str] | None = None) -> List[str]:
    """Select which verification gates to run for a given artifact type.

    If the caller requests specific gates, those are used if they are
    recognised.  Otherwise the default gate set for the artifact type
    is returned.

    An unknown artifact type returns an empty list (no gates selected).
    """
    if requested_gates:
        return [g for g in requested_gates if g in {
            GATE_CHIPGATE, GATE_EVIDENCEPACK, GATE_REPLAYGATE,
            GATE_CLAIMGATE, GATE_CLAIMLINT, GATE_UNITGATE,
            GATE_ELEMENTGATE, GATE_SOC_SAFETY, GATE_RISCV_DEMO,
            GATE_ASIC_BENCH, GATE_DTL_ACCEL,
        }]
    return list(ARTIFACT_GATE_MAP.get(artifact_type, []))


def compute_export_decision(
    risk_level: str,
    gates_passed: List[str],
    gates_failed: List[str],
    gates_requested: List[str],
    missing_evidence: bool = False,
    private_leak: bool = False,
    unsafe_claim: bool = False,
) -> str:
    """Compute the export decision based on policy rules.

    Rules (evaluated in priority order):

    1. Private leak detected: EXPORT_BLOCKED
    2. Unsafe claim detected: EXPORT_BLOCKED
    3. Unsupported / unknown artifact type with no gates: EXPORT_UNSUPPORTED
    4. Safety-critical with any failed gate: EXPORT_BLOCKED
    5. Safety-critical: EXPORT_NEEDS_REVIEW
    6. High risk with failed gates: EXPORT_BLOCKED
    7. High risk: EXPORT_NEEDS_REVIEW
    8. Missing evidence: EXPORT_NEEDS_REVIEW
    9. Failed gate present: EXPORT_BLOCKED
    10. Low risk, all gates passed: EXPORT_ALLOWED
    11. Medium risk, all gates passed: EXPORT_NEEDS_REVIEW
    12. Default: EXPORT_NEEDS_REVIEW

    Returns one of the EXPORT_* constants.
    """
    # 1. Private leak
    if private_leak:
        return EXPORT_BLOCKED

    # 2. Unsafe claim
    if unsafe_claim:
        return EXPORT_BLOCKED

    # 3. No gates at all
    if not gates_requested and not gates_passed and not gates_failed:
        return EXPORT_UNSUPPORTED

    # 4. Safety-critical with any failure
    if risk_level == RISK_SAFETY_CRITICAL and gates_failed:
        return EXPORT_BLOCKED

    # 5. Safety-critical always needs review
    if risk_level == RISK_SAFETY_CRITICAL:
        return EXPORT_NEEDS_REVIEW

    # 6. High risk with failures
    if risk_level == RISK_HIGH and gates_failed:
        return EXPORT_BLOCKED

    # 7. High risk defaults to review
    if risk_level == RISK_HIGH:
        return EXPORT_NEEDS_REVIEW

    # 8. Missing evidence
    if missing_evidence:
        return EXPORT_NEEDS_REVIEW

    # 9. Failed gate present
    if gates_failed:
        return EXPORT_BLOCKED

    # 10. Low risk, all passed
    if risk_level == RISK_LOW and gates_passed and not gates_failed:
        return EXPORT_NEEDS_REVIEW  # conservative default

    # 11. Medium risk, all passed
    if risk_level == RISK_MEDIUM and gates_passed and not gates_failed:
        return EXPORT_NEEDS_REVIEW

    # 12. Default
    return EXPORT_NEEDS_REVIEW


def classify_artifact_type(file_path: str = "", content: str = "", adapter_type: str = "") -> str:
    """Classify an artifact into one of the known artifact types.

    Classification is conservative: if the type cannot be determined
    with confidence, ARTIFACT_UNKNOWN is returned.

    Priority:
    1. Adapter-specified type (if valid)
    2. File extension heuristic
    3. Content heuristic
    4. Default to unknown
    """
    # 1. Adapter-specified type
    if adapter_type and adapter_type in ALL_ARTIFACT_TYPES:
        return adapter_type

    # 2. File extension heuristic
    if file_path:
        fl = file_path.lower()
        if fl.endswith(".v") or fl.endswith(".sv") or fl.endswith(".vh"):
            return ARTIFACT_RTL
        if fl.endswith(".jsonl") and "riscv" in fl:
            return ARTIFACT_RISCV_TRACE
        if fl.endswith(".json") and "asic" in fl:
            return ARTIFACT_ASIC_REVIEW_PACK
        if fl.endswith(".md") or fl.endswith(".txt"):
            return ARTIFACT_DOCUMENT
        if fl.endswith(".py") or fl.endswith(".js") or fl.endswith(".c"):
            return ARTIFACT_CODE

    # 3. Content heuristic
    if content:
        lower = content.lower()
        if "module " in lower and "endmodule" in lower and "input " in lower and "output " in lower:
            return ARTIFACT_RTL
        if "claim" in lower and ("verify" in lower or "evidence" in lower):
            return ARTIFACT_CLAIM_SET
        if "physics" in lower or "equation" in lower or "force" in lower:
            return ARTIFACT_PHYSICS_EQUATION
        if "chemistry" in lower or "molecule" in lower or "reaction" in lower:
            return ARTIFACT_CHEMISTRY_FORMULA

    # 4. Default
    return ARTIFACT_UNKNOWN
