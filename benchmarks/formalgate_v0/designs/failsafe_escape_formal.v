// failsafe_escape_formal.v - FormalGate-Lite benchmark design
//
// Expected: failsafe_no_direct_approve property FAIL.
// The FSM allows a direct transition from IDLE to APPROVED,
// bypassing the required PENDING state.
//
// ChipGate checks RTL structure and verification-gated safety patterns.
// It does not prove hardware correctness, silicon readiness, physical safety,
// regulatory compliance or experimental validity.

module failsafe_escape_formal (
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

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
            failsafe_state <= IDLE;
        end else if (kill_switch || timeout || reset) begin
            actuator_enable <= 1'b0;
            failsafe_state <= BLOCKED;
        end else begin
            case (failsafe_state)
                IDLE: begin
                    if (ai_output && verifier_ok && policy_ok && sensor_ok) begin
                        // UNSAFE: direct transition IDLE -> APPROVED, skipping PENDING
                        failsafe_state <= APPROVED;
                        actuator_enable <= ai_output && verifier_ok && policy_ok && sensor_ok;
                    end else begin
                        actuator_enable <= 1'b0;
                    end
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
                PENDING: begin
                    // PENDING goes straight to APPROVED if conditions met
                    if (verifier_ok && policy_ok && sensor_ok) begin
                        failsafe_state <= APPROVED;
                    end else begin
                        failsafe_state <= BLOCKED;
                    end
                    actuator_enable <= 1'b0;
                end
                default: begin
                    actuator_enable <= 1'b0;
                    failsafe_state <= IDLE;
                end
            endcase
        end
    end

endmodule