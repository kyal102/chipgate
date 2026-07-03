// bad_pin_constraints design — uses a separate constraints file
// FPGABoardBench demo: expected PIN_CONSTRAINT_FAIL (DUPLICATE_PIN_ASSIGNMENT)
//
// The constraints file for this design contains duplicate pin assignments.

module bad_pin_constraints (
    input  wire clk,
    input  wire rst_n,
    input  wire kill_switch,
    input  wire verifier_ok,
    input  wire policy_ok,
    input  wire ai_output,
    output reg  actuator_enable,
    output reg  safe_out,
    output reg  led_out
);

    initial begin
        actuator_enable = 1'b0;
        safe_out = 1'b0;
        led_out = 1'b0;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
            safe_out <= 1'b0;
            led_out <= 1'b0;
        end else begin
            actuator_enable <= ai_output & verifier_ok & policy_ok & ~kill_switch;
            safe_out <= verifier_ok & policy_ok & ~kill_switch;
            led_out <= safe_out;
        end
    end

endmodule