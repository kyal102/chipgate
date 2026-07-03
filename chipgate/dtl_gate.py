"""
ChipGate DTL hardware gate demo module.

This module generates and documents a tiny DTL hardware safety gate
as a demonstration of the DTL concept entering chip/hardware form.

The gate structure is:

    AI/proposed output
            |
    policy_ok?
    verifier_ok?
    sensor_ok?
    timeout_ok?
    kill_switch clear?
            |
    actuator_enable

This module provides:
1. A reference Verilog implementation
2. Documentation of the gate structure
3. Integration with the ChipGate scanner
"""

from typing import Optional


DTL_GATE_VERILOG = """\
// DTL Hardware Safety Gate — ChipGate Demo
//
// This module demonstrates the DTL (Decision-Trust-Logic) concept
// in hardware form. AI/proposed outputs must pass through all
// verification gates before enabling physical actuation.
//
// ChipGate checks RTL structure and verification-gated safety patterns.
// It does not guarantee hardware correctness, silicon readiness, physical safety,
// regulatory conformance or experimental validity.

module dtl_hardware_gate (
    input  wire        clk,
    input  wire        rst_n,

    // AI / proposed output
    input  wire        ai_output,

    // Verification gates
    input  wire        verifier_ok,    // Verifier has approved the output
    input  wire        policy_ok,      // Output complies with safety policy
    input  wire        sensor_ok,      // Physical sensors confirm safe state
    input  wire        timeout_ok,     // Operation completed within time limit

    // Emergency control
    input  wire        kill_switch,    // Hardware emergency stop (active high)

    // Actuator output — ONLY enabled when ALL gates pass
    output reg         actuator_enable,

    // Diagnostic outputs
    output wire        gate_chain_ok,   // All gates pass
    output wire [4:0]  gate_status       // Individual gate status bits
);

    // ── Gate Chain Logic ──────────────────────────────────────────────
    // All verification signals must be asserted for safe actuation.
    // kill_switch must be LOW (deasserted).

    assign gate_chain_ok = (
        verifier_ok &
        policy_ok &
        sensor_ok &
        timeout_ok &
        ~kill_switch
    );

    // Individual gate status for diagnostics
    assign gate_status = {
        ~kill_switch,    // bit 4: kill switch clear
        timeout_ok,      // bit 3: timeout ok
        sensor_ok,       // bit 2: sensor ok
        policy_ok,       // bit 1: policy ok
        verifier_ok      // bit 0: verifier ok
    };

    // ── Actuator Enable Logic ─────────────────────────────────────────
    // Actuator is ONLY enabled when ALL conditions are met:
    // 1. AI proposes action (ai_output)
    // 2. Verifier approves (verifier_ok)
    // 3. Policy allows (policy_ok)
    // 4. Sensors confirm safe state (sensor_ok)
    // 5. No timeout (timeout_ok)
    // 6. Kill switch is NOT activated (~kill_switch)

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Safe default: actuator DISABLED on reset
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output & gate_chain_ok;
        end
    end

    // ── Assertions ────────────────────────────────────────────────────
    // A1: Kill switch must always disable the actuator
    // assert property (@(posedge clk) kill_switch |-> !actuator_enable)
    //   else $error("SAFETY VIOLATION: actuator enabled while kill_switch is active");

    // A2: Actuator must never be enabled without verifier approval
    // assert property (@(posedge clk) actuator_enable |-> verifier_ok)
    //   else $error("SAFETY VIOLATION: actuator enabled without verifier_ok");

    // A3: Actuator must never be enabled without policy approval
    // assert property (@(posedge clk) actuator_enable |-> policy_ok)
    //   else $error("SAFETY VIOLATION: actuator enabled without policy_ok");

    // A4: Reset must always disable the actuator
    // assert property (@(posedge clk) !rst_n |-> !actuator_enable)
    //   else $error("SAFETY VIOLATION: actuator enabled during reset");

endmodule
"""


