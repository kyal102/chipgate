module dtl_gate_fast (
    input clk,
    input rst,
    input ai_output,
    output actuator_enable
);
    assign actuator_enable = ai_output;
endmodule