module no_reset_009 (
    input  clk,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule