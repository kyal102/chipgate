# Tiny DTL Gate

The tiny DTL (Decision-Trust Layer) gate is a minimal safety circuit designed as a public demonstration for open silicon submission workflows. It implements the core DTL pattern: an autonomous or AI system output must pass through multiple verification checks before it can drive a physical actuator.

## Core Logic (Combinational Variant)

The combinational variant is a pure Boolean gate with no clock or sequential state:

```verilog
assign actuator_enable = ai_output && verifier_ok && policy_ok
                          && sensor_ok && !timeout && !kill_switch && !reset;
```

Seven input signals control one primary output and four status outputs. The output is asserted only when all conditions are simultaneously true and no safety override is active.

### Truth Table

| ai_out | vrf | pol | sen | tmo | kill | rst | ena | blk | fsf |
|--------|-----|-----|-----|-----|------|-----|-----|-----|-----|
| 0 | X | X | X | X | X | X | 0 | 0 | 1 |
| 1 | 0 | X | X | X | X | X | 0 | 1 | 1 |
| 1 | 1 | 0 | X | X | X | X | 0 | 1 | 1 |
| 1 | 1 | 1 | 0 | X | X | X | 0 | 1 | 1 |
| 1 | 1 | 1 | 1 | 1 | X | X | 0 | 1 | 1 |
| 1 | 1 | 1 | 1 | 0 | 1 | X | 0 | 1 | 1 |
| 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 1 |
| 1 | 1 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |

Where: vrf=verifier_ok, pol=policy_ok, sen=sensor_ok, tmo=timeout, kill=kill_switch, rst=reset, ena=actuator_enable, blk=blocked, fsf=failsafe, X=don't care.

## FSM Variant

The sequential variant implements the same safety properties using a state machine with six states:

```
IDLE -> PROPOSED -> VERIFYING -> APPROVED
  |         |           |
  +---------+-----------+--> BLOCKED
  |         |           |
  +---------+-----------+--> FAILSAFE
```

### State Descriptions

| State | Description | actuator_enable |
|-------|-------------|-----------------|
| IDLE | No request, system at rest | 0 |
| PROPOSED | AI request received, awaiting verification | 0 |
| VERIFYING | Verification in progress | 0 |
| APPROVED | All checks passed, actuator enabled | 1 |
| BLOCKED | Verification failed or condition missing | 0 |
| FAILSAFE | Safety override or fault condition | 0 |

### State Transitions

- **IDLE**: Stays idle unless `ai_output` requests a transition. Kill switch and timeout immediately trigger FAILSAFE.
- **PROPOSED**: Transitions to VERIFYING if all verification signals are high, or to BLOCKED if any are low.
- **VERIFYING**: Transitions to APPROVED if verification holds, or to BLOCKED if any signal drops.
- **APPROVED**: Remains approved only while all conditions hold. Any violation immediately goes to FAILSAFE.
- **BLOCKED**: Remains blocked until reset. Kill switch or timeout go to FAILSAFE.
- **FAILSAFE**: Remains in failsafe until reset. This is the safest state.

### Critical Safety Property

The FSM enforces that **FAILSAFE cannot jump directly to APPROVED**. The only path from FAILSAFE is back to IDLE (via reset), which then requires a full IDLE -> PROPOSED -> VERIFYING -> APPROVED sequence. This prevents a single reset glitch from re-enabling the actuator without passing through all verification stages.

## TinyTapeout Integration

Both variants are wrapped in a TinyTapeout-compatible top module (`tt_um_chipgate_dtl_gate`) that maps the 7 input signals to `ui_in[0:6]` and the 5 output signals to `uo_out[0:4]`. See `docs/TINYTAPEOUT_PREP.md` for full pin mapping details.

## Limitations

- This is a demonstration design, not a production safety controller
- The combinational variant has no glitch protection or filtering
- The FSM variant has no clock-domain crossing logic
- No debouncing, no metastability protection, no fault-tolerant redundancy
- Not certified for any safety standard (IEC 61508, ISO 26262, etc.)
- Does not prove silicon correctness, timing signoff, or power consumption
- Not suitable for medical, defence, or safety-critical robotics use