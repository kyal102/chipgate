"""DTL Verified Design Passport — Artifact Intake and Classification.

Handles artifact intake validation, private leak detection, content
reading, and classification.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional, Tuple

from .passport_schema import (
    PASSPORT_PRIVATE_LEAK_BLOCKED,
    PASSPORT_UNSAFE_CLAIM_BLOCKED,
    PRIVATE_PATTERNS,
)
from .passport_policy import classify_artifact_type, assign_risk_level


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def compute_artifact_hash(content: str) -> str:
    """Compute SHA-256 hash of artifact content.

    Returns a string of the form ``sha256:<hex_digest>``.
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_artifact_hash_file(file_path: str) -> str:
    """Compute SHA-256 hash of a file.

    Returns a string of the form ``sha256:<hex_digest>``.
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def read_artifact_content(file_path: str) -> str:
    """Read artifact content from a file path.

    Returns empty string if the file does not exist or cannot be read.
    Only reads text files (not binary).
    """
    if not file_path or not os.path.isfile(file_path):
        return ""
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (UnicodeDecodeError, PermissionError, OSError):
        return ""


def check_private_leak(content: str) -> Tuple[bool, List[str]]:
    """Check content for private JARVI3/DTL patterns.

    Returns:
        Tuple of (has_leak: bool, matched_patterns: list)
    """
    if not content:
        return False, []
    lower = content.lower()
    matched = [p for p in PRIVATE_PATTERNS if p.lower() in lower]
    return len(matched) > 0, matched


def check_unsafe_claims(content: str) -> Tuple[bool, List[str]]:
    """Check content for unsafe overclaim phrases.

    Returns:
        Tuple of (has_unsafe: bool, matched_phrases: list)
    """
    from .passport_schema import FORBIDDEN_PHRASES
    if not content:
        return False, []
    matched = [p for p in FORBIDDEN_PHRASES if p in content]
    return len(matched) > 0, matched


def check_no_absolute_local_path(content: str) -> bool:
    """Check that content does not contain absolute local paths."""
    if not content:
        return True
    import re
    pattern = r"/(home|users|tmp|var)/[\w/]+"
    matches = re.findall(pattern, content, re.IGNORECASE)
    return len(matches) == 0


def check_english_only(content: str) -> bool:
    """Check that content contains only ASCII/printable English text.

    Allows common punctuation and whitespace. Returns True if the
    content appears to be English-only.
    """
    if not content:
        return True
    try:
        content.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def validate_artifact_intake(
    file_path: str = "",
    content: str = "",
    adapter_input: Optional[Dict] = None,
) -> Dict:
    """Validate an artifact at intake time.

    Checks:
    - Artifact exists (if file path given)
    - No private paths
    - No secrets
    - No private JARVI3 names
    - No private DTL internals
    - No unsupported binary artifacts

    Returns a dict with:
        valid: bool
        artifact_type: str
        risk_level: str
        content: str
        artifact_hash: str
        private_leak: bool
        private_leak_patterns: list
        unsafe_claims: bool
        unsafe_claim_phrases: list
        errors: list
    """
    errors: List[str] = []
    artifact_type = ""
    risk_level = ""
    actual_content = content

    # Determine content source
    if adapter_input and isinstance(adapter_input, dict):
        adapter_type = adapter_input.get("artifact_type", "")
        adapter_path = adapter_input.get("artifact_path", "")
        if adapter_path and os.path.isfile(adapter_path):
            actual_content = read_artifact_content(adapter_path)
        artifact_type = classify_artifact_type(
            file_path=adapter_path, content=actual_content, adapter_type=adapter_type
        )
    elif file_path and os.path.isfile(file_path):
        actual_content = read_artifact_content(file_path)
        artifact_type = classify_artifact_type(file_path=file_path, content=actual_content)
    elif content:
        artifact_type = classify_artifact_type(content=actual_content)
    else:
        errors.append("No artifact content or file path provided")
        artifact_type = "unknown"

    # Assign risk level
    risk_level = assign_risk_level(artifact_type)

    # Compute hash
    artifact_hash = compute_artifact_hash(actual_content) if actual_content else ""

    # Private leak check
    has_private_leak, private_patterns = check_private_leak(actual_content)
    if has_private_leak:
        errors.append(f"Private leak detected: {', '.join(private_patterns)}")

    # Unsafe claim check
    has_unsafe_claims, unsafe_phrases = check_unsafe_claims(actual_content)
    if has_unsafe_claims:
        errors.append(f"Unsafe claim detected: {', '.join(unsafe_phrases)}")

    # Absolute local path check
    if not check_no_absolute_local_path(actual_content):
        errors.append("Absolute local path detected in content")

    # English only check
    if not check_english_only(actual_content):
        errors.append("Non-English content detected")

    return {
        "valid": len(errors) == 0,
        "artifact_type": artifact_type,
        "risk_level": risk_level,
        "content": actual_content,
        "artifact_hash": artifact_hash,
        "private_leak": has_private_leak,
        "private_leak_patterns": private_patterns,
        "unsafe_claims": has_unsafe_claims,
        "unsafe_claim_phrases": unsafe_phrases,
        "errors": errors,
    }
