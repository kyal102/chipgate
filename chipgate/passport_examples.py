"""DTL Verified Design Passport — Demo Examples and Fixtures.

Provides demo artifact content, adapter inputs, and fixture data
for testing and demonstration purposes.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Demo RTL artifact (safe)
# ---------------------------------------------------------------------------

DEMO_RTL_SAFE: str = """\
module safe_dtl_gate (
    input wire clk,
    input wire rst_n,
    input wire verifier_ok,
    input wire policy_ok,
    input wire evidence_ok,
    input wire timeout_ok,
    input wire kill_switch,
    output reg approved
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n || kill_switch) begin
            approved <= 1'b0;
        end else if (verifier_ok && policy_ok && evidence_ok && timeout_ok) begin
            approved <= 1'b1;
        end else begin
            approved <= 1'b0;
        end
    end
endmodule
"""


# ---------------------------------------------------------------------------
# Demo RTL artifact (unsafe — missing kill switch)
# ---------------------------------------------------------------------------

DEMO_RTL_UNSAFE: str = """\
module unsafe_gate (
    input wire clk,
    input wire rst_n,
    input wire data_in,
    output reg data_out
);
    always @(posedge clk) begin
        data_out <= data_in;
    end
endmodule
"""


# ---------------------------------------------------------------------------
# Demo document artifact
# ---------------------------------------------------------------------------

DEMO_DOCUMENT: str = """\
# Design Claim Document

This document claims that the verification gate design meets
the following requirements:

1. Verifier signal is connected
2. Policy signal is connected
3. Evidence signal is connected
4. Kill switch forces safe state
5. Reset forces safe state

Evidence: All signals are checked in the RTL module.
"""


# ---------------------------------------------------------------------------
# Demo physics equation
# ---------------------------------------------------------------------------

DEMO_PHYSICS: str = """\
# Physics Equations for Sensor Model

Force calculation:
  F = m * a

Pressure:
  P = F / A

Kinetic energy:
  KE = 0.5 * m * v^2
"""


# ---------------------------------------------------------------------------
# Demo chemistry formula
# ---------------------------------------------------------------------------

DEMO_CHEMISTRY: str = """\
# Chemistry Formulas

Reaction rate: r = k * [A]^m * [B]^n

Molarity: M = mol / L

Ideal gas: PV = nRT
"""


# ---------------------------------------------------------------------------
# Demo adapter input (JARVI3 public adapter format)
# ---------------------------------------------------------------------------

DEMO_ADAPTER_INPUT: Dict[str, Any] = {
    "source": "jarvi3_public_adapter",
    "artifact_id": "jarvi3_design_001",
    "artifact_type": "rtl",
    "user_intent": "design a safety-gated actuator controller",
    "risk_level": "safety_critical",
    "artifact_path": "",
    "requested_gates": [
        "chipgate",
        "evidencepack",
        "replaygate",
    ],
}


# ---------------------------------------------------------------------------
# Demo fixture data
# ---------------------------------------------------------------------------

DEMO_FIXTURES: List[Dict[str, Any]] = [
    {
        "name": "safe_rtl",
        "artifact_id": "demo_rtl_safe_001",
        "artifact_type": "rtl",
        "expected_risk": "HIGH",
        "content": DEMO_RTL_SAFE,
        "expected_gates": ["chipgate", "evidencepack", "replaygate"],
    },
    {
        "name": "unsafe_rtl",
        "artifact_id": "demo_rtl_unsafe_001",
        "artifact_type": "rtl",
        "expected_risk": "HIGH",
        "content": DEMO_RTL_UNSAFE,
        "expected_gates": ["chipgate", "evidencepack", "replaygate"],
    },
    {
        "name": "document",
        "artifact_id": "demo_document_001",
        "artifact_type": "document",
        "expected_risk": "LOW",
        "content": DEMO_DOCUMENT,
        "expected_gates": ["claimgate", "claimlint", "evidencepack", "replaygate"],
    },
    {
        "name": "physics",
        "artifact_id": "demo_physics_001",
        "artifact_type": "physics_equation",
        "expected_risk": "MEDIUM",
        "content": DEMO_PHYSICS,
        "expected_gates": ["unitgate", "evidencepack", "replaygate"],
    },
    {
        "name": "chemistry",
        "artifact_id": "demo_chemistry_001",
        "artifact_type": "chemistry_formula",
        "expected_risk": "MEDIUM",
        "content": DEMO_CHEMISTRY,
        "expected_gates": ["elementgate", "evidencepack", "replaygate"],
    },
]


# ---------------------------------------------------------------------------
# Benchmark info fixture
# ---------------------------------------------------------------------------

BENCHMARK_INFO: Dict[str, Any] = {
    "benchmark_name": "designpassport_v0",
    "benchmark_version": "0.1.0",
    "description": "DTL Verified Design Passport benchmark fixtures",
    "artifact_count": len(DEMO_FIXTURES),
    "artifact_types": list(set(f["artifact_type"] for f in DEMO_FIXTURES)),
    "limitation": (
        "DTL Verified Design Passport does not prove that a design is correct, "
        "safe, certified, fabrication-ready, commercially validated or ready for "
        "real-world use."
    ),
}