DTL_GATE_FSM_VERILOG = """\
// DTL Hardware Safety Gate — FSM Variant
//
// State machine variant of the DTL gate with explicit states:
// IDLE -> PROPOSED -> VERIFYING -> APPROVED -> BLOCKED -> FAILSAFE

module dtl_gate_fsm (
    input  wire        clk,
    input  wire        rst_n,

    // AI / proposed output
    input  wire        ai_output,

    // Verification gates
    input  wire        verifier_ok,
    input  wire        policy_ok,
    input  wire        sensor_ok,
    input  wire        timeout,

    // Emergency control
    input  wire        kill_switch,

    // Actuator output
    output reg         actuator_enable,

    // State diagnostics
    output reg  [2:0]  current_state
);

    // ── State Encoding ────────────────────────────────────────────────
    localparam IDLE      = 3'b000;
    localparam PROPOSED  = 3'b001;
    localparam VERIFYING = 3'b010;
    localparam APPROVED  = 3'b011;
    localparam BLOCKED   = 3'b100;
    localparam FAILSAFE  = 3'b101;

    reg [2:0] state, next_state;

    // ── State Register ────────────────────────────────────────────────
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            actuator_enable <= 1'b0;
        end else begin
            state <= next_state;

            // Actuator only enabled in APPROVED state with all gates passing
            case (state)
                APPROVED: begin
                    actuator_enable <= ai_output && verifier_ok && policy_ok
                                    && sensor_ok && !timeout && !kill_switch;
                end
                default: begin
                    actuator_enable <= 1'b0;
                end
            endcase
        end
    end

    // ── Next State Logic ──────────────────────────────────────────────
    always @(*) begin
        next_state = state;  // default: stay in current state
        case (state)
            IDLE: begin
                if (ai_output) begin
                    next_state = PROPOSED;
                end
            end

            PROPOSED: begin
                next_state = VERIFYING;
            end

            VERIFYING: begin
                if (kill_switch) begin
                    next_state = FAILSAFE;
                end else if (timeout) begin
                    next_state = BLOCKED;
                end else if (verifier_ok && policy_ok && sensor_ok) begin
                    next_state = APPROVED;
                end
            end

            APPROVED: begin
                if (kill_switch) begin
                    next_state = FAILSAFE;
                end else if (timeout || !verifier_ok || !policy_ok) begin
                    next_state = BLOCKED;
                end else if (!ai_output) begin
                    next_state = IDLE;
                end
            end

            BLOCKED: begin
                if (kill_switch) begin
                    next_state = FAILSAFE;
                end else if (!ai_output) begin
                    next_state = IDLE;
                end
            end

            FAILSAFE: begin
                if (!kill_switch && !ai_output) begin
                    next_state = IDLE;
                end
            end

            default: begin
                next_state = IDLE;
            end
        endcase
    end

    // ── State Output ──────────────────────────────────────────────────
    always @(*) begin
        current_state = state;
    end

    // ── Assertions (commented for ChipGate detection) ─────────────────
    // assert property (@(posedge clk) kill_switch |-> !actuator_enable);
    // assert property (@(posedge clk) actuator_enable |-> (state == APPROVED));
    // assert property (@(posedge clk) actuator_enable |-> verifier_ok && policy_ok);
    // assert property (@(posedge clk) state == FAILSAFE |-> !actuator_enable);

endmodule
"""


def get_dtl_gate_reference() -> str:
    """Return the reference DTL gate Verilog implementation."""
    return DTL_GATE_VERILOG


def get_dtl_fsm_reference() -> str:
    """Return the reference DTL FSM gate Verilog implementation."""
    return DTL_GATE_FSM_VERILOG


def get_gate_structure_docs() -> str:
    """Return documentation of the DTL gate structure."""
    return """\
DTL Hardware Safety Gate Structure
===================================

The gate enforces that AI/proposed outputs cannot directly control
physical actuators. Every proposed action must pass through a chain
of verification checks before actuation is enabled.

Gate Chain (all must pass):

    1. verifier_ok  — AI output has been independently verified
    2. policy_ok    — Output complies with defined safety policy
    3. sensor_ok    — Physical sensors confirm the environment is safe
    4. timeout_ok   — Operation has not exceeded its time limit
    5. kill_switch  — Emergency stop is NOT activated

Logic:
    actuator_enable = ai_output & verifier_ok & policy_ok
                    & sensor_ok & timeout_ok & ~kill_switch

On reset (rst_n deasserted), actuator_enable is forced to 0 (safe default).

This gate can be implemented in:
    - ASIC (via OpenLane/OpenROAD flow)
    - FPGA (via Yosys/nextpnr flow)
    - Simulation (via Verilator/cocotb)
    - Formal verification (via SymbiYosys)
"""