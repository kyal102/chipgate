// ChipGate TinyTapeoutPrep - Physical Flow DTL Gate
// Public-safe minimal DTL safety gate for OpenLane physical readiness.
// This is NOT a real tapeout design.

module tiny_dtl_gate_physical (
    input  wire clk,
    input  wire rst_n,
    input  wire ai_output,
    input  wire verifier_ok,
    input  wire policy_ok,
    input  wire sensor_ok,
    input  wire timeout,
    input  wire kill_switch,
    input  wire reset,
    output wire actuator_enable,
    output wire status_out,
    output wire diag_0,
    output wire diag_1,
    output wire diag_2
);

    // DTL safety gate: all conditions must be met
    wire gate = ai_output & verifier_ok & policy_ok & sensor_ok;
    wire safe = ~timeout & ~kill_switch & ~reset & rst_n;

    assign actuator_enable = gate & safe;

    // Diagnostic outputs
    assign status_out = safe;
    assign diag_0 = gate;
    assign diag_1 = verifier_ok & policy_ok;
    assign diag_2 = sensor_ok & ~timeout;

endmodule