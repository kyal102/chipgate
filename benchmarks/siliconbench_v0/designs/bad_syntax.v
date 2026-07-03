// bad_syntax.v — SiliconReadinessBench design
//
// Expected: lint/synthesis fail due to syntax errors.
//
// This file contains intentional Verilog syntax errors for testing
// that SiliconReadinessBench correctly classifies malformed RTL.

module bad_syntax (
    input clk,
    output reg out
);
    always @(posedge clk) begin
        // Missing semicolon and bad syntax
        out <= = clk +
    end
endmodule