// safe_dtl_gate_fpga.v
// FPGABoardBench demo: expected safety pass, pin constraints pass
// Safe DTL-gated design for FPGA board testing
//
// This design gates actuator_enable behind verifier_ok, policy_ok,
// and !kill_switch. It includes clock, reset, and kill_switch inputs.
// Expected: safety precheck PASS, pin constraints PASS

module safe_dtl_gate_fpga (
    input  wire clk,
    input  wire rst_n,
    input  wire kill_switch,
    input  wire verifier_ok,
    input  wire policy_ok,
    input  wire ai_output,
    output reg  actuator_enable,
    output reg  safe_out
);

    // Safe default: all outputs low
    initial begin
        actuator_enable = 1'b0;
        safe_out = 1'b0;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
            safe_out <= 1'b0;
        end else begin
            // DTL gate chain: verifier_ok && policy_ok && !kill_switch
            actuator_enable <= ai_output & verifier_ok & policy_ok & ~kill_switch;
            safe_out <= verifier_ok & policy_ok & ~kill_switch;
        end
    end

    // Safety assertion
    `ifdef FORMAL
    always @(*) begin
        if (kill_switch)
            assert(actuator_enable == 1'b0);
    end
    `endif

endmodule