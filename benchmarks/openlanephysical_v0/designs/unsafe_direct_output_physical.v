// UNSAFE design for testing - direct output with no safety gating
module unsafe_direct_output_physical (
    input  wire clk,
    input  wire rst_n,
    input  wire ai_output,
    output wire actuator_enable
);

    // UNSAFE: direct output, no safety gating
    assign actuator_enable = ai_output;

endmodule