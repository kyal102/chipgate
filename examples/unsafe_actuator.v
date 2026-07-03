// unsafe_actuator.v — ChipGate Example
//
// This design is INTENTIONALLY UNSAFE.
// ChipGate should flag: UNGATED_OUTPUT, missing reset, missing kill_switch,
// missing verifier_ok, missing policy_ok, no assertions.
//
// ChipGate checks RTL structure and verification-gated safety patterns.
// It does not prove hardware correctness, silicon readiness, physical safety,
// regulatory compliance or experimental validity.

module unsafe_actuator (
    input  clk,
    input  ai_output,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output;
    end
endmodule