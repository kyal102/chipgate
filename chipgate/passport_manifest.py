"""DTL Verified Design Passport — Manifest and Hashing.

Handles passport manifest creation, verification, certificate hashing,
and tamper detection.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from .passport_schema import (
    PASSPORT_TAMPERED,
    PASSPORT_VERIFIED,
    REQUIRED_PASSPORT_FIELDS,
    SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Hashing utilities
# ---------------------------------------------------------------------------


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of a string.

    Returns ``sha256:<hex_digest>``.
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_dict_hash(data: Dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of a JSON-serialisable dict.

    Keys are sorted for determinism.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return compute_hash(canonical)


def compute_certificate_hash(passport_data: Dict[str, Any]) -> str:
    """Compute the certificate hash for a passport.

    The certificate hash covers the essential immutable fields of
    the passport: schema_version, passport_id, artifact_id,
    artifact_type, risk_level, gates_passed, gates_failed,
    passport_status, export_decision, and replay_command.
    """
    covered = {
        "schema_version": passport_data.get("schema_version", ""),
        "passport_id": passport_data.get("passport_id", ""),
        "artifact_id": passport_data.get("artifact_id", ""),
        "artifact_type": passport_data.get("artifact_type", ""),
        "risk_level": passport_data.get("risk_level", ""),
        "gates_passed": sorted(passport_data.get("gates_passed", [])),
        "gates_failed": sorted(passport_data.get("gates_failed", [])),
        "passport_status": passport_data.get("passport_status", ""),
        "export_decision": passport_data.get("export_decision", ""),
        "replay_command": passport_data.get("replay_command", ""),
    }
    return compute_dict_hash(covered)


# ---------------------------------------------------------------------------
# Manifest creation
# ---------------------------------------------------------------------------


def build_manifest(
    passport_data: Dict[str, Any],
    artifact_hashes: Dict[str, str],
    evidence_pack_hashes: Dict[str, str],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a passport manifest with all hashes and metadata.

    Returns a dict suitable for serialisation to JSON.
    """
    cert_hash = compute_certificate_hash(passport_data)
    passport_data["certificate_hash"] = cert_hash

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "passport_id": passport_data.get("passport_id", ""),
        "artifact_id": passport_data.get("artifact_id", ""),
        "artifact_type": passport_data.get("artifact_type", ""),
        "risk_level": passport_data.get("risk_level", ""),
        "passport_status": passport_data.get("passport_status", ""),
        "export_decision": passport_data.get("export_decision", ""),
        "badge": passport_data.get("badge", ""),
        "certificate_hash": cert_hash,
        "artifact_hashes": artifact_hashes,
        "evidence_pack_hashes": evidence_pack_hashes,
        "limitations": passport_data.get("limitations", []),
        "public_wording": passport_data.get("public_wording", ""),
    }
    if extra:
        manifest.update(extra)
    return manifest


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_passport(passport_data: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a passport for completeness and integrity.

    Checks:
    - Schema version is present and correct
    - All required fields are present
    - Certificate hash matches recomputed hash
    - No tampering detected
    - No unsafe claim wording
    - No private leak patterns
    - Replay command exists

    Returns:
        Dict with:
            valid: bool
            status: str (PASSPORT_VERIFIED or PASSPORT_TAMPERED)
            errors: list of error descriptions
            certificate_match: bool
    """
    errors: List[str] = []

    # 1. Schema version
    sv = passport_data.get("schema_version", "")
    if sv != SCHEMA_VERSION:
        errors.append(f"Wrong schema version: '{sv}', expected '{SCHEMA_VERSION}'")

    # 2. Required fields
    for field_name in REQUIRED_PASSPORT_FIELDS:
        if field_name not in passport_data:
            errors.append(f"Missing required field: {field_name}")

    # 3. Certificate hash
    recorded_hash = passport_data.get("certificate_hash", "")
    recomputed_hash = compute_certificate_hash(passport_data)
    cert_match = recorded_hash == recomputed_hash
    if not cert_match and recorded_hash:
        errors.append("Certificate hash mismatch: passport may have been tampered with")

    # 4. Replay command
    if not passport_data.get("replay_command", ""):
        errors.append("Missing replay command")

    # 5. Check for private leaks in the serialized form
    passport_str = json.dumps(passport_data, sort_keys=True)
    from .passport_schema import PRIVATE_PATTERNS, FORBIDDEN_PHRASES
    for pattern in PRIVATE_PATTERNS:
        if pattern.lower() in passport_str.lower():
            errors.append(f"Private leak pattern detected: {pattern}")
    for phrase in FORBIDDEN_PHRASES:
        if phrase in passport_str:
            errors.append(f"Forbidden overclaim phrase detected: {phrase}")

    valid = len(errors) == 0 and cert_match
    status = PASSPORT_VERIFIED if valid else PASSPORT_TAMPERED

    return {
        "valid": valid,
        "status": status,
        "errors": errors,
        "certificate_match": cert_match,
    }


def load_passport_from_file(file_path: str) -> Dict[str, Any]:
    """Load a passport from a JSON file.

    Returns an empty dict if the file cannot be read or parsed.
    """
    if not file_path or not os.path.isfile(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError, PermissionError):
        return {}


def save_passport_to_file(passport_data: Dict[str, Any], file_path: str) -> bool:
    """Save a passport dict to a JSON file.

    Returns True on success, False on failure.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(passport_data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        return True
    except (OSError, PermissionError, TypeError):
        return False
