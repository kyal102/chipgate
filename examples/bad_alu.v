// A deliberately broken "ALU": trips several ChipGate Lite checks.
//  - case without default + if without else  -> latch-inference risk
//  - blocking '=' in an edge-triggered block -> sequential style hazard
//  - 'status' output is never assigned       -> undriven output
module bad_alu (
    input  wire       clk,
    input  wire [1:0] op,
    input  wire [7:0] a,
    input  wire [7:0] b,
    output reg  [7:0] y,
    output wire       status
);
    always @(*) begin
        case (op)
            2'b00: y = a + b;
            2'b01: y = a - b;
            2'b10: y = a & b;
        endcase
        if (op == 2'b11)
            y = a | b;
    end

    reg [7:0] acc;
    always @(posedge clk) begin
        acc = acc + y;   // blocking '=' in sequential logic
    end
endmodule
