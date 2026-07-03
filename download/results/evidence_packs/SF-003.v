module safe_fsm_003 (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  sensor_ok,
    input  timeout,
    input  kill_switch,
    output reg actuator_enable,
    output reg [2:0] state
);
    localparam IDLE=0, VERIFYING=1, APPROVED=2, BLOCKED=3, FAILSAFE=4;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin state <= IDLE; actuator_enable <= 1'b0; end
        else begin
            case (state)
                IDLE: if (ai_output) state <= VERIFYING;
                VERIFYING: if (kill_switch) state <= FAILSAFE;
                           else if (timeout) state <= BLOCKED;
                           else if (verifier_ok && policy_ok && sensor_ok) state <= APPROVED;
                APPROVED: begin
                    actuator_enable <= ai_output && verifier_ok && policy_ok && sensor_ok && !timeout && !kill_switch;
                    if (kill_switch || !verifier_ok) state <= BLOCKED;
                    else if (!ai_output) state <= IDLE;
                end
                BLOCKED: if (!ai_output) state <= IDLE;
                FAILSAFE: if (!kill_switch && !ai_output) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule