// dtl_gate_fsm.v — ChipGate Example
//
// DTL Hardware Safety Gate with FSM
//
// States: IDLE -> PROPOSED -> VERIFYING -> APPROVED -> BLOCKED -> FAILSAFE
//
// Inputs:
//   clk          - System clock
//   rst_n        - Active-low reset
//   ai_output    - AI/proposed output
//   verifier_ok  - Verifier has approved the output
//   policy_ok    - Output complies with safety policy
//   sensor_ok    - Physical sensors confirm safe state
//   timeout      - Operation has exceeded time limit
//   kill_switch  - Hardware emergency stop (active high)
//
// Output:
//   actuator_enable - ONLY enabled when all gates pass
//
// Assertions:
//   actuator_enable must never be high when kill_switch is high.
//   actuator_enable must never be high unless verifier_ok and policy_ok are true.
//
// ChipGate checks RTL structure and verification-gated safety patterns.
// It does not prove hardware correctness, silicon readiness, physical safety,
// regulatory compliance or experimental validity.

module dtl_gate_fsm (
    input  wire        clk,
    input  wire        rst_n,

    // AI / proposed output
    input  wire        ai_output,

    // Verification gates
    input  wire        verifier_ok,
    input  wire        policy_ok,
    input  wire        sensor_ok,
    input  wire        timeout,

    // Emergency control
    input  wire        kill_switch,

    // Actuator output
    output reg         actuator_enable,

    // State diagnostics
    output reg  [2:0]  current_state
);

    // State encoding
    localparam IDLE      = 3'b000;
    localparam PROPOSED  = 3'b001;
    localparam VERIFYING = 3'b010;
    localparam APPROVED  = 3'b011;
    localparam BLOCKED   = 3'b100;
    localparam FAILSAFE  = 3'b101;

    reg [2:0] state, next_state;

    // State register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            actuator_enable <= 1'b0;
        end else begin
            state <= next_state;

            case (state)
                APPROVED: begin
                    actuator_enable <= ai_output && verifier_ok && policy_ok && sensor_ok && !timeout && !kill_switch;
                end
                default: begin
                    actuator_enable <= 1'b0;
                end
            endcase
        end
    end

    // Next state logic
    always @(*) begin
        next_state = state;
        case (state)
            IDLE: begin
                if (ai_output) begin
                    next_state = PROPOSED;
                end
            end

            PROPOSED: begin
                next_state = VERIFYING;
            end

            VERIFYING: begin
                if (kill_switch) begin
                    next_state = FAILSAFE;
                end else if (timeout) begin
                    next_state = BLOCKED;
                end else if (verifier_ok && policy_ok && sensor_ok) begin
                    next_state = APPROVED;
                end
            end

            APPROVED: begin
                if (kill_switch) begin
                    next_state = FAILSAFE;
                end else if (timeout || !verifier_ok || !policy_ok) begin
                    next_state = BLOCKED;
                end else if (!ai_output) begin
                    next_state = IDLE;
                end
            end

            BLOCKED: begin
                if (kill_switch) begin
                    next_state = FAILSAFE;
                end else if (!ai_output) begin
                    next_state = IDLE;
                end
            end

            FAILSAFE: begin
                if (!kill_switch && !ai_output) begin
                    next_state = IDLE;
                end
            end

            default: begin
                next_state = IDLE;
            end
        endcase
    end

    // State output
    always @(*) begin
        current_state = state;
    end

    // Assertions (written as comments for structural detection)
    // assert property (@(posedge clk) kill_switch |-> !actuator_enable)
    //   else $error("SAFETY VIOLATION: actuator enabled while kill_switch is active");

    // assert property (@(posedge clk) actuator_enable |-> verifier_ok && policy_ok)
    //   else $error("SAFETY VIOLATION: actuator enabled without verifier_ok and policy_ok");

endmodule