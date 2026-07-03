# Mutation Catalog

This document describes each mutation category in the MutationBench catalog.

## Unsafe Bypass Group

### remove_verifier_gate
**Description:** Removes `verifier_ok` from the actuator enable condition.
**Example:**
```verilog
// Before:
actuator_enable <= ai_output && verifier_ok && policy_ok;
// After:
actuator_enable <= ai_output && policy_ok;
```
**Criticality:** Critical — must be 100% detected.

### remove_policy_gate
**Description:** Removes `policy_ok` from the actuator enable condition.
**Example:**
```verilog
// Before:
actuator_enable <= ai_output && verifier_ok && policy_ok;
// After:
actuator_enable <= ai_output && verifier_ok;
```
**Criticality:** Critical — must be 100% detected.

### remove_sensor_gate
**Description:** Removes `sensor_ok` from the actuator enable condition.
**Criticality:** Critical — must be 100% detected.

### direct_actuator_bypass
**Description:** Replaces the gated actuator assignment with a direct `ai_output` passthrough.
**Example:**
```verilog
// After:
assign actuator_enable = ai_output;
```
**Criticality:** Critical — must be 100% detected.

### or_bypass
**Description:** Changes safe AND chains to unsafe OR chains in the gating condition.
**Example:**
```verilog
// Before:
actuator_enable <= ai_output && verifier_ok;
// After:
actuator_enable <= ai_output || verifier_ok;
```
**Criticality:** Critical — must be 100% detected.

### failsafe_escape
**Description:** Allows the FSM to jump directly from the BLOCKED state to the APPROVED state, bypassing the normal recovery path.
**Criticality:** Critical — must be 100% detected.

### blocked_escape
**Description:** Allows the BLOCKED state to transition directly to APPROVED when `ai_output` is high, without verification.
**Criticality:** Critical — must be 100% detected.

### unsafe_pin_exposure
**Description:** Exposes `actuator_enable` directly in a TinyTapeout/FPGA wrapper without gating proof.
**Criticality:** Critical — must be 100% detected.

## Safety Group

### invert_kill_switch
**Description:** Inverts the kill switch polarity so `!kill_switch` becomes `kill_switch`.
**Criticality:** Critical — must be 100% detected.

### remove_timeout_block
**Description:** Removes the `!timeout` blocking condition from the gating chain.
**Criticality:** Critical — must be 100% detected.

### remove_reset_block
**Description:** Removes the `!reset` blocking condition from the gating chain.
**Criticality:** Critical — must be 100% detected.

### glitchy_reset
**Description:** Allows actuator output to be driven during the reset transition, creating a glitch window.
**Criticality:** Critical — must be 100% detected.

## Structural Group

### stale_verifier
**Description:** Injects a wire `stale_verifier_ok = 1'b1` that is always high, then replaces `verifier_ok` with this stale signal.
**Criticality:** High — must be detected.

### shadow_signal
**Description:** Creates a new alias wire `hidden_enable` that routes actuator output around the safety gate.
**Criticality:** High — must be detected.

### obfuscated_expression
**Description:** Uses nested ternary operators and brace formatting to hide the removal of safety gates.
**Criticality:** High — must be detected.

### multiline_bypass
**Description:** Splits an unsafe assignment across multiple lines to evade single-line pattern matching.
**Criticality:** High — must be detected.

### duplicate_assignment
**Description:** Creates conflicting assignments for `actuator_enable` — one gated and one direct.
**Criticality:** High — must be detected.

### unsafe_default_state
**Description:** Changes the FSM default state from IDLE to APPROVED, so the actuator starts enabled.
**Criticality:** High — must be detected.

### missing_safety_output
**Description:** Removes the blocked/failsafe output signal declaration.
**Criticality:** High — must be detected.

## Hygiene Group

### private_leak
**Description:** Injects a forbidden private name reference (e.g., "jarvi3") into the RTL and confirms the hygiene scanner catches it.
**Criticality:** Critical — must be 100% detected.

## Summary

| # | Category | Group | Criticality | Must Detect |
|---|----------|-------|-------------|-------------|
| 1 | remove_verifier_gate | unsafe_bypass | critical | Yes |
| 2 | remove_policy_gate | unsafe_bypass | critical | Yes |
| 3 | remove_sensor_gate | unsafe_bypass | critical | Yes |
| 4 | invert_kill_switch | safety | critical | Yes |
| 5 | remove_timeout_block | safety | critical | Yes |
| 6 | remove_reset_block | safety | critical | Yes |
| 7 | direct_actuator_bypass | unsafe_bypass | critical | Yes |
| 8 | or_bypass | unsafe_bypass | critical | Yes |
| 9 | stale_verifier | structural | high | Yes |
| 10 | failsafe_escape | unsafe_bypass | critical | Yes |
| 11 | blocked_escape | unsafe_bypass | critical | Yes |
| 12 | glitchy_reset | safety | critical | Yes |
| 13 | shadow_signal | structural | high | Yes |
| 14 | obfuscated_expression | structural | high | Yes |
| 15 | multiline_bypass | structural | high | Yes |
| 16 | duplicate_assignment | structural | high | Yes |
| 17 | unsafe_default_state | structural | high | Yes |
| 18 | missing_safety_output | structural | high | Yes |
| 19 | unsafe_pin_exposure | unsafe_bypass | critical | Yes |
| 20 | private_leak | hygiene | critical | Yes |