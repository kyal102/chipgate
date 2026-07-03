# DTL-ChipBench Benchmark Documentation

## Overview

DTL-ChipBench is a **model-free benchmark** that tests the ChipGate/DTL
verification gate itself. It uses deterministic synthetic RTL proposals and
mutation-generated cases to measure whether unsafe or regressive chip-design
changes are blocked before heavier verification is needed. Model-connected
testing is a future phase.

The benchmark measures four properties of the deterministic gate:

1. **Gate correctness** -- whether the gate blocks known unsafe RTL patterns
   (ungated actuators, missing verifiers, kill-switch removals, timeout
   bypasses) and passes known-safe gated patterns.
2. **No-regression detection** -- whether the system detects when a previously
   safe baseline design is modified to remove required safety gates.
3. **Replayability** -- deterministic results: identical inputs produce
   identical gate decisions, certificate hashes, and evidence records across
   repeated runs.
4. **Estimated verification-cost reduction** -- under a transparent cost
   model, how many synthetic proposals are blocked before heavier
   verification would be required.

### Benchmark Scope

DTL-ChipBench currently tests the verification gate, not an AI model.

**Current phase:**

- Synthetic RTL proposals
- Mutation-generated unsafe/safe variants
- ChipGate deterministic rules
- No-regression checks
- Evidence packs
- Replay matching
- Transparent cost-model estimate

**Future phase:**

- Connect a real model as the proposal generator
- Freeze a public test set and private holdout
- Compare model-only vs model+DTL
- Measure unsafe accepts, safe accepts, regressions, heavy checks avoided,
  and cost per accepted verified change
- Publish results only after fresh holdout testing

### Public-Safe Wording

DTL-ChipBench does not guarantee chip correctness, silicon readiness, or physical
safety. It does not guarantee that any AI model is faster, safer, or better at
chip design. It measures whether a deterministic gating workflow can reduce
wasted verification work, block known unsafe RTL patterns, preserve safe
designs, and produce replayable evidence under a transparent benchmark. All
cost figures are abstract benchmark cost units, not measured silicon
performance, GPU performance, or real EDA cloud cost.

---

## Workflow Comparison

DTL-ChipBench compares two verification workflows side by side using
synthetic RTL proposals:

### Ungated Baseline Workflow

Every proposed RTL change (safe or unsafe) enters the full verification
pipeline unconditionally:

```
Synthetic RTL proposal
        |
        v
  Lint (5 units)
        |
        v
  Simulation (25 units)
        |
        v
  Formal verification (100 units)
        |
        v
  Synthesis (250 units)
        |
        v
  Total: 380 units per case
```

No filtering occurs. Unsafe designs consume the same resources as safe
designs. There is no early-exit path for clearly dangerous patterns.

### DTL-Gated Workflow

Every proposed RTL change first passes through a cheap deterministic scan:

```
Synthetic RTL proposal
        |
        v
  DTL Scan (1 unit)
        |
   +--------- blocked? -----> STOP (unsafe, no heavy checks)
   |
   v (passed)
  Lint (5 units)
        |
        v
  Simulation (25 units)
        |
        v
  Formal verification (100 units)
        |
        v
  Synthesis (250 units)
        |
        v
  Total: 381 units per non-blocked case
```

Cases that the DTL scan identifies as unsafe are blocked immediately. They
do not proceed to lint, simulation, formal verification, or synthesis. Only
cases that pass the DTL scan incur heavy verification cost.

---

## How to Run

### Demo Run (12 representative cases)

```bash
python -m chipgate bench --demo
```

Runs a small subset of cases spanning multiple categories. Useful for
quick validation and CI smoke tests.

### Full Benchmark with JSON Output

```bash
python -m chipgate bench --json
```

Runs all 121 cases and prints the full result set as structured JSON. The
output includes per-case details, aggregate metrics, the cost model, and
the benchmark hash.

### HTML Report

```bash
python -m chipgate bench --html report.html
```

Runs the full benchmark and writes a self-contained HTML report to the
specified path. The report includes summary cards, category breakdowns,
gate decision error tables, workflow comparison, cost model tables,
benchmark scope, and example blocked cases.

### Evidence Pack Generation

```bash
python -m chipgate bench --evidence
```

Runs the full benchmark and writes a per-case evidence record (JSON) for
each case. Each evidence pack contains the input hash, gate result,
certificate hash, statuses, regression status, and replay command. The
evidence pack count is reported in the aggregate results.

### Baseline Comparison (legacy)

```bash
python -m chipgate bench --compare-baseline
```

### Mode-Specific Runs (v0.3.0)

```bash
# Ungated baseline: everything goes to heavy verification
python -m chipgate bench --mode ungated_baseline --json

# ChipGate-only: deterministic public gates filter cases
python -m chipgate bench --mode chipgate_only --json

# External DTL: adapter-supplied proposals
python -m chipgate bench --mode external_dtl --adapter results/dtl_proposals.jsonl --json
```

### Multi-Mode Comparison (v0.3.0)

```bash
# Compare all three modes
python -m chipgate bench --compare-modes --html chipbench_compare.html

# Compare with external DTL adapter
python -m chipgate bench --compare-modes --adapter proposals.jsonl --html comparison.html
```

