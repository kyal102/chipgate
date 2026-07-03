// unsafe_direct_output_fpga.v
// FPGABoardBench demo: expected safety precheck FAIL
//
// This design directly connects ai_output to actuator_enable
// without any safety gating. Expected: safety precheck FAIL,
// should not proceed as a safe candidate.

module unsafe_direct_output_fpga (
    input  wire clk,
    input  wire rst_n,
    input  wire ai_output,
    output reg  actuator_enable
);

    // UNSAFE: no verifier_ok, policy_ok, or kill_switch gating
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output;
        end
    end

endmodule