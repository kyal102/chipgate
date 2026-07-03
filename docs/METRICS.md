# DTL-ChipBench Metrics Reference

## Overview

DTL-ChipBench produces a set of metrics that characterize the behaviour of
the ChipGate/DTL verification gate on synthetic RTL proposals. This document
defines every metric, the underlying cost model, and the formulas used to
compute aggregate results.

**Important:** All cost values are expressed in abstract benchmark cost
units. These are not measured silicon performance, GPU performance, or real
EDA cloud cost. The cost model uses fixed per-tier unit costs to provide a
transparent, reproducible, and comparable framework for workflow-level
analysis of the deterministic gate.

**Benchmark scope:** DTL-ChipBench currently tests the verification gate,
not an AI model. The benchmark cases are mutation-generated from templates.
Model-connected testing is a future phase.

---

## Metric Definitions

### Case Counts

| Metric | Type | Description |
|---|---|---|
| `total_cases` | integer | Total number of synthetic benchmark cases executed |
| `unsafe_cases` | integer | Number of cases whose expected gate result is "block" (unsafe patterns) |
| `safe_cases` | integer | Number of cases whose expected gate result is "pass" (safe patterns) |
| `regressions` | integer | Number of cases that include a baseline RTL for regression testing |

### Gate Decision Outcomes

| Metric | Type | Description |
|---|---|---|
| `unsafe_blocked` | integer | Unsafe cases correctly blocked by the DTL scan |
| `unsafe_accepted` | integer | Unsafe cases incorrectly passed by the DTL scan (false accepts) |
| `safe_accepted` | integer | Safe cases correctly passed by the DTL scan to heavy verification |
| `safe_rejected` | integer | Safe cases incorrectly blocked by the DTL scan (false rejects) |

### Rate Metrics

| Metric | Type | Formula | Description |
|---|---|---|---|
| `false_accept_rate` | percent | `(unsafe_accepted / unsafe_cases) * 100` | Percentage of unsafe cases that slipped past the DTL gate. A value of 0.0% means no unsafe design was accepted. This is the most critical safety metric. |
| `false_reject_rate` | percent | `(safe_rejected / safe_cases) * 100` | Percentage of safe cases that were incorrectly blocked. High false-reject rates indicate an overly aggressive scanner that wastes developer time. |
| `no_regression_pass_rate` | percent | `(no_regression_count / regression_cases_with_status) * 100` | Percentage of regression test cases that correctly detected either a regression (when expected) or confirmed no regression (when expected). Computed only over cases where both baseline and proposed RTL were available. |
| `replay_match_rate` | percent | 100.0 if all gate decisions are correct, 0.0 otherwise | Measures deterministic replayability. Because the benchmark uses synthetic RTL with no random or time-dependent components, this is 100.0% unless a code defect causes non-deterministic behavior. |

### Heavy Check Metrics

| Metric | Type | Description |
|---|---|---|
| `heavy_checks_baseline` | integer | Number of cases that would undergo heavy verification (lint, simulation, formal, synthesis) in the ungated baseline workflow. Equals `total_cases` because every case enters the full pipeline unconditionally. |
| `heavy_checks_dtl` | integer | Number of cases that undergo heavy verification in the DTL-gated workflow. Equals `safe_accepted + safe_rejected` because only cases not blocked by the DTL scan proceed. |
| `heavy_checks_avoided` | integer | Difference: `heavy_checks_baseline - heavy_checks_dtl`. Represents the number of synthetic proposals blocked before heavier verification would be required under the cost model. |

### Cost Metrics

| Metric | Type | Description |
|---|---|---|
| `estimated_baseline_cost` | integer | Total estimated cost units for the ungated baseline workflow |
| `estimated_dtl_cost` | integer | Total estimated cost units for the DTL-gated workflow |
| `estimated_speedup_ratio` | float | Ratio: `estimated_baseline_cost / estimated_dtl_cost`. Described as "estimated verification-cost reduction under the synthetic benchmark cost model" -- not a measured real-world speedup. Returns 0.0 if gated cost is zero to avoid division by zero. |
| `cost_per_verified_accepted_change` | float | Ratio: `estimated_dtl_cost / safe_accepted`. Average cost units spent per safe design change that completed the full DTL-gated pipeline. Returns infinity if no safe cases were accepted. |

### Evidence Metrics

| Metric | Type | Description |
|---|---|---|
| `evidence_packs_created` | integer | Number of per-case evidence packs written when the benchmark is run with the `--evidence` flag. Zero when evidence generation is not requested. |

### Regression Metrics (v0.3.0)

| Metric | Type | Description |
|---|---|---|
| `regressions_detected` | integer | Total number of regressions detected across all cases with baselines |
| `regressions_accepted` | integer | Regressions that were not blocked by the gate (critical safety concern) |

### Mode Metrics (v0.3.0)

| Metric | Type | Description |
|---|---|---|
| `benchmark_mode` | string | The mode used: "ungated_baseline", "chipgate_only", or "external_dtl" |
| `adapter_name` | string | Name of the adapter used (empty if built-in synthetic) |
| `proposal_source` | string | Proposal source label (e.g. "synthetic", "external_dtl") |
| `holdout_cases_included` | integer | Number of private holdout cases loaded (0 if no holdout directory) |

---

## Cost Model

The cost model assigns a fixed unit cost to each verification tier. These
units are not monetary values, wall-clock times, or cloud compute charges.
They are abstract weights chosen to reflect the relative computational
burden of each verification step.

### Tier Costs

