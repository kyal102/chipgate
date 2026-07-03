"""DTL Verified Design Passport — Passport Builder.

Assembles a complete passport by running the pipeline:
  artifact -> classification -> risk -> gates -> results -> evidence ->
  replay -> passport -> badge -> export decision

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .passport_schema import (
    ARTIFACT_UNKNOWN,
    BADGE_UNVERIFIED,
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    EVIDENCE_PACK_CREATED,
    EXPORT_NEEDS_REVIEW,
    PASSPORT_CREATED,
    PASSPORT_LIMITATION,
    PASSPORT_NEEDS_REVIEW,
    PASSPORT_PUBLIC_WORDING,
    RISK_UNKNOWN,
    SCHEMA_VERSION,
    PassportData,
    PassportMetrics,
)
from .passport_artifacts import (
    validate_artifact_intake,
    compute_artifact_hash,
    check_private_leak,
    check_unsafe_claims,
)
from .passport_policy import (
    classify_artifact_type,
    assign_risk_level,
    select_gates,
    compute_export_decision,
)
from .passport_manifest import (
    compute_certificate_hash,
    compute_dict_hash,
    build_manifest,
    verify_passport,
)
from .passport_replay import generate_replay_command
from .passport_badges import determine_badge, generate_badge_json


# ---------------------------------------------------------------------------
# Gate simulation (public demo — no real toolchain calls)
# ---------------------------------------------------------------------------


def _simulate_gate_run(gate_id: str, artifact_type: str, content: str) -> Dict[str, Any]:
    """Simulate running a single verification gate.

    This is a public demonstration only.  It does not call real
    toolchains.  Gate results are deterministic based on artifact type
    and content checks.

    Returns a dict with gate_id, passed, failed, reason.
    """
    # Private leak check blocks everything
    has_leak, _ = check_private_leak(content)
    if has_leak:
        return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "Private leak detected in artifact content"}

    # Unsafe claim check
    has_unsafe, _ = check_unsafe_claims(content)
    if has_unsafe:
        return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "Unsafe overclaim phrase detected"}

    # Gate-specific simulation
    if gate_id == "chipgate":
        if artifact_type in ("rtl", "soc_design", "code"):
            # Check for basic safety patterns
            if "kill_switch" in content or "failsafe" in content or "verifier" in content:
                return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "Safety gate patterns detected in artifact"}
            return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "No safety gate patterns detected"}
        return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "Non-RTL artifact, gate not applicable (pass by default)"}

    if gate_id == "claimgate":
        if content and len(content) > 10:
            return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "Claims present and structured"}
        return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "Insufficient claim content"}

    if gate_id == "claimlint":
        return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "Claim lint check passed"}

    if gate_id == "unitgate":
        return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "Unit gate check passed"}

    if gate_id == "elementgate":
        return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "Element gate check passed"}

    if gate_id == "evidencepack":
        if content:
            evidence_hash = compute_artifact_hash(content)
            return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "Evidence pack created", "evidence_hash": evidence_hash}
        return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "No content to create evidence pack from"}

    if gate_id == "replaygate":
        return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "Replay gate check passed"}

    if gate_id == "soc_safety":
        if "kill_switch" in content or "reset" in content:
            return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "SoC safety patterns detected"}
        return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "No SoC safety patterns detected"}

    if gate_id == "riscv_demo":
        if "riscv" in content.lower() or "coprocessor" in content.lower():
            return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "RISC-V patterns detected"}
        return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "No RISC-V patterns detected"}

    if gate_id == "asic_bench":
        if "asic" in content.lower() or "synthesis" in content.lower():
            return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "ASIC patterns detected"}
        return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "No ASIC patterns detected"}

    if gate_id == "dtl_accel":
        return {"gate_id": gate_id, "passed": True, "failed": False, "reason": "DTL accelerator check passed"}

    # Unknown gate
    return {"gate_id": gate_id, "passed": False, "failed": True, "reason": "Unknown gate"}


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_passport(
    artifact_id: str = "demo_artifact_001",
    file_path: str = "",
    content: str = "",
    adapter_input: Optional[Dict] = None,
    requested_gates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a complete passport for an artifact.

    Pipeline stages:
    1. Artifact intake and validation
    2. Artifact classification
    3. Risk level assignment
    4. Gate selection
    5. Gate result collection (simulated)
    6. Evidence pack creation
    7. Replay command generation
    8. Passport assembly
    9. Badge determination
    10. Export decision

    Returns a complete passport dict.
    """
    # ── 1. Artifact intake ────────────────────────────────────────────
    intake = validate_artifact_intake(
        file_path=file_path,
        content=content,
        adapter_input=adapter_input,
    )

    artifact_type = intake["artifact_type"]
    risk_level = intake["risk_level"]
    actual_content = intake["content"]
    artifact_hash = intake["artifact_hash"]
    has_private_leak = intake["private_leak"]
    has_unsafe_claims = intake["unsafe_claims"]
    intake_errors = intake["errors"]

    # ── 2-3. Classification and risk (already done in intake) ─────────

    # ── 4. Gate selection ────────────────────────────────────────────
    gates = select_gates(artifact_type, requested_gates)

    # ── 5. Gate results (simulated) ──────────────────────────────────
    gates_run: List[str] = []
    gates_passed: List[str] = []
    gates_failed: List[str] = []
    gate_results: List[Dict] = []
    evidence_packs: List[Dict[str, str]] = []
    manual_review_items: List[str] = []
    limitations: List[str] = [PASSPORT_LIMITATION]

    for gate_id in gates:
        result = _simulate_gate_run(gate_id, artifact_type, actual_content)
        gates_run.append(gate_id)
        gate_results.append(result)
        if result["passed"]:
            gates_passed.append(gate_id)
        if result["failed"]:
            gates_failed.append(gate_id)
        # Collect evidence hashes
        if "evidence_hash" in result:
            evidence_packs.append({
                "gate_id": gate_id,
                "evidence_hash": result["evidence_hash"],
            })

    # ── 6. Evidence pack ─────────────────────────────────────────────
    if evidence_packs:
        limitations.append(EVIDENCE_PACK_CREATED)

    # ── 7. Replay command ────────────────────────────────────────────
    replay_cmd = generate_replay_command(
        artifact_path=file_path,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        gates=gates,
    )

    # ── 8. Passport assembly ─────────────────────────────────────────
    passport_id = f"passport-{artifact_id}"
    created_at = datetime.now(timezone.utc).isoformat()

    # Build artifact hashes dict
    artifact_hashes: Dict[str, str] = {}
    if artifact_hash:
        artifact_hashes["artifact_content"] = artifact_hash
    for ep in evidence_packs:
        artifact_hashes[f"evidence_{ep['gate_id']}"] = ep["evidence_hash"]

    # Determine passport status
    if has_private_leak:
        passport_status = "PASSPORT_PRIVATE_LEAK_BLOCKED"
    elif has_unsafe_claims:
        passport_status = "PASSPORT_UNSAFE_CLAIM_BLOCKED"
    elif not gates:
        passport_status = "PASSPORT_UNSUPPORTED_ARTIFACT"
    elif not evidence_packs and gates:
        passport_status = "PASSPORT_MISSING_EVIDENCE"
    elif gates_failed:
        passport_status = "PASSPORT_NEEDS_REVIEW"
    else:
        passport_status = "PASSPORT_CHECKED"

    # ── 9. Export decision ────────────────────────────────────────────
    export_decision = compute_export_decision(
        risk_level=risk_level,
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        gates_requested=gates,
        missing_evidence=(not evidence_packs and bool(gates)),
        private_leak=has_private_leak,
        unsafe_claim=has_unsafe_claims,
    )

    # ── 10. Badge ────────────────────────────────────────────────────
    badge = determine_badge(passport_status, export_decision)

    # Collect manual review items
    if risk_level in ("HIGH", "SAFETY_CRITICAL"):
        manual_review_items.append(f"{risk_level} risk artifact requires human review")
    if has_private_leak:
        manual_review_items.append("Private leak detected — blocked until resolved")
    if has_unsafe_claims:
        manual_review_items.append("Unsafe claim phrases detected — blocked until resolved")
    for err in intake_errors:
        if err not in manual_review_items:
            manual_review_items.append(err)

    # Assemble passport data
    passport_data: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "passport_id": passport_id,
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "artifact_hash": artifact_hash,
        "risk_level": risk_level,
        "created_at": created_at,
        "gates_requested": gates,
        "gates_run": gates_run,
        "gates_passed": gates_passed,
        "gates_failed": gates_failed,
        "evidence_packs": evidence_packs,
        "artifact_hashes": artifact_hashes,
        "replay_command": replay_cmd,
        "passport_status": passport_status,
        "export_decision": export_decision,
        "limitations": limitations,
        "badge": badge,
        "manual_review_items": manual_review_items,
        "public_wording": PASSPORT_PUBLIC_WORDING,
    }

    # Compute certificate hash
    passport_data["certificate_hash"] = compute_certificate_hash(passport_data)

    # Generate badge data
    passport_hash = compute_dict_hash({
        k: passport_data[k] for k in [
            "passport_id", "artifact_id", "artifact_type",
            "risk_level", "passport_status", "export_decision", "badge",
        ]
    })
    badge_reason = _badge_reason(badge, passport_status, export_decision, risk_level)
    badge_data = generate_badge_json(artifact_id, badge, badge_reason, passport_hash)

    return {
        "passport": passport_data,
        "badge": badge_data,
        "gate_results": gate_results,
        "metrics": _compute_metrics(passport_data, gate_results),
    }


