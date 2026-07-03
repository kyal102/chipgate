"""
ChipGate MutationBench — Mutation category catalog.

Provides metadata about each mutation category: name, description,
criticality level, and category grouping.

Does not guarantee silicon correctness, fabrication readiness,
timing signoff, physical safety, real power or real area.
"""

from typing import Any, Dict, List, Optional

from .mutators import MUTATION_CATALOG


# Category metadata
CATEGORY_META: Dict[str, Dict[str, Any]] = {}

CRITICAL_CATEGORIES = {
    "remove_verifier_gate",
    "remove_policy_gate",
    "remove_sensor_gate",
    "direct_actuator_bypass",
    "or_bypass",
    "failsafe_escape",
    "blocked_escape",
    "unsafe_pin_exposure",
}

SAFETY_CATEGORIES = {
    "invert_kill_switch",
    "remove_timeout_block",
    "remove_reset_block",
    "glitchy_reset",
}

STRUCTURAL_CATEGORIES = {
    "stale_verifier",
    "shadow_signal",
    "obfuscated_expression",
    "multiline_bypass",
    "duplicate_assignment",
    "unsafe_default_state",
    "missing_safety_output",
}

HYGIENE_CATEGORIES = {
    "private_leak",
}

for name, _, _ in MUTATION_CATALOG:
    if name in CRITICAL_CATEGORIES:
        CATEGORY_META[name] = {
            "criticality": "critical",
            "group": "unsafe_bypass",
            "must_detect": True,
        }
    elif name in SAFETY_CATEGORIES:
        CATEGORY_META[name] = {
            "criticality": "critical",
            "group": "safety",
            "must_detect": True,
        }
    elif name in STRUCTURAL_CATEGORIES:
        CATEGORY_META[name] = {
            "criticality": "high",
            "group": "structural",
            "must_detect": True,
        }
    elif name in HYGIENE_CATEGORIES:
        CATEGORY_META[name] = {
            "criticality": "critical",
            "group": "hygiene",
            "must_detect": True,
        }


def list_categories() -> List[Dict[str, Any]]:
    """Return list of all mutation categories with metadata."""
    result = []
    for name, description, _ in MUTATION_CATALOG:
        meta = CATEGORY_META.get(name, {
            "criticality": "medium",
            "group": "general",
            "must_detect": False,
        })
        result.append({
            "name": name,
            "description": description,
            **meta,
        })
    return result


def get_category(name: str) -> Dict[str, Any]:
    """Get metadata for a single category."""
    return CATEGORY_META.get(name, {
        "criticality": "medium",
        "group": "general",
        "must_detect": False,
    })


def get_critical_categories() -> List[str]:
    """Return list of category names that must be 100% detected."""
    return list(CRITICAL_CATEGORIES | SAFETY_CATEGORIES | HYGIENE_CATEGORIES)


def get_must_detect_categories() -> List[str]:
    """Return categories where detection rate must be 100%."""
    return [n for n, m in CATEGORY_META.items() if m.get("must_detect", False)]


def get_category_groups() -> Dict[str, List[str]]:
    """Return categories grouped by group name."""
    groups: Dict[str, List[str]] = {}
    for name, meta in CATEGORY_META.items():
        group = meta.get("group", "general")
        groups.setdefault(group, []).append(name)
    return groups