| Tier | Cost Units | Description |
|---|---|---|
| DTL Scan | 1 | Deterministic RTL structure and safety-gate pattern check. Pattern matching on the AST, no simulation. |
| Lint | 5 | Verilog/SystemVerilog lint via Verilator or equivalent tool. Syntax and style checking. |
| Simulation | 25 | RTL simulation via Verilator, cocotb, or equivalent. Functional correctness testing. |
| Formal Verification | 100 | Formal property checking via SymbiYosys/SBY. Exhaustive state-space exploration. |
| Synthesis | 250 | RTL synthesis via Yosys or equivalent. Gate-level mapping and timing estimation. |

### Baseline Workflow Cost

In the ungated baseline workflow, every case passes through the full
pipeline:

```
baseline_cost = total_cases * (lint + simulation + formal + synthesis)
              = total_cases * (5 + 25 + 100 + 250)
              = total_cases * 380
```

For 121 cases: 121 x 380 = 45,980 units.

### DTL-Gated Workflow Cost

In the DTL-gated workflow, all cases receive a cheap DTL scan first. Only
cases that pass the scan proceed to heavy checks:

```
dtl_gated_cost = (total_cases * dtl_scan)
               + (non_blocked_cases * lint + simulation + formal + synthesis)
               = (total_cases * 1)
               + (non_blocked_cases * 380)
```

For 121 cases with 81 blocked: (121 x 1) + (40 x 380) = 121 + 15,200 =
15,321 units.

### Estimated Verification-Cost Reduction Ratio

The ratio measures how many times cheaper the DTL-gated workflow is
compared to the ungated baseline, under the synthetic benchmark cost model:

```
estimated_speedup_ratio = estimated_baseline_cost / estimated_dtl_cost
```

For the example above: 45,980 / 15,321 = 3.00x.

A ratio of 3.00x means the DTL-gated workflow costs one-third of the
ungated baseline under the synthetic benchmark cost model. This is an
estimated verification-cost reduction, not a measured real-world speedup.

### Cost Per Verified Accepted Change

```
cost_per_verified_accepted_change = estimated_dtl_cost / safe_accepted
```

For the example above: 15,321 / 40 = 383 units per safe design change.

This metric represents the average verification investment per design
change that successfully passed all gates and completed heavy verification.

---

## Key Definitions

### False Accept

A false accept occurs when an unsafe RTL pattern (a case with expected gate
result "block") is incorrectly passed by the DTL scan. The unsafe design
escapes early filtering and proceeds to heavy verification, where it may or
may not be caught by downstream checks.

The false accept rate is the proportion of unsafe cases that were incorrectly
passed:

```
false_accept_rate = (unsafe_accepted / unsafe_cases) * 100
```

A false accept rate of 0.0% is the target. Any non-zero value indicates a
gap in the DTL scanner's pattern coverage.

### False Reject

A false reject occurs when a safe RTL pattern (a case with expected gate
result "pass") is incorrectly blocked by the DTL scan. The safe design is
prevented from reaching heavy verification, resulting in wasted developer
effort to diagnose and override the block.

The false reject rate is the proportion of safe cases that were incorrectly
blocked:

```
false_reject_rate = (safe_rejected / safe_cases) * 100
```

A low false reject rate (below 5.0%) indicates the scanner is precise and
does not over-block safe designs.

### No-Regression Pass Rate

This rate measures the correctness of the regression detection subsystem.
It is computed only over cases that include a baseline RTL for comparison:

```
no_regression_pass_rate = (correct_regression_results / total_regression_cases) * 100
```

A correct result is one where:
- A regression was expected and `REGRESSION_DETECTED` was the outcome, or
- No regression was expected and `NO_REGRESSION_PASS` was the outcome.

A pass rate of 100.0% indicates the regression checker correctly identifies
both regressions (gate removal) and non-regressions (safe modifications or
improvements).

---

## Evidence Pack Integrity

When the benchmark is run with `--evidence`, each case produces an evidence
pack containing:

| Field | Description |
|---|---|
| `case_id` | Unique identifier for the benchmark case |
| `category` | Benchmark category the case belongs to |
| `risk_level` | Assigned risk level (critical, high, medium, low, info) |
| `input_hash` | SHA-256 hash of the RTL source provided to the scanner |
| `gate_result` | Actual gate decision ("block" or "pass") |
| `expected_gate_result` | Known correct gate decision for this case |
| `gate_correct` | Boolean: whether the actual decision matches expected |
| `statuses` | List of status flags produced by the scanner |
| `heavy_check_decision` | Whether heavy checks were "avoided" or "required" |
| `regression_status` | Regression detection result, if applicable |
| `certificate_hash` | Hash from the scan certificate |
| `replay_command` | CLI command to replay this specific scan |
| `findings_count` | Number of findings produced by the scanner |
| `public_wording` | Standard disclaimer text |

Evidence packs are written as sorted JSON files to ensure deterministic
serialization. The `input_hash` and `certificate_hash` fields enable
independent verification that the inputs and outputs have not been tampered
with.

---

## Disclaimer

All metrics in this document are based on the DTL-ChipBench synthetic
benchmark. These are benchmark cost units, not measured silicon performance,
GPU performance, or real EDA cloud cost.

These results are not model-connected yet. They measure ChipGate's
deterministic gate behaviour on synthetic RTL and mutation-generated
benchmark cases. They do not guarantee that any AI model is faster, safer or
better at chip design.

No claims about chip correctness, silicon readiness, physical safety,
regulatory conformance, AI model quality, or real-world workflow speedup
should be derived from these metrics.