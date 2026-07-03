# FormalGate-Lite

FormalGate-Lite is the ChipGate Phase 12 formal safety property checker. It
generates SBY (SymbiYosys) property files for small DTL-gated RTL designs,
optionally runs bounded model checks where SymbiYosys and Yosys are installed,
parses SBY reports, and creates evidence artifacts.

FormalGate-Lite runs structural formal property checks on small DTL-gated RTL
designs. It does not prove chip correctness, fabrication readiness, timing
signoff, physical safety, or real-world actuation safety.

---

## Table of Contents

- [What FormalGate-Lite Checks](#what-formalgate-lite-checks)
- [How It Connects to Other Benchmarks](#how-it-connects-to-other-benchmarks)
- [Running the Demo](#running-the-demo)
- [Running with SymbiYosys and Yosys](#running-with-symbiyosys-and-yosys)
- [Output Formats](#output-formats)
- [Reading Pass / Fail / Skipped Statuses](#reading-pass--fail--skipped-statuses)
- [Property Reference Table](#property-reference-table)
- [Status Reference](#status-reference)
- [What the Benchmark Does NOT Prove](#what-the-benchmark-does-not-prove)
- [What the Benchmark Does NOT Guarantee](#what-the-benchmark-does-not-guarantee)
- [Limitations and Honest Claims](#limitations-and-honest-claims)

---

## What FormalGate-Lite Checks

FormalGate-Lite checks structural safety properties on small DTL-gated Verilog
designs. For each design, it:

1. **Scans the RTL** using the ChipGate scanner to verify basic safety patterns
   (gating, kill switch, reset, assertions).
2. **Generates SBY property files** containing formal assertions derived from
   the safety patterns found in the design.
3. **Optionally runs SymbiYosys** to execute bounded model checks (BMC) against
   those properties, if SBY and Yosys are installed.
4. **Parses SBY reports** to extract pass/fail/timeout/inconclusive results for
   each property.
5. **Creates evidence artifacts** including property files, SBY logs (when
   available), and evidence packs with SHA-256 hashes.

The properties checked include, but are not limited to:

- Kill switch deassertion forces safe output within bounded cycles
- No unreachable safe states under reset
- Gating signals (verifier_ok, policy_ok) are not simultaneously bypassed
- Reset recovery reaches a known-safe state
- No combinational loops that could cause indeterminate behaviour
- Output does not toggle when all gating signals are deasserted

---

## How It Connects to Other Benchmarks

FormalGate-Lite is part of the ChipGate verification pipeline and connects to
other benchmarks as follows:

| Benchmark | Relationship |
|-----------|--------------|
| **ChipGate (core scanner)** | FormalGate-Lite uses the core scanner to detect safety patterns. Properties are generated from scanner findings. |
| **LongevityBench** | LongevityBench checks RTL-level reliability and stress patterns. FormalGate-Lite can add formal proof of longevity-related properties (e.g., no latch inference, no combinational loops). |
| **SiliconReadinessBench** | SiliconReadinessBench checks tool-flow readiness (lint, synthesis, formal). FormalGate-Lite provides a deeper set of formal properties beyond the basic `FORMAL_READY` check. |
| **OpenLanePhysicalBench** | OpenLanePhysicalBench checks physical-flow readiness (DRC, LVS, timing). FormalGate-Lite complements this by proving logical safety properties before physical implementation. FormalGate-Lite results may trigger `NEEDS_PHYSICAL_SIGNOFF` when all formal properties pass. |

The pipeline is designed to be cumulative: designs that pass FormalGate-Lite
can proceed to SiliconReadinessBench and then OpenLanePhysicalBench with
increasing confidence (but never certainty) that the design is safe.

---

## Running the Demo

```bash
# Run the built-in demo designs
python -m chipgate formal --demo

# JSON output
python -m chipgate formal --demo --json

# HTML report
python -m chipgate formal --demo --html formal_demo_report.html
```

The demo uses built-in DTL gate designs with known safety patterns. It
generates property files and prints results to the terminal. If SBY/Yosys are
not installed, properties are marked as `FORMAL_PROPERTY_SKIPPED` with
`FORMAL_SOLVER_MISSING`.

---

## Running with SymbiYosys and Yosys

When SymbiYosys and Yosys are installed, FormalGate-Lite can run real bounded
model checks:

```bash
# Check if formal tools are available
python -m chipgate formal --toolchain-status

# Run with real SBY (if installed)
python -m chipgate formal benchmarks/formalgate_v0 --json

# Full mode with explicit SBY invocation
python -m chipgate formal benchmarks/formalgate_v0 --full --json
```

### Toolchain Detection

| Tool | Detection Method | Used For |
|------|-----------------|----------|
| `sby` (SymbiYosys) | `sby --version` | Bounded model checking |
| `yosys` | `yosys --version` | Synthesis backend for SBY |
| `verilator` | `verilator --version` | Optional pre-check linting |

Missing tools are recorded as `FORMAL_SOLVER_MISSING`, never as failures.
The bench produces valid results with or without external tools installed.

---

## Output Formats

### Terminal

By default, results are printed to the terminal with ANSI colour coding.

### JSON

```bash
python -m chipgate formal --demo --json
```

Outputs a JSON object containing the full `FormalBenchResult` structure:
overall status, timestamp, metrics, per-design property results, evidence
packs, manual review items, public wording, and limitation text.

### HTML

```bash
python -m chipgate formal --demo --html formal_report.html
```

Generates a self-contained, static, dependency-free HTML report with inline
CSS (no JavaScript). The report includes:

- Summary cards (overall status, properties passed/failed/skipped)
- Design results table
- Per-property breakdown per design
- Manual review items
- Public disclaimer and limitation text

---

## Reading Pass / Fail / Skipped Statuses

Each formal property is assigned one of the following statuses:

| Status | Meaning |
|--------|---------|
| `FORMAL_PROPERTY_PASS` | The property was proven (BMC passed up to the bound, or structure was verified) |
| `FORMAL_PROPERTY_FAIL` | The property was disproven (counterexample found) |
| `FORMAL_PROPERTY_SKIPPED` | The property was not checked (solver not installed, or design not applicable) |
| `FORMAL_INCONCLUSIVE` | The solver could not determine pass or fail within the bound |
| `FORMAL_TIMEOUT` | The solver timed out before reaching a conclusion |
| `FORMAL_COUNTEREXAMPLE_FOUND` | A counterexample trace was generated (implies FAIL) |
| `FORMAL_SOLVER_MISSING` | SBY or Yosys was not available on the system |

### Important: SKIPPED Is Not FAIL

A property marked `FORMAL_PROPERTY_SKIPPED` with `FORMAL_SOLVER_MISSING` means
the formal solver was not installed. It does **not** mean:

- The property failed
- The design is unsafe
- The property is irrelevant

It simply means the tool was not available for this run. The property file
was still generated and can be run manually with an SBY installation.

---

## Property Reference Table

| Property ID | Category | Description |
|-------------|----------|-------------|
| `fg_kill_switch_deassert` | Safety | Kill switch deassertion forces safe output within N cycles |
| `fg_reset_recovery` | Safety | Reset recovery reaches a known-safe state |
| `fg_gating_no_bypass` | Safety | Gating signals (verifier_ok, policy_ok) cannot be simultaneously bypassed |
| `fg_no_combinational_loop` | Structure | No combinational loops that could cause indeterminate behaviour |
| `fg_output_quiescent` | Safety | Output does not toggle when all gating signals are deasserted |
| `fg_assertion_holds` | Verification | All SystemVerilog assertions in the design hold under bounded check |
| `fg_no_latch_inference` | Structure | No transparent latches are inferred in the synthesised design |
| `fg_state_machine_reachable` | Structure | All FSM states are reachable from the reset state |
| `fg_output_default_safe` | Safety | Default output state is safe (deasserted) before any verification gate |
| `fg_no_ungated_path` | Safety | No direct path from input to actuation output bypassing the verification gate |

Property definitions may evolve between versions. Use
`python -m chipgate formal --list-properties` to see the current set.

---

## Status Reference

FormalGate-Lite introduces 12 new statuses. These are distinct from the
existing scan, bench, silicon-readiness, and CI statuses.

### Per-Property Statuses

| Status | Meaning |
|--------|---------|
| `FORMAL_PROPERTY_PASS` | Property proven or structurally verified |
| `FORMAL_PROPERTY_FAIL` | Property disproven (counterexample found) |
| `FORMAL_PROPERTY_SKIPPED` | Property not checked (solver missing or not applicable) |
| `FORMAL_INCONCLUSIVE` | Solver could not determine result within bound |
| `FORMAL_TIMEOUT` | Solver timed out |
| `FORMAL_COUNTEREXAMPLE_FOUND` | Counterexample trace generated |
| `FORMAL_SOLVER_MISSING` | SBY/Yosys not available |
| `PROPERTY_FILE_CREATED` | SBY property file was generated |
| `FORMAL_EVIDENCE_CREATED` | Formal evidence artifact was created |

### Cross-Phase Statuses

| Status | Meaning |
|--------|---------|
| `NEEDS_DEEP_FORMAL_REVIEW` | One or more properties need expert formal verification review |
| `NEEDS_PHYSICAL_SIGNOFF` | Formal properties passed; design is a candidate for physical signoff |
| `EVIDENCE_PACK_CREATED` | Evidence pack with SHA-256 hashes was generated |

---

## What the Benchmark Does NOT Prove

> Passing FormalGate-Lite does not prove chip correctness, fabrication
> readiness, timing signoff, physical safety, or real-world actuation safety.

Specifically, FormalGate-Lite does **not**:

- **Prove chip correctness** -- a `FORMAL_PROPERTY_PASS` means a specific
  bounded property held. It does not mean the entire design is functionally
  correct, free of bugs, or verified for all possible inputs and states.
- **Prove fabrication readiness** -- no DRC, LVS, or physical verification is
  performed. A design that passes formal checks may still have physical
  layout errors.
- **Prove timing signoff** -- no static timing analysis is performed. A
  formally verified design may still fail timing at any clock frequency.
- **Prove physical safety** -- formal properties are checked against an
  abstract RTL model. Real-world physical effects (voltage droop, thermal
  runaway, EM, latch-up) are not modeled.
- **Prove real-world actuation safety** -- the formal model does not include
  the physical actuator, power electronics, mechanical load, or
  environmental conditions. Formal verification of RTL alone cannot guarantee
  safe actuation.
- **Replace professional formal verification** -- FormalGate-Lite runs a
  bounded set of properties on small designs. Professional formal
  verification uses unbounded proofs, comprehensive cover property suites,
  and expert-driven property elaboration.
- **Certify for safety-critical use** -- no medical, defence, aerospace, or
  robotics certification is implied or provided.

---

## What the Benchmark Does NOT Guarantee

FormalGate-Lite provides structural checks and optional bounded model checking
results. The following are **not** guaranteed:

1. **Completeness** -- The property suite does not cover all possible safety
   properties. A design may pass all checked properties and still have
   uncaught safety issues.
2. **Soundness without real solver** -- When SBY/Yosys are not installed,
   properties are generated but not proven. The output is a list of properties,
   not a list of proofs.
3. **Bounded vs unbounded** -- Even with SBY, properties are checked up to a
   bounded depth. A bug that requires more cycles to manifest will not be
   caught.
4. **No false negatives guaranteed** -- The checker may produce false
   negatives (reporting a property as INCONCLUSIVE when it is actually FAIL)
   due to solver limitations or insufficient bounds.
5. **Determinism** -- SBY solver results may vary between versions, platforms,
   and random seeds. Replay stability is not guaranteed for solver outcomes.
6. **Scalability** -- FormalGate-Lite is designed for small DTL-gated designs
   (tens to hundreds of lines of Verilog). It is not suitable for large-scale
   SoC or processor designs.

---

## Limitations and Honest Claims

### Core Limitation

> FormalGate-Lite runs structural formal property checks on small DTL-gated
> RTL designs. It does not prove chip correctness, fabrication readiness,
> timing signoff, physical safety, or real-world actuation safety.

FormalGate-Lite is a lightweight property checker. It generates SBY property
files, optionally runs bounded model checks, and parses results. It does not
perform exhaustive formal verification, unbounded proof, or full property
elaboration.

### SKIPPED Means Solver Not Installed

A property marked with `FORMAL_PROPERTY_SKIPPED` and `FORMAL_SOLVER_MISSING`
means the formal solver was not installed or not found on the system. It does
**not** mean:

- The property failed
- The design has a defect
- The property was attempted and produced an error

A result with multiple SKIPPED properties on a system without SBY/Yosys is
expected and normal. Only `FORMAL_PROPERTY_FAIL` and
`FORMAL_COUNTEREXAMPLE_FOUND` indicate actual property violations.

### No Claim of Real Power, Real Area, Real Timing

FormalGate-Lite does not measure, estimate, or claim:

- **Real power consumption** -- No dynamic or leakage power analysis.
- **Real area** -- No gate-level area measurement or die area estimation.
- **Real timing** -- No static timing analysis, no setup/hold verification,
  no clock domain crossing analysis.

### No NVIDIA Comparison

FormalGate-Lite does not compare to, benchmark against, or make any claims
relative to any NVIDIA product, tool, workflow, or design methodology.

### No Medical, Defence, or Robotics Certification

FormalGate-Lite is not certified, validated, or suitable as evidence for any
regulated application:

- **Medical devices** -- Does not meet IEC 60601, FDA guidance, or medical
  device regulatory requirements.
- **Defence and aerospace** -- Does not meet DO-254, MIL-STD-882, or
  equivalent standards.
- **Robotics and autonomous systems** -- Does not validate real-time
  constraints, sensor fusion correctness, or motion safety envelopes.
- **Safety-critical deployment** -- Must not be used as the primary means of
  demonstrating functional safety for any system where failure could result in
  personal injury, death, environmental damage, or significant property damage.

### English-Only, Public-Safe Wording

All output from FormalGate-Lite uses English-only, public-safe language. The
`FORMALGATE_PUBLIC_WORDING` and `FORMALGATE_LIMITATION` fields are included in
every JSON output and HTML report. These fields must not be omitted when
results are shared, published, or used for decision-making.

The mandatory wording is:

> FormalGate-Lite runs structural formal property checks on small DTL-gated
> RTL designs. It does not prove chip correctness, fabrication readiness,
> timing signoff, physical safety, or real-world actuation safety.

The limitation text is:

> FormalGate-Lite generates SBY property files and optionally runs bounded
> model checks. Passing does not mean the design is verified, correct, or
> safe. A SKIPPED property means the solver was not available, not that the
> property was verified.

### Honest Claims

You can honestly claim:

- FormalGate-Lite generated SBY property files for a set of DTL-gated designs.
- Specific properties passed, failed, or were skipped (with reasons).
- An evidence pack with SHA-256 hashes was generated.
- The formal report shows specific property outcomes at a specific point in
  time on a specific system.

You cannot honestly claim:

- The design is correct, safe, or ready for fabrication.
- The design has been formally verified for any safety-critical application.
- A `FORMAL_PROPERTY_PASS` means the design is proven correct.
- A SKIPPED property was verified.
- The formal results are comparable to professional formal verification tools
  or flows.

### What Is Required for Real Formal Verification

Real formal verification requires:

- Comprehensive property elaboration by verification engineers
- Unbounded or inductive proofs, not just bounded model checking
- Cover property suites that exercise all design intent
- Constraint modelling for all environmental and interface assumptions
- Formal signoff review by qualified verification experts
- Correlation with simulation, emulation, and silicon testing
- Foundry-qualified PDK for any physical safety claims

FormalGate-Lite provides none of these. It is a lightweight property generation
and optional bounded-checking tool, not a replacement for professional formal
verification or physical signoff.