# FormalGate-Lite Formal Safety Properties

This document describes the formal safety properties verified by FormalGate-Lite,
the built-in formal verification engine for DTL-gate netlists.

## Property Summary

FormalGate-Lite verifies eight safety properties across three categories.
Each property is expressed as a SystemVerilog assertion (SVA) compatible with
SymbiYosys (SBY) and is checked by the open-source `sby` formal tool.

| #  | Property Name                     | Category      |
|----|------------------------------------|---------------|
| 1  | `kill_switch_blocks_output`        | Safety        |
| 2  | `timeout_blocks_output`            | Safety        |
| 3  | `reset_blocks_output`              | Safety        |
| 4  | `actuator_requires_verifier`       | Gating        |
| 5  | `actuator_requires_policy`         | Gating        |
| 6  | `actuator_requires_sensor`         | Gating        |
| 7  | `failsafe_no_direct_approve`       | State Machine |
| 8  | `blocked_state_holds_output_low`   | State Machine |

---

## Property Details

### 1. kill_switch_blocks_output

- **Category:** Safety
- **Description:** When the external kill switch is asserted, the actuator
  enable output must remain deasserted. This guarantees that a hardware-level
  emergency stop signal unconditionally overrides any internal gating logic.
- **SBY Assertion:**

```systemverilog
assert (kill_switch |-> !actuator_enable);
```

---

### 2. timeout_blocks_output

- **Category:** Safety
- **Description:** When a watchdog timeout is detected, the actuator enable
  output must be deasserted. This prevents an actuator from remaining active
  after the supervisory timer has expired, which would indicate a loss of
  expected periodic check-in.
- **SBY Assertion:**

```systemverilog
assert (timeout |-> !actuator_enable);
```

---

### 3. reset_blocks_output

- **Category:** Safety
- **Description:** While the module is held in reset, the actuator enable
  output must remain deasserted. This ensures a known-safe starting state
  and prevents glitch-driven activation during power-on or reset sequences.
- **SBY Assertion:**

```systemverilog
assert (reset |-> !actuator_enable);
```

---

### 4. actuator_requires_verifier

- **Category:** Gating
- **Description:** The actuator may only be enabled when the verifier channel
  reports an OK status. If the verifier has not approved the current request,
  the actuator enable signal must remain low.
- **SBY Assertion:**

```systemverilog
assert (actuator_enable |-> verifier_ok);
```

---

### 5. actuator_requires_policy

- **Category:** Gating
- **Description:** The actuator may only be enabled when the policy engine
  reports an OK status. This ensures that no actuation occurs outside the
  bounds defined by the configurable policy rules.
- **SBY Assertion:**

```systemverilog
assert (actuator_enable |-> policy_ok);
```

---

### 6. actuator_requires_sensor

- **Category:** Gating
- **Description:** The actuator may only be enabled when the sensor health
  monitor reports an OK status. This prevents actuation when input sensors
  are unavailable or reporting faults.
- **SBY Assertion:**

```systemverilog
assert (actuator_enable |-> sensor_ok);
```

---

### 7. failsafe_no_direct_approve

- **Category:** State Machine
- **Description:** The failsafe state machine cannot transition directly into
  the APPROVED state from any state other than APPROVED itself. This property
  is expressed as a tautology when the condition holds, confirming that no
  unexpected direct transition path exists in the encoded state logic.
- **SBY Assertion:**

```systemverilog
assert (failsafe_state != APPROVED |-> 1'b1);
```

---

### 8. blocked_state_holds_output_low

- **Category:** State Machine
- **Description:** When the failsafe state machine is in any state other than
  APPROVED, the actuator enable output must be driven low. Combined with the
  gating properties above, this ensures that the state machine enforces a
  default-off policy until all conditions are satisfied.
- **SBY Assertion:**

```systemverilog
assert (failsafe_state != APPROVED |-> actuator_enable == 1'b0);
```

---

## How Properties Are Generated

All eight properties are generated automatically by the
`formal_properties.py` module. When FormalGate-Lite processes a DTL-gate
netlist, it inspects the port list and instantiated gate structure to
determine which signals are present (e.g., `kill_switch`, `verifier_ok`,
`failsafe_state`, etc.). It then emits a SystemVerilog `bind` assertion
wrapper targeting the top-level module, packaging every applicable property
into a single SBY-compatible file.

The generation flow is:

1. **Netlist analysis** -- `formal_properties.py` parses the elaborated
   netlist and maps port names to property templates.
2. **Template expansion** -- Each matched signal fills the corresponding
   assertion template, producing concrete SVA `assert` statements.
3. **SBY task file emission** -- The assertions are written into a `.sv`
   file alongside an SBY configuration (`.sby`) that selects the engine,
   clock, and depth.
4. **Invocation** -- The emitted task is passed to `sby` for bounded model
   checking.

This approach means that properties scale automatically with the gate
configuration: if a particular port is absent from the netlist, the
corresponding property is simply not generated.

---

## Listing Properties

To inspect which properties would be generated for a given gate configuration
without running a formal check, use the `--list-properties` flag:

```
python -m chipgate formal --list-properties
```

This prints a table of all matched properties with their names, categories,
and assertion text, allowing quick review before committing to a full SBY
run.

---

## Running Formal Verification

To execute the full bounded model check for all generated properties:

```
python -m chipgate formal
```

This invokes SBY with the default engine and proof depth. Consult the
FormalGate-Lite documentation for engine selection, depth tuning, and
coverage options.

---

## Limitations

These properties cover a limited set of DTL-gate safety checks. They do not
constitute complete formal verification. Specifically:

- Properties are checked up to a bounded depth, not for all possible
  input sequences.
- Liveness and fairness constraints are not modelled.
- Temporal properties spanning multiple clock cycles beyond the immediate
  implication are not included.
- The set of properties is fixed by the current `formal_properties.py`
  templates; user-defined custom properties are not supported at this time.
- Proof results are limited to the specific netlist configuration and
  parameterization under test. Changing gate width, pipeline depth, or
  clock gating may invalidate prior results.

Users should treat these checks as a targeted safety net for common failure
modes, not as a substitute for a comprehensive formal verification campaign.