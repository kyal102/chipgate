# JARVI3 Extension Boundary

## Public Interface Only

The DTL Verified Design Passport operates entirely on public code. No private JARVI3 or DTL modules are imported. The system is designed as a standalone, public-domain verification record generator.

## Adapter Format

JARVI3 can pass artifacts to the Design Passport via a JSON adapter input:

```json
{
  "source": "jarvi3_public_adapter",
  "artifact_id": "jarvi3_design_001",
  "artifact_type": "rtl",
  "user_intent": "design a safety-gated actuator controller",
  "risk_level": "safety_critical",
  "artifact_path": "",
  "requested_gates": ["chipgate", "evidencepack", "replaygate"]
}
```

## Fields Used from Adapter

| Field | Usage |
|-------|-------|
| source | Metadata only, not used in decisions |
| artifact_id | Used as passport artifact_id |
| artifact_type | Used for classification (if valid) |
| user_intent | Metadata only, not used in decisions |
| risk_level | Metadata only; actual risk computed from artifact type |
| artifact_path | Read artifact content from file |
| requested_gates | Override default gate selection |

## Fields NOT Used

- `user_intent` is recorded but does not affect verification
- `risk_level` from adapter is advisory; the passport computes its own risk level
- No JARVI3 internal state is accessed

## Private Leak Detection

The passport actively blocks artifacts containing patterns like `jarvi3_private`, `dtl_private`, `JARVI3_CORE`, `JARVI3_ROUTER`, `DTL_ROUTER`, `_private_key`, `secret_key`, `api_key`. If detected, the passport status is set to `PASSPORT_PRIVATE_LEAK_BLOCKED` and export is blocked.