def _badge_reason(badge: str, status: str, export: str, risk: str) -> str:
    """Generate a human-readable reason for the badge."""
    if badge == "BLOCKED":
        return f"Artifact blocked: status={status}, export={export}"
    if badge == "NEEDS_REVIEW":
        return f"{risk} risk artifact requires review before export."
    if badge == "REPLAYABLE":
        return "Passport is verified and replayable."
    if badge == "CHECKED":
        return "All configured gates passed."
    if badge == "MISSING_EVIDENCE":
        return "Evidence pack is missing for one or more gates."
    if badge == "EXTERNAL_REVIEW_PENDING":
        return "External review is pending."
    return "Passport has not been fully verified."


def _compute_metrics(passport_data: Dict, gate_results: List[Dict]) -> Dict[str, int]:
    """Compute aggregate metrics from a passport build."""
    return {
        "artifacts_checked": 1,
        "passports_created": 1,
        "passports_verified": 0,
        "passports_tampered": 0,
        "badges_created": 1,
        "gates_requested": len(passport_data.get("gates_requested", [])),
        "gates_run": len(passport_data.get("gates_run", [])),
        "gates_passed": len(passport_data.get("gates_passed", [])),
        "gates_failed": len(passport_data.get("gates_failed", [])),
        "evidence_packs_attached": len(passport_data.get("evidence_packs", [])),
        "replay_matches": 0,
        "replay_drifts": 0,
        "exports_allowed": 1 if passport_data.get("export_decision") == "EXPORT_ALLOWED" else 0,
        "exports_blocked": 1 if passport_data.get("export_decision") == "EXPORT_BLOCKED" else 0,
        "exports_needing_review": 1 if passport_data.get("export_decision") == "EXPORT_NEEDS_REVIEW" else 0,
        "manual_review_items": len(passport_data.get("manual_review_items", [])),
        "private_leaks_blocked": 1 if "PASSPORT_PRIVATE_LEAK_BLOCKED" in passport_data.get("passport_status", "") else 0,
        "unsafe_claims_blocked": 1 if "PASSPORT_UNSAFE_CLAIM_BLOCKED" in passport_data.get("passport_status", "") else 0,
        "artifact_hash_count": len(passport_data.get("artifact_hashes", {})),
    }
