// missing_kill_switch_formal.v - FormalGate-Lite benchmark design
//
// Expected: KILL_SWITCH_MISSING from safety scan; formal properties for
// kill_switch_blocks_output should FAIL or be flagged.
//
// This design has no kill_switch input. The kill_switch signal is
// completely absent, violating the DTL gate specification.
//
// ChipGate checks RTL structure and verification-gated safety patterns.
// It does not prove hardware correctness, silicon readiness, physical safety,
// regulatory compliance or experimental validity.

module missing_kill_switch_formal (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  sensor_ok,
    // kill_switch is INTENTIONALLY MISSING
    input  timeout,
    input  reset,
    output reg actuator_enable,
    output reg [1:0] failsafe_state
);

    localparam IDLE     = 2'b00;
    localparam PENDING  = 2'b01;
    localparam APPROVED = 2'b10;
    localparam BLOCKED  = 2'b11;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
            failsafe_state <= IDLE;
        end else if (reset || timeout) begin
            actuator_enable <= 1'b0;
            failsafe_state <= BLOCKED;
        end else begin
            case (failsafe_state)
                IDLE: begin
                    if (ai_output && verifier_ok && policy_ok && sensor_ok)
                        failsafe_state <= PENDING;
                    actuator_enable <= 1'b0;
                end
                PENDING: begin
                    if (verifier_ok && policy_ok && sensor_ok)
                        failsafe_state <= APPROVED;
                    else
                        failsafe_state <= BLOCKED;
                    actuator_enable <= 1'b0;
                end
                APPROVED: begin
                    actuator_enable <= ai_output && verifier_ok && policy_ok && sensor_ok;
                    if (!(verifier_ok && policy_ok && sensor_ok))
                        failsafe_state <= BLOCKED;
                end
                BLOCKED: begin
                    actuator_enable <= 1'b0;
                    if (reset)
                        failsafe_state <= IDLE;
                end
                default: begin
                    actuator_enable <= 1'b0;
                    failsafe_state <= IDLE;
                end
            endcase
        end
    end

endmodule