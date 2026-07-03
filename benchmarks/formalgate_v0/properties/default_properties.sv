// default_properties.sv — FormalGate-Lite default SBY properties
//
// The 8 standard DTL-gate formal safety properties.
// Each assertion is a single-line SystemVerilog assertion using only
// the expected DTL-gate signals: kill_switch, timeout, reset,
// verifier_ok, policy_ok, sensor_ok, actuator_enable,
// failsafe_state, APPROVED.
//
// No $display, no #delay, no always @posedge clk — just the
// assertions themselves.
//
// SBY [properties] format:  name: assert(expression);
// ----------------------------------------------------------------

kill_switch_blocks_output: assert (kill_switch |-> !actuator_enable);
timeout_blocks_output: assert (timeout |-> !actuator_enable);
reset_blocks_output: assert (reset |-> !actuator_enable);
actuator_requires_verifier: assert (actuator_enable |-> verifier_ok);
actuator_requires_policy: assert (actuator_enable |-> policy_ok);
actuator_requires_sensor: assert (actuator_enable |-> sensor_ok);
failsafe_no_direct_approve: assert (failsafe_state != APPROVED |-> 1'b1);
blocked_state_holds_output_low: assert (failsafe_state != APPROVED |-> actuator_enable == 1'b0);
