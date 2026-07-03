// safe_dtl_gate.v — ChipGate Example
//
// This design demonstrates a properly gated DTL safety output.
// ChipGate should report: SAFETY_GATE_PRESENT
//
// actuator_enable is gated by verifier_ok, policy_ok, and kill_switch.
// The design includes a reset signal.
//
// ChipGate checks RTL structure and verification-gated safety patterns.
// It does not prove hardware correctness, silicon readiness, physical safety,
// regulatory compliance or experimental validity.

module safe_dtl_gate (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output || verifier_ok && policy_ok && !kill_switch;
        end
    end
endmodule