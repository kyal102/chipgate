module dtl_gate_safe_large (
    input clk,
    input rst,
    input ai_output,
    input verifier_ok,
    input policy_ok,
    input kill_switch,
    input sensor_ok,
    input watchdog_ok,
    input timeout_ok,
    output reg actuator_enable
);
    reg [2:0] state;
    reg [2:0] next_state;
    always @(posedge clk) begin
        if (rst) begin
            state <= 3'd0;
            actuator_enable <= 1'b0;
        end else begin
            case (state)
                3'd0: begin
                    if (sensor_ok && watchdog_ok) begin
                        next_state <= 3'd1;
                    end else begin
                        next_state <= 3'd0;
                    end
                end
                3'd1: begin
                    if (timeout_ok) begin
                        next_state <= 3'd2;
                    end else begin
                        next_state <= 3'd4;
                    end
                end
                3'd2: begin
                    if (verifier_ok && policy_ok && !kill_switch) begin
                        actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
                        next_state <= 3'd3;
                    end else begin
                        actuator_enable <= 1'b0;
                        next_state <= 3'd4;
                    end
                end
                3'd3: begin
                    next_state <= 3'd2;
                end
                3'd4: begin
                    actuator_enable <= 1'b0;
                    next_state <= 3'd0;
                end
                default: begin
                    next_state <= 3'd0;
                end
            endcase
            state <= next_state;
        end
    end
endmodule