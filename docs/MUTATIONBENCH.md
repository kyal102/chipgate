# MutationBench

## Overview

MutationBench stress-tests ChipGate by attacking safe RTL with thousands of unsafe mutations and bypass attempts. It measures whether ChipGate detects, blocks, records and replays those failures before RTL progresses toward synthesis, FPGA, TinyTapeout or OpenLane/OpenROAD stages.

MutationBench does not prove full chip correctness, physical safety, fabrication readiness, timing closure or real-world security. It tests whether known classes of unsafe RTL mutations are detected, blocked, recorded and replayed.

## What MutationBench Does

1. **Loads seed designs** — Safe, properly-gated DTL gate Verilog files that pass ChipGate scanning.
2. **Generates mutations** — Applies 20 mutation categories to create thousands of unsafe RTL variants.
3. **Scans each mutation** — Runs ChipGate's structural scanner on every mutated design.
4. **Classifies results** — Each mutation is classified as DETECTED or ESCAPED.
5. **Scores the run** — Computes detection rates per category, with strict thresholds for critical safety mutations.
6. **Creates evidence** — Generates JSON evidence packs with SHA-256 audit trails for every mutation.
7. **Generates reports** — Produces static HTML and JSON reports.

## Mutation Categories

MutationBench defines 20 mutation categories organized into four groups:

### Unsafe Bypass (Critical — must be 100% detected)
| Category | Description |
|----------|-------------|
| `remove_verifier_gate` | Remove `verifier_ok` from gating |
| `remove_policy_gate` | Remove `policy_ok` from gating |
| `remove_sensor_gate` | Remove `sensor_ok` from gating |
| `direct_actuator_bypass` | Replace gated output with `assign actuator_enable = ai_output` |
| `or_bypass` | Change safe AND chain to unsafe OR chain |
| `failsafe_escape` | Allow FSM to jump from BLOCKED to APPROVED |
| `blocked_escape` | Allow BLOCKED to transition directly to APPROVED |
| `unsafe_pin_exposure` | Expose actuator without gate in wrapper |

### Safety (Critical — must be 100% detected)
| Category | Description |
|----------|-------------|
| `invert_kill_switch` | Change `!kill_switch` to `kill_switch` |
| `remove_timeout_block` | Remove `!timeout` from blocking condition |
| `remove_reset_block` | Remove `!reset` from blocking condition |
| `glitchy_reset` | Allow actuator output during reset transition |

### Structural (High — must be detected)
| Category | Description |
|----------|-------------|
| `stale_verifier` | Bypass with stale always-high verifier signal |
| `shadow_signal` | Create alias signal that routes around gate |
| `obfuscated_expression` | Hide unsafe logic in nested ternary |
| `multiline_bypass` | Split unsafe assignment across multiple lines |
| `duplicate_assignment` | Create conflicting actuator assignments |
| `unsafe_default_state` | Set default FSM state to APPROVED |
| `missing_safety_output` | Remove blocked/failsafe output signal |

### Hygiene (Critical — must be 100% detected)
| Category | Description |
|----------|-------------|
| `private_leak` | Inject forbidden private names, confirm hygiene scanner catches them |

## Scoring

A run passes only if all of the following are true:

- `mutation_detection_rate >= 95%` (configurable threshold)
- `unsafe_bypass_detection_rate = 100%`
- `kill_switch_mutation_detection_rate = 100%`
- `timeout_mutation_detection_rate = 100%`
- `reset_mutation_detection_rate = 100%`
- `replay_match_rate = 100%`

If any critical category has an escaped mutation, the run status is `MUTATIONBENCH_PASS_WITH_REVIEW` and the escaped mutations are listed for rule hardening.

## How to Run

### Demo
```bash
python -m chipgate mutation --demo
```

### Generate mutations only
```bash
python -m chipgate mutation --generate 1000
python -m chipgate mutation --seed safe_dtl_gate.v --generate 1000
```

### Full run with JSON output
```bash
python -m chipgate mutation benchmarks/mutationbench_v0 --json
```

### HTML report
```bash
python -m chipgate mutation benchmarks/mutationbench_v0 --html mutation_report.html
```

### List mutators
```bash
python -m chipgate mutation --list-mutators
```

## Connections to Other Benchmarks

- **ChipGate** — MutationBench uses ChipGate's scanner as the detection engine.
- **FormalGate-Lite** — Escaped mutations that reach formal verification can be cross-checked with FormalGate-Lite properties.
- **LongevityBench** — Mutations that pass structural checks can be further tested for reliability regressions.
- **TinyTapeoutPrep** — MutationBench ensures unsafe RTL cannot progress into TinyTapeout submission flow.
- **OpenLanePhysicalBench** — MutationBench acts as a verification firewall before RTL enters OpenLane/OpenROAD physical flow.

## What MutationBench Does NOT Prove

Passing MutationBench does not prove the design is secure, physically safe, fabricated, timing-closed or fully verified. It only means the configured mutation classes were generated and checked, and that detected/escaped results were recorded.

See [MUTATION_LIMITATIONS.md](MUTATION_LIMITATIONS.md) for the full limitation statement.