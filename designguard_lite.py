"""DesignGuard Lite - Standalone Public Demonstration.

This is a standalone demonstration of the JARVI3 Chip DesignGuard adapter
format. It does NOT require ChipGate installation and does NOT contain
private JARVI3 or private DTL logic.

This demonstrates the JSON request/response format and the product flow.
It does not prove silicon correctness, fabrication readiness, ASIC readiness,
timing closure, physical safety, medical safety, defence suitability,
robotics safety, production readiness or regulatory compliance.
"""
from __future__ import annotations
import json
from typing import Any, Dict

PUBLIC_HOOK = (
    "JARVI3 Chip DesignGuard gives users a verification layer around "
    "AI-generated chip designs before those designs are trusted, exported "
    "or moved toward hardware workflows."
)

LIMITATION = (
    "JARVI3 Chip DesignGuard does not prove silicon correctness, ASIC "
    "fabrication readiness, timing closure, physical safety, medical safety, "
    "defence suitability, robotics safety, production readiness or regulatory "
    "compliance. It routes artifacts through configured public checks and "
    "records evidence, replay and passport status."
)

PRODUCT_FLOW = [
    "JARVI3 user prompt",
    "JARVI3 generated design",
    "Chip DesignGuard panel",
    "Artifact classification",
    "Risk level assignment",
    "Public gate routing",
    "ChipGate / SoCGate / ASICBench / RISC-V / Robotics checks",
    "EvidencePack",
    "ReplayGate",
    "Design Passport",
    "UI decision: APPROVED / BLOCKED / NEEDS REVIEW / UNSUPPORTED",
]

STATUSES = [
    "DESIGNGUARD_APPROVED",
    "DESIGNGUARD_BLOCKED",
    "DESIGNGUARD_NEEDS_REVIEW",
    "DESIGNGUARD_UNSUPPORTED",
    "DESIGNGUARD_REPLAY_REQUIRED",
    "DESIGNGUARD_REPLAY_MATCH",
    "DESIGNGUARD_REPLAY_DRIFT",
    "DESIGNGUARD_PRIVATE_LEAK_BLOCKED",
    "DESIGNGUARD_UNSAFE_CLAIM_BLOCKED",
    "DESIGNGUARD_PASSPORT_CREATED",
    "DESIGNGUARD_EVIDENCE_CREATED",
    "DESIGNGUARD_EXPORT_ALLOWED",
    "DESIGNGUARD_EXPORT_BLOCKED",
    "DESIGNGUARD_EXPORT_NEEDS_REVIEW",
]

ARTIFACT_TYPES = ["rtl", "soc_design", "asic_review_pack", "riscv_trace", "actuator_rtl", "robotics_trace", "document", "claim_set", "code", "unknown"]

def run_lite_demo() -> Dict[str, Any]:
    """Run the standalone DesignGuard Lite demo.

    Returns:
        Demo result dict with product flow, statuses and sample request/response.
    """
    sample_request = {
        "schema_version": "jarvi3.designguard.v0",
        "request_id": "lite-demo-001",
        "source": "jarvi3",
        "user_intent": "design a safety-gated actuator controller",
        "artifact_type": "rtl",
        "risk_level": "SAFETY_CRITICAL",
        "artifact": {
            "mode": "inline",
            "filename": "generated_design.v",
            "content": "module generated_design(input clk, input req, output reg ack); endmodule",
        },
        "requested_mode": "Safety-Critical Check",
        "policy": {
            "require_evidence_pack": True,
            "require_replay": True,
            "require_passport": True,
            "require_human_review_for_safety_critical": True,
            "block_export_on_failed_gate": True,
            "block_export_on_missing_evidence": True,
            "default_unknown_to_review": True,
        },
    }

    sample_response = {
        "schema_version": "jarvi3.designguard.response.v0",
        "request_id": "lite-demo-001",
        "response_id": "designguard-response-lite",
        "artifact_type": "rtl",
        "risk_level": "SAFETY_CRITICAL",
        "status": "DESIGNGUARD_NEEDS_REVIEW",
        "export_decision": "DESIGNGUARD_EXPORT_NEEDS_REVIEW",
        "gates_run": ["ChipGate", "EvidencePack", "ReplayGate", "Design Passport"],
        "gates_passed": ["ChipGate"],
        "gates_failed": [],
        "unsafe_findings": [],
        "manual_review_items": ["Safety-critical rtl requires human review before export or trust"],
        "evidence_pack_hashes": [],
        "passport_id": "",
        "passport_hash": "",
        "replay_command": "",
        "limitations": [LIMITATION],
        "user_message": "DesignGuard requires review before this artifact should be exported or trusted.",
    }

    return {
        "public_hook": PUBLIC_HOOK,
        "product_flow": PRODUCT_FLOW,
        "supported_statuses": STATUSES,
        "supported_artifact_types": ARTIFACT_TYPES,
        "sample_request": sample_request,
        "sample_response": sample_response,
        "limitation": LIMITATION,
    }

if __name__ == "__main__":
    demo = run_lite_demo()
    print("=== JARVI3 Chip DesignGuard Lite Demo ===")
    print()
    print(f"Public Hook: {demo['public_hook']}")
    print()
    print("Product Flow:")
    for i, step in enumerate(demo["product_flow"], 1):
        print(f"  {i}. {step}")
    print()
    print(f"Supported Artifact Types: {', '.join(demo['supported_artifact_types'])}")
    print()
    print("Limitation:")
    print(f"  {demo['limitation']}")
    print()
    print("Sample Request:")
    print(json.dumps(demo["sample_request"], indent=2))
    print()
    print("Sample Response:")
    print(json.dumps(demo["sample_response"], indent=2))