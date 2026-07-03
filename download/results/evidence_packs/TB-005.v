module timeout_bypass_005 (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    input  timeout,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else if (timeout) actuator_enable <= ai_output;
        else actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule