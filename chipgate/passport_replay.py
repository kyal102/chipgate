"""DTL Verified Design Passport — Replay System.

Handles replay command generation, replay execution, and drift
detection for passport verification.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

from typing import Any, Dict

from .passport_schema import (
    PASSPORT_REPLAY_DRIFT,
    PASSPORT_REPLAY_MATCH,
)
from .passport_manifest import compute_certificate_hash, verify_passport


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def generate_replay_command(
    artifact_path: str = "",
    artifact_id: str = "",
    artifact_type: str = "",
    gates: list | None = None,
) -> str:
    """Generate a replay command string for a passport.

    The replay command is a deterministic, machine-readable string
    that describes how to reproduce the passport decision.  It uses
    only public CLI commands.

    Returns a command string like::

        python -m chipgate passport --artifact <path> --json
    """
    parts = ["python -m chipgate passport"]
    if artifact_path:
        parts.append(f"--artifact {artifact_path}")
    elif artifact_id:
        parts.append(f"--artifact {artifact_id}")
    else:
        parts.append("--demo")
    parts.append("--json")
    return " ".join(parts)


def replay_passport(passport_data: Dict[str, Any]) -> Dict[str, Any]:
    """Replay a passport by verifying its recorded evidence.

    Checks:
    1. Verify the passport structure (via verify_passport)
    2. Recompute the certificate hash
    3. Compare with recorded hash
    4. Determine if replay matches or drifts

    Returns:
        Dict with:
            replay_match: bool
            replay_status: str (PASSPORT_REPLAY_MATCH or PASSPORT_REPLAY_DRIFT)
            certificate_match: bool
            verification: dict (from verify_passport)
            errors: list
    """
    errors: list = []

    # 1. Verify structure
    verification = verify_passport(passport_data)
    if not verification["valid"]:
        errors.extend(verification["errors"])

    # 2. Recompute certificate hash
    recorded_hash = passport_data.get("certificate_hash", "")
    recomputed_hash = compute_certificate_hash(passport_data)
    cert_match = recorded_hash == recomputed_hash

    # 3. Check for drift
    # Drift is detected if:
    #   - Certificate hash doesn't match
    #   - Verification fails
    #   - Any gate results appear inconsistent
    gates_passed = passport_data.get("gates_passed", [])
    gates_failed = passport_data.get("gates_failed", [])
    gates_run = passport_data.get("gates_run", [])

    # Overlap between passed and failed is a drift indicator
    overlap = set(gates_passed) & set(gates_failed)
    if overlap:
        errors.append(f"Gate listed as both passed and failed: {overlap}")

    # Gates not in run list
    unexpected_passed = set(gates_passed) - set(gates_run)
    unexpected_failed = set(gates_failed) - set(gates_run)
    if unexpected_passed:
        errors.append(f"Gate passed but not in run list: {unexpected_passed}")
    if unexpected_failed:
        errors.append(f"Gate failed but not in run list: {unexpected_failed}")

    replay_match = cert_match and verification["valid"] and len(errors) == 0
    replay_status = PASSPORT_REPLAY_MATCH if replay_match else PASSPORT_REPLAY_DRIFT

    return {
        "replay_match": replay_match,
        "replay_status": replay_status,
        "certificate_match": cert_match,
        "verification": verification,
        "errors": errors,
    }


def check_replay_stability(passport_data: Dict[str, Any]) -> bool:
    """Check if a passport replay produces the same result.

    Convenience function that returns True if replay matches.
    """
    result = replay_passport(passport_data)
    return result["replay_match"]
