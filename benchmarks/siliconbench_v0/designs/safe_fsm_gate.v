// safe_fsm_gate.v — SiliconReadinessBench design
//
// Expected: safety precheck pass, formal-ready.
//
// This design uses an FSM to gate the actuator output through
// multiple safety checks. Includes default case and reset.

module safe_fsm_gate (
    input  clk,
    input  rst_n,
    input  start_cmd,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    input  timeout_sig,
    output reg actuator_enable,
    output reg [1:0] fsm_state
);
    localparam IDLE   = 2'd0;
    localparam CHECK  = 2'd1;
    localparam ACTIVE = 2'd2;
    localparam ERROR  = 2'd3;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fsm_state <= IDLE;
            actuator_enable <= 1'b0;
        end else begin
            case (fsm_state)
                IDLE: begin
                    actuator_enable <= 1'b0;
                    if (start_cmd)
                        fsm_state <= CHECK;
                end
                CHECK: begin
                    if (kill_switch || timeout_sig) begin
                        fsm_state <= ERROR;
                        actuator_enable <= 1'b0;
                    end else if (verifier_ok && policy_ok) begin
                        fsm_state <= ACTIVE;
                        actuator_enable <= 1'b1;
                    end else begin
                        fsm_state <= IDLE;
                    end
                end
                ACTIVE: begin
                    if (kill_switch || timeout_sig || !verifier_ok || !policy_ok) begin
                        fsm_state <= ERROR;
                        actuator_enable <= 1'b0;
                    end
                end
                ERROR: begin
                    actuator_enable <= 1'b0;
                    fsm_state <= IDLE;
                end
                default: begin
                    fsm_state <= IDLE;
                    actuator_enable <= 1'b0;
                end
            endcase
        end
    end
endmodule