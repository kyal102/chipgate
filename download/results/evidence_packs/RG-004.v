module no_change_safe (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
        end
    end
endmodule