// unsafe_direct_actuator_formal.v — FormalGate-Lite benchmark design
//
// Expected: formal checks FAIL — specifically failsafe_no_direct_approve
// and other safety properties.
//
// This design is intentionally unsafe:
//   - actuator_enable is directly driven by ai_output without verification gating.
//   - failsafe_state can go directly to APPROVED without intermediate PENDING.
//   - kill_switch, timeout, reset, verifier_ok, policy_ok, sensor_ok signals
//     are declared but NOT wired into the output logic.
//
// ChipGate checks RTL structure and verification-gated safety patterns.
// It does not prove hardware correctness, silicon readiness, physical safety,
// regulatory compliance or experimental validity.

module unsafe_direct_actuator_formal (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  sensor_ok,
    input  kill_switch,
    input  timeout,
    input  reset,
    output reg actuator_enable,
    output reg [1:0] failsafe_state
);

    localparam IDLE     = 2'b00;
    localparam PENDING  = 2'b01;
    localparam APPROVED = 2'b10;
    localparam BLOCKED  = 2'b11;

    // UNSAFE: actuator_enable is driven directly from ai_output
    // with no verification gating.  All safety inputs are ignored.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
            failsafe_state <= IDLE;
        end else begin
            // Direct passthrough — no gating at all.
            actuator_enable <= ai_output;

            // Failsafe state also skips PENDING: can jump IDLE -> APPROVED.
            if (ai_output)
                failsafe_state <= APPROVED;
            else
                failsafe_state <= IDLE;
        end
    end

endmodule
