"""DTL Verified Design Passport — Badge System.

Generates badge data structures and optional SVG badge images.
Badges are labels only and do not constitute certifications.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

from typing import Dict

from .passport_schema import (
    BADGE_BLOCKED,
    BADGE_CHECKED,
    BADGE_EXTERNAL_REVIEW_PENDING,
    BADGE_MISSING_EVIDENCE,
    BADGE_NEEDS_REVIEW,
    BADGE_REPLAYABLE,
    BADGE_UNVERIFIED,
    EXPORT_BLOCKED,
    EXPORT_NEEDS_REVIEW,
    EXPORT_UNSUPPORTED,
    PASSPORT_BLOCKED,
    PASSPORT_CHECKED,
    PASSPORT_CREATED,
    PASSPORT_EXTERNAL_REVIEW_PENDING,
    PASSPORT_MISSING_EVIDENCE,
    PASSPORT_NEEDS_REVIEW,
    PASSPORT_PRIVATE_LEAK_BLOCKED,
    PASSPORT_REPLAY_DRIFT,
    PASSPORT_REPLAY_MATCH,
    PASSPORT_TAMPERED,
    PASSPORT_UNSAFE_CLAIM_BLOCKED,
    PASSPORT_UNSUPPORTED_ARTIFACT,
    PASSPORT_VERIFIED,
)


# ---------------------------------------------------------------------------
# Badge color map (for SVG rendering)
# ---------------------------------------------------------------------------

BADGE_COLORS: Dict[str, str] = {
    BADGE_UNVERIFIED: "#999999",
    BADGE_CHECKED: "#4CAF50",
    BADGE_BLOCKED: "#F44336",
    BADGE_NEEDS_REVIEW: "#FF9800",
    BADGE_REPLAYABLE: "#2196F3",
    BADGE_MISSING_EVIDENCE: "#FF5722",
    BADGE_EXTERNAL_REVIEW_PENDING: "#9C27B0",
}


# ---------------------------------------------------------------------------
# Status-to-badge mapping
# ---------------------------------------------------------------------------

STATUS_TO_BADGE: Dict[str, str] = {
    PASSPORT_VERIFIED: BADGE_CHECKED,
    PASSPORT_REPLAY_MATCH: BADGE_REPLAYABLE,
    PASSPORT_CHECKED: BADGE_CHECKED,
    PASSPORT_BLOCKED: BADGE_BLOCKED,
    PASSPORT_NEEDS_REVIEW: BADGE_NEEDS_REVIEW,
    PASSPORT_UNSUPPORTED_ARTIFACT: BADGE_UNVERIFIED,
    PASSPORT_MISSING_EVIDENCE: BADGE_MISSING_EVIDENCE,
    PASSPORT_PRIVATE_LEAK_BLOCKED: BADGE_BLOCKED,
    PASSPORT_UNSAFE_CLAIM_BLOCKED: BADGE_BLOCKED,
    PASSPORT_EXTERNAL_REVIEW_PENDING: BADGE_EXTERNAL_REVIEW_PENDING,
    PASSPORT_TAMPERED: BADGE_BLOCKED,
    PASSPORT_REPLAY_DRIFT: BADGE_NEEDS_REVIEW,
    PASSPORT_CREATED: BADGE_UNVERIFIED,
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def determine_badge(passport_status: str, export_decision: str = "") -> str:
    """Determine the badge type from passport status and export decision.

    Priority order:
    1. Direct status-to-badge mapping
    2. Export decision fallback (blocked -> BLOCKED, unsupported -> UNVERIFIED)
    3. Default: UNVERIFIED
    """
    # Direct mapping
    if passport_status in STATUS_TO_BADGE:
        return STATUS_TO_BADGE[passport_status]

    # Export decision fallback
    if export_decision == EXPORT_BLOCKED:
        return BADGE_BLOCKED
    if export_decision == EXPORT_UNSUPPORTED:
        return BADGE_UNVERIFIED
    if export_decision == EXPORT_NEEDS_REVIEW:
        return BADGE_NEEDS_REVIEW

    return BADGE_UNVERIFIED


def generate_badge_json(artifact_id: str, badge: str, reason: str, passport_hash: str) -> Dict[str, str]:
    """Generate a badge JSON structure.

    Returns a dict matching the badge JSON schema.
    """
    return {
        "artifact_id": artifact_id,
        "badge": badge,
        "reason": reason,
        "passport_hash": passport_hash,
    }


def generate_badge_svg(badge: str, artifact_id: str = "", width: int = 180, height: int = 28) -> str:
    """Generate a simple SVG badge image.

    The SVG is self-contained and uses no external dependencies.
    Badge colors are drawn from BADGE_COLORS.
    """
    color = BADGE_COLORS.get(badge, "#999999")
    label = badge.replace("_", " ").title()
    text_color = "#FFFFFF"

    # Calculate text positioning
    text_x = width // 2
    text_y = height // 2 + 5

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" rx="4" ry="4" fill="{color}"/>'
        f'<text x="{text_x}" y="{text_y}" font-family="sans-serif" '
        f'font-size="12" fill="{text_color}" text-anchor="middle">{label}</text>'
        f'</svg>'
    )
    return svg
