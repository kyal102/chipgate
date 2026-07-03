# ChipGate Known Limitations

ChipGate is a structural pattern-matching tool for Verilog/SystemVerilog RTL
code. It is designed to catch obviously unsafe designs before they proceed to
silicon, but it has significant limitations that must be understood before
relying on its results.

---

## Table of Contents

- [Parsing Limitations](#parsing-limitations)
- [Analysis Limitations](#analysis-limitations)
- [External Tool Integration](#external-tool-integration)
- [What ChipGate Does NOT Prove](#what-chipgate-does-not-prove)
- [Scope Limitations](#scope-limitations)
- [Design Space Limitations](#design-space-limitations)
- [Not Suitable For](#not-suitable-for)
- [Mandatory Disclaimer](#mandatory-disclaimer)

---

## Parsing Limitations

### Regex-Based Parsing (Not a Full Parser)

ChipGate uses regular expressions to extract structural elements from Verilog
and SystemVerilog source files. It does **not** implement a complete
language grammar or AST (abstract syntax tree).

**Consequences:**

- **No preprocessor support** — ` `define`, ` `include`, ` `ifdef`, and
  conditional compilation directives are not processed. Code behind ` `ifdef`
  guards will not be analysed.
- **No parameter/parameter overrides** — `parameter` and `localparam` values
  are not tracked through module instantiation hierarchies.
- **No generate block expansion** — `generate`/`for`/`if` constructs are not
  expanded or analysed.
- **No macro-awareness** — ` `define` macros used in expressions or port lists
  may cause the scanner to miss patterns or produce false negatives.
- **Limited port parsing** — Only basic `input`/`output` declarations with
  optional single-bit bus widths (`[N:0]`) are parsed. Multi-dimensional
  arrays, interface ports, and ANSI-style port declarations may not be fully
  handled.
- **Comment stripping is approximate** — Nested block comments or comments
  inside string literals may be incorrectly stripped.

### No Semantic Analysis or Type Checking

ChipGate performs purely structural pattern matching. It does **not**
understand:

- **Data types** — `wire`, `reg`, `logic`, `int`, `struct`, `union`, `enum`
  are treated identically when matching signal names.
- **Signal widths** — Bit width mismatches (e.g., assigning an 8-bit signal to
  a 1-bit port) are not detected.
- **Value propagation** — Constant folding, parameter evaluation, and signal
  value analysis are not performed.
- **Hierarchical references** — Cross-module signal references (e.g.,
  `module_a.signal_x`) are not resolved.
- **Operator semantics** — Logical vs. bitwise operators (`&&` vs `&`, `||`
  vs `|`) are not distinguished in gate detection.
- **Namespace resolution** — Packages, classes, and typedefs are not handled.

---

## Analysis Limitations

### No Synthesis or Timing Analysis

ChipGate operates exclusively on RTL source text. It does **not**:

- Estimate gate count, area, or power consumption
- Perform static timing analysis (STA)
- Detect timing violations, setup/hold issues, or clock domain crossings
- Analyse synthesis results or netlists
- Evaluate resource utilisation for FPGA targets
- Check for combinational loops orglitches

### Limited to Structural Pattern Matching

All checks are based on detecting textual patterns in the source code. This
means:

- **False negatives are possible** — Safety violations that use non-standard
  naming conventions, indirect assignments, or complex gate logic may be
  missed entirely.
- **False positives are possible** — Signals with actuator-like names (e.g.,
  `enable_debug`) that are not actually safety-critical may be flagged.
- **No control flow analysis** — The scanner does not trace signal flow
  through multiplexers, conditional assignments, or module hierarchies.
- **No data flow analysis** — Values are not propagated to determine whether
  a gate signal can actually influence the actuator output.
- **No state reachability analysis** — For FSM-based designs, ChipGate does
  not verify that all states are reachable or that unsafe states cannot be
  reached.

### No Coverage Analysis

ChipGate does **not** provide:

- Code coverage metrics (line, condition, toggle, path)
- Functional coverage analysis
- Assertion coverage tracking
- Verification completeness assessment

A design that passes all ChipGate rules may still have significant unverified
functionality.

---

## External Tool Integration

### Verilator (Lint)

The Verilator integration is **optional** and may be unavailable in many
environments:

- Verilator must be separately installed; ChipGate does not bundle it.
- When Verilator is not installed, lint checks are gracefully skipped — the
  scan will not fail, but external lint data will be absent.
- Verilator's own limitations apply: it does not support all SystemVerilog
  constructs and may report false positives for some valid code patterns.
- The 60-second timeout may not be sufficient for large designs.

### cocotb (Simulation)

The cocotb integration is currently a **placeholder**:

- The simulation module detects whether cocotb is installed but does not
  execute any tests.
- Future releases plan to support cocotb-based regression testing.
- No testbench generation is provided — users must write their own testbenches.

### SymbiYosys (Formal Verification)

The formal verification module checks **readiness only** — it does not
execute formal proofs:

- It detects whether assertions exist and whether SBY/Yosys are installed.
- It generates a sample `.sby` configuration file but does not run it.
- No BMC (bounded model checking) or induction proofs are performed.
- No proof results (PASS/FAIL/UNKNOWN) are reported.

### Integration Status Summary

| Tool | Status | What It Does |
|------|--------|--------------|
| Verilator | Optional, functional when installed | Runs `--lint-only -Wall` and parses output |
| cocotb | Placeholder, future | Detects availability only |
| Yosys | Detected, not invoked | Checks `which yosys` for readiness reporting |
| SBY | Detected, not invoked | Checks `which sby` for readiness reporting |

---

## What ChipGate Does NOT Prove

### Does Not Prove Hardware Correctness

A `RTL_SCAN_PASS` result means that **no obvious structural violations were
detected**. It does **not** mean:

- The design functions as intended
- All edge cases are handled correctly
- The logic is free of bugs
- The implementation matches the specification
- State machines are correct and complete

### Does Not Guarantee Silicon Readiness

ChipGate does **not** validate:

- Synthesis constraints and timing signoff
- Power integrity or signal integrity
- Foundry-specific design rules
- Package and pin mapping
- Manufacturing test coverage
- Silicon debuggability

### Does Not Replace Professional Verification Flows

ChipGate is a **pre-check** tool, not a replacement for:

- **Formal verification** — Property checking, equivalence checking, model
  checking
- **Simulation-based verification** — Directed tests, random testing,
  constrained-random verification
- **Lint and code review** — Systematic lint rules, coding standard checks,
  peer review processes
- **Timing analysis** — Static timing analysis, clock domain crossing
  verification
- **Physical verification** — DRC, LVS, RC extraction

### Does Not Handle All SystemVerilog Constructs

ChipGate is optimised for Verilog-2001 style RTL. It may not correctly handle:

- **SystemVerilog classes and objects**
- **UVM methodology constructs**
- **Interfaces and modports**
- **Virtual interfaces**
- **Covergroups and coverage models**
- **Program blocks**
- **Packages and imports**
- **Checker blocks**
- **DPI (Direct Programming Interface) calls**
- **Assertions with complex sequences** (detected by keyword but not analysed)
- **Clocking blocks**
- **Constraint blocks**

### No Support for Multi-File Designs in a Single Scan

Each invocation of `scan_file()` processes exactly one Verilog file:

- Cross-module references are not resolved.
- Multi-module files are handled (first module is used), but multi-file
  hierarchies are not.
- Use `scan_directory()` to scan multiple files, but each file is analysed
  independently — inter-module relationships are not evaluated.
- File-level dependencies (` `include`, instantiation hierarchy) are not
  resolved.

---

## Scope Limitations

### Actuator Detection Is Name-Based

ChipGate identifies actuator/safety-critical signals by matching against a
fixed list of known names and regex patterns:

```
actuator_enable, actuator_cmd, motor_enable, relay_on,
valve_open, heater_on, laser_enable, solenoid_on,
pump_enable, drive_enable, trigger_out, fire_cmd, deploy_cmd
```

Plus a general regex pattern for words like `actuator`, `motor`, `relay`,
`valve`, `heater`, `laser`, `solenoid`, `pump`, `drive`, `enable`,
`trigger`, `fire`, `deploy`.

**Limitation:** Designs that use non-standard names for safety-critical
outputs (e.g., `gpio_out`, `pwm_duty`, `dac_output`) will not be flagged,
even if they control physical actuators.

### Gate Detection Is Signal-Name-Based

The verification gate detection looks for specific signal names:

```
verifier_ok, policy_ok, kill_switch, sensor_ok, timeout
```

Designs that use functionally equivalent signals with different names
(e.g., `verified`, `policy_check`, `estop_n`, `sensor_valid`, `wdog_expire`)
will not be recognised as safety gates.

### Bypass Detection Is Expression-Heuristic

The bypass detection uses simple heuristics on assignment expressions:

- A single identifier → bypass (e.g., `assign out = in;`)
- A negated identifier → bypass (e.g., `assign out = !in;`)
- Complex expressions without gate signals → unsafe bypass path

These heuristics can miss sophisticated bypass patterns or flag safe patterns
that happen to use few signals.

---

## Design Space Limitations

### No Power/Area Estimation

ChipGate does not estimate:

- Dynamic or static power consumption
- Gate-level area utilisation
- FPGA resource usage (LUTs, FFs, BRAM, DSP)
- Thermal characteristics
- Clock tree synthesis feasibility

### No Clock Domain Crossing Analysis

ChipGate does not detect:

- Async clock domain crossings
- Missing synchroniser chains
- Metastability risks
- Clock gating issues

### No Bus Protocol Checking

ChipGate does not validate:

- AXI, AHB, APB, or Wishbone protocol compliance
- FIFO depth and overflow analysis
- Back-pressure handling
- Burst transfer correctness

---

## Not Suitable For

ChipGate is explicitly **not suitable** as a verification tool for designs
intended for deployment in:

### Medical Devices

ChipGate does not perform the verification rigour required by IEC 60601,
FDA guidance, or medical device regulations. A `RTL_SCAN_PASS` result must
never be used as evidence of medical device safety.

### Robotics and Autonomous Systems

ChipGate does not validate real-time constraints, sensor fusion correctness,
motion safety envelopes, or the complex interactions between hardware and
control software required for safe robotic operation.

### Defence and Aerospace

ChipGate does not meet the requirements of DO-254, MIL-STD-882, or equivalent
defence and aerospace standards. It must not be used as a sole verification
artifact for safety-critical avionics, weapons systems, or defence hardware.

### Safety-Critical Deployment Validation

ChipGate is a structural pre-check, not a safety validation tool. It must not
be used as the primary means of demonstrating functional safety for any
system where failure could result in:

- **Personal injury or death**
- **Environmental damage**
- **Significant property damage**
- **Loss of critical infrastructure**

For such applications, use industry-standard verification flows including
formal verification, simulation-based verification, timing analysis, and
independent safety assessment.

---

## Mandatory Disclaimer

The following disclaimer text is included in every ChipGate output and
**must always accompany results** when they are shared, published, or used
for decision-making:

> **ChipGate checks RTL structure and verification-gated safety patterns.
> It does not guarantee hardware correctness, silicon readiness, physical safety,
> regulatory conformance or experimental validity.**

This disclaimer is stored in the `public_wording` field of every ScanResult
and EvidencePack and must not be omitted.

### Implications

1. **Never claim** that ChipGate "verified" or "proved" a design is safe.
2. **Never use** ChipGate results alone to justify silicon production.
3. **Never present** ChipGate results as regulatory conformance evidence.
4. **Always run** additional verification (formal, simulation, lint, timing)
   before committing a design to production.
5. **Always include** the disclaimer when sharing ChipGate output with
   stakeholders, reviewers, or the public.