This runs ungated_baseline, chipgate_only, and (if adapter provided)
external_dtl modes, then generates a comparison HTML report with the
key metric: estimated cost per verified accepted change.

---

## Benchmark Categories

The 14 benchmark categories cover a range of unsafe patterns, safe designs,
regression scenarios, and adversarial edge cases. Each category contains
multiple cases with deterministic RTL and known expected outcomes.

### Unsafe Pattern Categories (should be blocked)

| Category | Cases | Risk Level | Description |
|---|---|---|---|
| `ungated_actuator` | 15 | critical | Actuator output driven directly by proposed signal without any verification gating |
| `missing_verifier_ok` | 12 | critical | `verifier_ok` gate absent from the actuator enable logic |
| `missing_policy_ok` | 12 | critical | `policy_ok` gate absent from the actuator enable logic |
| `missing_kill_switch` | 10 | critical | Kill switch / emergency-stop path missing for the actuator output |
| `timeout_bypass` | 8 | critical | Timeout condition creates an unsafe bypass around verification gates |
| `unsafe_direct_ai` | 5 | critical | Direct AI-to-actuator assignments across varied signal names (motor, heater, valve, relay, laser) |
| `missing_reset` | 10 | critical | Safe gate chain present but no reset signal; design cannot reach a known-safe state |
| `false_negative_trap` | 5 | critical | Unsafe design with obfuscated signal names; should still be caught by the scanner |

### Safe Pattern Categories (should pass to heavy checks)

| Category | Cases | Risk Level | Description |
|---|---|---|---|
| `missing_sensor_ok` | 8 | high | `sensor_ok` not in the core three required DTL gates but recommended for full coverage |
| `missing_default_case` | 8 | high | Missing `default` case in a state machine `case` block; gate chain is otherwise present |
| `safe_dtl_gate` | 10 | low | Standard DTL gate variations (bitwise operators, nested conditionals, parameterized width, all five gates, active-high kill, registered chain) |
| `safe_fsm_dtl_gate` | 5 | low | FSM-based DTL gate with explicit IDLE, VERIFYING, APPROVED, BLOCKED, and FAILSAFE states |
| `false_positive_trap` | 5 | low | Safe design with unusual but valid formatting; should not be falsely blocked |

### Regression Category

| Category | Cases | Risk Level | Description |
|---|---|---|---|
| `regression_safe_baseline` | 8 | varies | Safe baseline modified to unsafe (regression) or safe (no regression). Tests that the system detects when a previously safe design has gates removed. |

---

## The DTL Gate Chain

The core DTL (Design-Through-Lineage) gate chain requires three mandatory
signals to concur before a proposed output can reach a physical actuator:

```
Proposed output
        |
        v
    policy_ok?
        |
        v
    verifier_ok?
        |
        v
    kill_switch clear?
        |
        v
    actuator_enable
```

The scanner checks for the simultaneous presence of all three gates in the
logic that drives the actuator. Additional recommended gates (sensor_ok,
timeout_ok) are noted but not mandatory at the scan tier.

A safe DTL gate in Verilog typically looks like this:

```verilog
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        actuator_enable <= 1'b0;
    end else begin
        actuator_enable <= ai_output
                        && verifier_ok
                        && policy_ok
                        && !kill_switch;
    end
end
```

---

## Example Results

A representative run of the full 121-case benchmark:

```
Total cases:              121
Unsafe blocked:           81
Unsafe accepted:          0
Safe accepted:            40
Safe rejected:            0
False accept rate:        0.0%
False reject rate:        0.0%
No-regression pass rate:  100.0%
Replay match rate:        100.0%

Heavy checks (baseline):  121
Heavy checks (DTL-gated): 40
Synthetic proposals blocked before heavier verification: 81
Baseline cost:            45,980 units
DTL-gated cost:           15,321 units
Est. verification-cost reduction: 3.00x under the synthetic benchmark cost model
Cost per accepted change: 383 units
```

These figures are generated deterministically from the synthetic benchmark
cases and the abstract cost model. They demonstrate that a DTL-gated
workflow filters 81 out of 121 synthetic proposals before they reach
expensive verification stages, yielding an estimated 3.00x
verification-cost reduction under the synthetic benchmark cost model.

---

## Public-Safe Wording Requirements

All output from DTL-ChipBench -- terminal summaries, JSON results, and HTML
reports -- includes the following disclaimer and public wording:

**Disclaimer:**
These are benchmark cost units, not measured silicon performance, GPU
performance, or real EDA cloud cost.

**Model-Free Benchmark:**
These results are not model-connected yet. They measure ChipGate's
deterministic gate behaviour on synthetic RTL and mutation-generated
benchmark cases. They do not guarantee that any AI model is faster, safer or
better at chip design.

**Public wording:**
DTL-ChipBench is a model-free benchmark that tests the ChipGate/DTL
verification gate itself. It uses deterministic synthetic RTL proposals
and mutation-generated cases to measure whether unsafe or regressive
chip-design changes are blocked before heavier verification is needed.

No claims about silicon correctness, tape-out readiness, regulatory
compliance, physical safety, AI model quality, or real-world workflow
speedup should be derived from DTL-ChipBench results. The benchmark
operates on synthetic RTL with known expected outcomes; it does not
substitute for full EDA verification flows.