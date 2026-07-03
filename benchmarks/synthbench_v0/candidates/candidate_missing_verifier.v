module dtl_gate_no_verifier (
    input clk,
    input rst,
    input ai_output,
    input policy_ok,
    input kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        if (rst) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output & policy_ok & ~kill_switch;
        end
    end
endmodule