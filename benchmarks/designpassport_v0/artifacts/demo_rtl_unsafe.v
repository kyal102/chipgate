module unsafe_gate (
    input wire clk,
    input wire rst_n,
    input wire data_in,
    output reg data_out
);
    always @(posedge clk) begin
        data_out <= data_in;
    end
endmodule
