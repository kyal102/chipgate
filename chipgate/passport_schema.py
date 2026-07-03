"""DTL Verified Design Passport — Schema Definitions.

Defines the passport schema version, field names, status constants,
risk levels, badge types, export decisions, artifact types, and
gate identifiers used throughout the Design Passport system.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready. It creates a structured, replayable verification
record for the configured checks that were actually run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION: str = "designpassport.v0"
BENCHMARK_NAME: str = "designpassport_v0"
BENCHMARK_VERSION: str = "0.1.0"


# ---------------------------------------------------------------------------
# Passport statuses
# ---------------------------------------------------------------------------

PASSPORT_CREATED: str = "PASSPORT_CREATED"
PASSPORT_VERIFIED: str = "PASSPORT_VERIFIED"
PASSPORT_TAMPERED: str = "PASSPORT_TAMPERED"
PASSPORT_REPLAY_MATCH: str = "PASSPORT_REPLAY_MATCH"
PASSPORT_REPLAY_DRIFT: str = "PASSPORT_REPLAY_DRIFT"
PASSPORT_CHECKED: str = "PASSPORT_CHECKED"
PASSPORT_BLOCKED: str = "PASSPORT_BLOCKED"
PASSPORT_NEEDS_REVIEW: str = "PASSPORT_NEEDS_REVIEW"
PASSPORT_UNSUPPORTED_ARTIFACT: str = "PASSPORT_UNSUPPORTED_ARTIFACT"
PASSPORT_MISSING_EVIDENCE: str = "PASSPORT_MISSING_EVIDENCE"
PASSPORT_PRIVATE_LEAK_BLOCKED: str = "PASSPORT_PRIVATE_LEAK_BLOCKED"
PASSPORT_UNSAFE_CLAIM_BLOCKED: str = "PASSPORT_UNSAFE_CLAIM_BLOCKED"
PASSPORT_EXTERNAL_REVIEW_PENDING: str = "PASSPORT_EXTERNAL_REVIEW_PENDING"
EVIDENCE_PACK_CREATED: str = "EVIDENCE_PACK_CREATED"

ALL_PASSPORT_STATUSES: List[str] = [
    PASSPORT_CREATED,
    PASSPORT_VERIFIED,
    PASSPORT_TAMPERED,
    PASSPORT_REPLAY_MATCH,
    PASSPORT_REPLAY_DRIFT,
    PASSPORT_CHECKED,
    PASSPORT_BLOCKED,
    PASSPORT_NEEDS_REVIEW,
    PASSPORT_UNSUPPORTED_ARTIFACT,
    PASSPORT_MISSING_EVIDENCE,
    PASSPORT_PRIVATE_LEAK_BLOCKED,
    PASSPORT_UNSAFE_CLAIM_BLOCKED,
    PASSPORT_EXTERNAL_REVIEW_PENDING,
    EVIDENCE_PACK_CREATED,
]


# ---------------------------------------------------------------------------
# Export decisions
# ---------------------------------------------------------------------------

EXPORT_ALLOWED: str = "EXPORT_ALLOWED"
EXPORT_BLOCKED: str = "EXPORT_BLOCKED"
EXPORT_NEEDS_REVIEW: str = "EXPORT_NEEDS_REVIEW"
EXPORT_UNSUPPORTED: str = "EXPORT_UNSUPPORTED"
EXPORT_PRIVATE_MATERIAL_BLOCKED: str = "EXPORT_PRIVATE_MATERIAL_BLOCKED"
EXPORT_REPLAY_REQUIRED: str = "EXPORT_REPLAY_REQUIRED"

ALL_EXPORT_DECISIONS: List[str] = [
    EXPORT_ALLOWED,
    EXPORT_BLOCKED,
    EXPORT_NEEDS_REVIEW,
    EXPORT_UNSUPPORTED,
    EXPORT_PRIVATE_MATERIAL_BLOCKED,
    EXPORT_REPLAY_REQUIRED,
]


# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------

RISK_LOW: str = "LOW"
RISK_MEDIUM: str = "MEDIUM"
RISK_HIGH: str = "HIGH"
RISK_SAFETY_CRITICAL: str = "SAFETY_CRITICAL"
RISK_UNKNOWN: str = "UNKNOWN"

ALL_RISK_LEVELS: List[str] = [
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_SAFETY_CRITICAL,
    RISK_UNKNOWN,
]


# ---------------------------------------------------------------------------
# Badge types
# ---------------------------------------------------------------------------

BADGE_UNVERIFIED: str = "UNVERIFIED"
BADGE_CHECKED: str = "CHECKED"
BADGE_BLOCKED: str = "BLOCKED"
BADGE_NEEDS_REVIEW: str = "NEEDS_REVIEW"
BADGE_REPLAYABLE: str = "REPLAYABLE"
BADGE_MISSING_EVIDENCE: str = "MISSING_EVIDENCE"
BADGE_EXTERNAL_REVIEW_PENDING: str = "EXTERNAL_REVIEW_PENDING"

ALL_BADGE_TYPES: List[str] = [
    BADGE_UNVERIFIED,
    BADGE_CHECKED,
    BADGE_BLOCKED,
    BADGE_NEEDS_REVIEW,
    BADGE_REPLAYABLE,
    BADGE_MISSING_EVIDENCE,
    BADGE_EXTERNAL_REVIEW_PENDING,
]


# ---------------------------------------------------------------------------
# Artifact types
# ---------------------------------------------------------------------------

ARTIFACT_DOCUMENT: str = "document"
ARTIFACT_CLAIM_SET: str = "claim_set"
ARTIFACT_CODE: str = "code"
ARTIFACT_RTL: str = "rtl"
ARTIFACT_RISCV_TRACE: str = "riscv_trace"
ARTIFACT_SOC_DESIGN: str = "soc_design"
ARTIFACT_ASIC_REVIEW_PACK: str = "asic_review_pack"
ARTIFACT_ROBOTICS_CONTROL_DEMO: str = "robotics_control_demo"
ARTIFACT_SUPPLY_CHAIN_POLICY_DEMO: str = "supply_chain_policy_demo"
ARTIFACT_PHYSICS_EQUATION: str = "physics_equation"
ARTIFACT_CHEMISTRY_FORMULA: str = "chemistry_formula"
ARTIFACT_UNKNOWN: str = "unknown"

ALL_ARTIFACT_TYPES: List[str] = [
    ARTIFACT_DOCUMENT,
    ARTIFACT_CLAIM_SET,
    ARTIFACT_CODE,
    ARTIFACT_RTL,
    ARTIFACT_RISCV_TRACE,
    ARTIFACT_SOC_DESIGN,
    ARTIFACT_ASIC_REVIEW_PACK,
    ARTIFACT_ROBOTICS_CONTROL_DEMO,
    ARTIFACT_SUPPLY_CHAIN_POLICY_DEMO,
    ARTIFACT_PHYSICS_EQUATION,
    ARTIFACT_CHEMISTRY_FORMULA,
    ARTIFACT_UNKNOWN,
]


# ---------------------------------------------------------------------------
# Gate identifiers
# ---------------------------------------------------------------------------

GATE_CHIPGATE: str = "chipgate"
GATE_EVIDENCEPACK: str = "evidencepack"
GATE_REPLAYGATE: str = "replaygate"
GATE_CLAIMGATE: str = "claimgate"
GATE_CLAIMLINT: str = "claimlint"
GATE_UNITGATE: str = "unitgate"
GATE_ELEMENTGATE: str = "elementgate"
GATE_SOC_SAFETY: str = "soc_safety"
GATE_RISCV_DEMO: str = "riscv_demo"
GATE_ASIC_BENCH: str = "asic_bench"
GATE_DTL_ACCEL: str = "dtl_accel"

ALL_GATE_IDS: List[str] = [
    GATE_CHIPGATE,
    GATE_EVIDENCEPACK,
    GATE_REPLAYGATE,
    GATE_CLAIMGATE,
    GATE_CLAIMLINT,
    GATE_UNITGATE,
    GATE_ELEMENTGATE,
    GATE_SOC_SAFETY,
    GATE_RISCV_DEMO,
    GATE_ASIC_BENCH,
    GATE_DTL_ACCEL,
]


# ---------------------------------------------------------------------------
# Forbidden phrases (overclaims)
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES: List[str] = [
    "CERTIFIED_SAFE",
    "PROVEN_CORRECT",
    "FABRICATION_READY",
    "SILICON_PROVEN",
    "DEPLOYMENT_SAFE",
    "MEDICAL_SAFE",
    "DEFENCE_CERTIFIED",
    "COMMERCIALLY_VALIDATED",
    "INDEPENDENTLY_VALIDATED",
    "HARDWARE_ACCELERATOR_PROVEN",
    "SILICON_ACCELERATOR_READY",
    "GPU_REPLACEMENT",
    "ASIC_READY",
    "TAPEOUT_READY",
    "PRODUCTION_READY",
    "PHYSICAL_SAFETY_PROVEN",
    "NVIDIA",
]


# ---------------------------------------------------------------------------
# Public wording and limitations
# ---------------------------------------------------------------------------

PASSPORT_PUBLIC_WORDING: str = (
    "DTL Verified Design Passport gives AI-generated designs a portable "
    "record of what was checked, what failed, what evidence exists and "
    "whether the result can be replayed."
)

PASSPORT_LIMITATION: str = (
    "DTL Verified Design Passport does not prove that a design is correct, "
    "safe, certified, fabrication-ready, commercially validated or ready for "
    "real-world use. It records the configured checks, evidence, limitations "
    "and replay status for a specific artifact."
)


# ---------------------------------------------------------------------------
# Private leak detection patterns
# ---------------------------------------------------------------------------

PRIVATE_PATTERNS: List[str] = [
    "jarvi3_private",
    "dtl_private",
    "dtl_internal",
    "_private_key",
    "secret_key",
    "api_key",
    "JARVI3_CORE",
    "JARVI3_ROUTER",
    "DTL_ROUTER",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """Result of running a single verification gate."""

    gate_id: str = ""
    gate_name: str = ""
    passed: bool = False
    failed: bool = False
    skipped: bool = False
    reason: str = ""
    evidence_pack_path: str = ""
    evidence_hash: str = ""


@dataclass
class PassportData:
    """Complete passport data structure.

    This is the serialisable representation of a design passport.
    """

    schema_version: str = SCHEMA_VERSION
    passport_id: str = ""
    artifact_id: str = ""
    artifact_type: str = ARTIFACT_UNKNOWN
    artifact_hash: str = ""
    risk_level: str = RISK_UNKNOWN
    created_at: str = ""
    gates_requested: List[str] = field(default_factory=list)
    gates_run: List[str] = field(default_factory=list)
    gates_passed: List[str] = field(default_factory=list)
    gates_failed: List[str] = field(default_factory=list)
    evidence_packs: List[Dict[str, str]] = field(default_factory=list)
    artifact_hashes: Dict[str, str] = field(default_factory=dict)
    replay_command: str = ""
    passport_status: str = PASSPORT_CREATED
    export_decision: str = EXPORT_NEEDS_REVIEW
    limitations: List[str] = field(default_factory=list)
    certificate_hash: str = ""
    badge: str = BADGE_UNVERIFIED
    manual_review_items: List[str] = field(default_factory=list)
    public_wording: str = PASSPORT_PUBLIC_WORDING


@dataclass
class BadgeData:
    """Badge output structure."""

    artifact_id: str = ""
    badge: str = BADGE_UNVERIFIED
    reason: str = ""
    passport_hash: str = ""


@dataclass
class PassportMetrics:
    """Aggregate metrics collected across a passport evaluation run."""

    artifacts_checked: int = 0
    passports_created: int = 0
    passports_verified: int = 0
    passports_tampered: int = 0
    badges_created: int = 0
    gates_requested: int = 0
    gates_run: int = 0
    gates_passed: int = 0
    gates_failed: int = 0
    evidence_packs_attached: int = 0
    replay_matches: int = 0
    replay_drifts: int = 0
    exports_allowed: int = 0
    exports_blocked: int = 0
    exports_needing_review: int = 0
    manual_review_items: int = 0
    private_leaks_blocked: int = 0
    unsafe_claims_blocked: int = 0
    artifact_hash_count: int = 0


# ---------------------------------------------------------------------------
# Required fields for a valid passport
# ---------------------------------------------------------------------------

REQUIRED_PASSPORT_FIELDS: List[str] = [
    "schema_version",
    "passport_id",
    "artifact_id",
    "artifact_type",
    "risk_level",
    "created_at",
    "gates_requested",
    "gates_run",
    "gates_passed",
    "gates_failed",
    "evidence_packs",
    "artifact_hashes",
    "replay_command",
    "passport_status",
    "export_decision",
    "limitations",
    "certificate_hash",
]
