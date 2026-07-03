module dtl_gate_small (
    input clk,
    input rst,
    input ai_output,
    input verifier_ok,
    input policy_ok,
    input kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or posedge rst)
        if (rst) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output & verifier_ok & policy_ok & ~kill_switch;
endmodule