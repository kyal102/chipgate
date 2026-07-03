// safe_dtl_gate_formal.v — FormalGate-Lite benchmark design
//
// Expected: all formal properties PASS (if SBY is available).
//
// This is a properly gated DTL safety design with all required formal
// signals: kill_switch, timeout, reset, verifier_ok, policy_ok, sensor_ok,
// actuator_enable, and a failsafe_state enum.
//
// ChipGate checks RTL structure and verification-gated safety patterns.
// It does not prove hardware correctness, silicon readiness, physical safety,
// regulatory compliance or experimental validity.

module safe_dtl_gate_formal (
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

    // ----------------------------------------------------------------
    // Failsafe state machine: IDLE -> PENDING -> APPROVED / BLOCKED
    // Cannot go directly to APPROVED without passing through PENDING.
    // ----------------------------------------------------------------
    localparam IDLE     = 2'b00;
    localparam PENDING  = 2'b01;
    localparam APPROVED = 2'b10;
    localparam BLOCKED  = 2'b11;

    // formal: kill_switch_blocks_output
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
            failsafe_state <= IDLE;
        end else if (reset) begin
            actuator_enable <= 1'b0;
            failsafe_state <= IDLE;
        end else if (kill_switch || timeout) begin
            // Kill switch or timeout immediately blocks actuator output.
            actuator_enable <= 1'b0;
            failsafe_state <= BLOCKED;
        end else begin
            // Failsafe FSM: must transition IDLE -> PENDING -> APPROVED
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
                    // Remain in APPROVED while all conditions hold.
                    if (!(verifier_ok && policy_ok && sensor_ok))
                        failsafe_state <= BLOCKED;
                end
                BLOCKED: begin
                    actuator_enable <= 1'b0;
                    // Can only recover to IDLE via reset.
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
