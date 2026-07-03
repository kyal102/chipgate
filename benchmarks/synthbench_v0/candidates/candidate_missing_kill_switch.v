module dtl_gate_no_kill (
    input clk,
    input rst,
    input ai_output,
    input verifier_ok,
    input policy_ok,
    output reg actuator_enable
);
    always @(posedge clk) begin
        if (rst) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output & verifier_ok & policy_ok;
        end
    end
endmodule