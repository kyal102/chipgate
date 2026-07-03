# Design Passport Schema

## Schema Version

`designpassport.v0`

## Benchmark

- Name: `designpassport_v0`
- Version: `0.1.0`

## Required Passport Fields (17)

| Field | Type | Description |
|-------|------|-------------|
| schema_version | str | Schema version identifier |
| passport_id | str | Unique passport identifier |
| artifact_id | str | Artifact identifier |
| artifact_type | str | One of 12 artifact types |
| risk_level | str | LOW, MEDIUM, HIGH, SAFETY_CRITICAL, UNKNOWN |
| created_at | str | ISO 8601 timestamp |
| gates_requested | list | Gates selected for this artifact |
| gates_run | list | Gates actually executed |
| gates_passed | list | Gates that passed |
| gates_failed | list | Gates that failed |
| evidence_packs | list | Evidence pack references with hashes |
| artifact_hashes | dict | Content and evidence hashes |
| replay_command | str | CLI command to reproduce the decision |
| passport_status | str | One of 14 passport statuses |
| export_decision | str | One of 6 export decisions |
| limitations | list | Limitation disclaimers |
| certificate_hash | str | SHA-256 hash of core passport fields |

## Passport Statuses (14)

PASSPORT_CREATED, PASSPORT_VERIFIED, PASSPORT_TAMPERED, PASSPORT_REPLAY_MATCH, PASSPORT_REPLAY_DRIFT, PASSPORT_CHECKED, PASSPORT_BLOCKED, PASSPORT_NEEDS_REVIEW, PASSPORT_UNSUPPORTED_ARTIFACT, PASSPORT_MISSING_EVIDENCE, PASSPORT_PRIVATE_LEAK_BLOCKED, PASSPORT_UNSAFE_CLAIM_BLOCKED, PASSPORT_EXTERNAL_REVIEW_PENDING, EVIDENCE_PACK_CREATED

## Export Decisions (6)

EXPORT_ALLOWED, EXPORT_BLOCKED, EXPORT_NEEDS_REVIEW, EXPORT_UNSUPPORTED, EXPORT_PRIVATE_MATERIAL_BLOCKED, EXPORT_REPLAY_REQUIRED

## Badge Types (7)

UNVERIFIED, CHECKED, BLOCKED, NEEDS_REVIEW, REPLAYABLE, MISSING_EVIDENCE, EXTERNAL_REVIEW_PENDING

## Forbidden Phrases (17)

CERTIFIED_SAFE, PROVEN_CORRECT, FABRICATION_READY, SILICON_PROVEN, DEPLOYMENT_SAFE, MEDICAL_SAFE, DEFENCE_CERTIFIED, COMMERCIALLY_VALIDATED, INDEPENDENTLY_VALIDATED, HARDWARE_ACCELERATOR_PROVEN, SILICON_ACCELERATOR_READY, GPU_REPLACEMENT, ASIC_READY, TAPEOUT_READY, PRODUCTION_READY, PHYSICAL_SAFETY_PROVEN, NVIDIA

## Hashing

All hashes use SHA-256, returned as `sha256:<64-hex-digits>`. Certificate hash covers: schema_version, passport_id, artifact_id, artifact_type, risk_level, gates_passed, gates_failed, passport_status, export_decision, replay_command.
