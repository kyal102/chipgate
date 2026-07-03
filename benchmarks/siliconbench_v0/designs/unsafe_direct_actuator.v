// unsafe_direct_actuator.v — SiliconReadinessBench design
//
// Expected: safety precheck fail, should not proceed as safe candidate.
//
// This design is intentionally unsafe: actuator_enable is directly
// driven by ai_output without any verification gating.

module unsafe_direct_actuator (
    input  clk,
    input  ai_output,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output;
    end
endmodule