module no_default_008 (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    input  [1:0] mode,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else begin
            case (mode)
                2'b00: actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
                2'b01: actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
                2'b10: actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
            endcase
        end
    end
endmodule