// missing_kill_switch_fpga.v
// FPGABoardBench demo: expected KILL_SWITCH_MISSING
//
// This design has safety gating (verifier_ok && policy_ok) but
// is missing a kill_switch input. Expected: pin constraint FAIL
// with KILL_SWITCH_MISSING.

module missing_kill_switch_fpga (
    input  wire clk,
    input  wire rst_n,
    input  wire verifier_ok,
    input  wire policy_ok,
    input  wire ai_output,
    output reg  actuator_enable
);

    initial begin
        actuator_enable = 1'b0;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
        end else begin
            // Gated but missing kill_switch
            actuator_enable <= ai_output & verifier_ok & policy_ok;
        end
    end

endmodule