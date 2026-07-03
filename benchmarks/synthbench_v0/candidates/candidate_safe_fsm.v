module dtl_gate_fsm (
    input clk,
    input rst,
    input ai_output,
    input verifier_ok,
    input policy_ok,
    input kill_switch,
    output reg actuator_enable
);
    parameter IDLE = 3'd0;
    parameter VERIFY = 3'd1;
    parameter APPROVED = 3'd2;
    parameter BLOCKED = 3'd3;
    parameter FAILSAFE = 3'd4;
    reg [2:0] state;
    reg [2:0] next_state;

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            actuator_enable <= 1'b0;
        end else begin
            state <= next_state;
            case (state)
                IDLE: begin
                    next_state <= VERIFY;
                    actuator_enable <= 1'b0;
                end
                VERIFY: begin
                    if (verifier_ok && policy_ok && !kill_switch) begin
                        next_state <= APPROVED;
                    end else begin
                        next_state <= BLOCKED;
                    end
                    actuator_enable <= 1'b0;
                end
                APPROVED: begin
                    actuator_enable <= ai_output & verifier_ok & policy_ok & ~kill_switch;
                    next_state <= VERIFY;
                end
                BLOCKED: begin
                    actuator_enable <= 1'b0;
                    next_state <= VERIFY;
                end
                FAILSAFE: begin
                    actuator_enable <= 1'b0;
                    next_state <= IDLE;
                end
                default: begin
                    actuator_enable <= 1'b0;
                    next_state <= FAILSAFE;
                end
            endcase
        end
    end
endmodule