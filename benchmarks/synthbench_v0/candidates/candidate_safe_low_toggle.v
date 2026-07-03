module dtl_gate_low_toggle (
    input clk,
    input rst,
    input ai_output,
    input verifier_ok,
    input policy_ok,
    input kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= (rst) ? 1'b0 : (ai_output & verifier_ok & policy_ok & ~kill_switch);
    end
endmodule