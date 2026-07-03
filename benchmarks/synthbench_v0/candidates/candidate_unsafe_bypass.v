module dtl_gate_bypass (
    input clk,
    input rst,
    input ai_output,
    input verifier_ok,
    input kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        if (rst) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output & verifier_ok;
        end
    end
endmodule