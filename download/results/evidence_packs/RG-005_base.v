module unsafe_base (
    input  clk,
    input  ai_output,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output;
    end
endmodule