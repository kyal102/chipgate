module leaky (
    input wire clk,
    output reg out
);
    // This references JARVI3_CORE_SECRET
    always @(posedge clk) begin
        out <= jarvi3_core_secret;
    end
endmodule
