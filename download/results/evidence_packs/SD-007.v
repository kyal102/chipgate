module safe_dtl_v7 (
    input  clk, input  rst_n, input  ai_output,
    input  verifier_ok, input  policy_ok, input  sensor_ok,
    input  timeout, input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && verifier_ok && policy_ok && sensor_ok && !timeout && !kill_switch;
    end
endmodule