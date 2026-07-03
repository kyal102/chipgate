# DTL Verified Design Passport

## Overview

The DTL Verified Design Passport creates a portable verification record for AI-generated or user-submitted design artifacts. It records what was designed, the artifact type, risk level, gates run, pass/fail results, evidence, replay commands, and export/build/simulation decisions.

**DTL Verified Design Passport does not prove that a design is safe, correct, certified, fabrication-ready, commercially validated or production-ready.** It creates a structured, replayable verification record for the configured checks that were actually run.

## Pipeline

```
artifact → classification → risk assignment → gate selection → gate execution →
evidence collection → replay command → passport assembly → badge determination →
export decision → handoff pack
```

## Artifact Types

| Type | Description |
|------|-------------|
| document | Markdown or text documents |
| claim_set | Claim sets with verify/evidence keywords |
| code | Python, JS, C code |
| rtl | Verilog/SystemVerilog RTL |
| riscv_trace | RISC-V trace files |
| soc_design | SoC-level designs |
| asic_review_pack | ASIC review packs |
| robotics_control_demo | Robotics control demonstrations |
| supply_chain_policy_demo | Supply chain policy demonstrations |
| physics_equation | Physics equations |
| chemistry_formula | Chemistry formulas |
| unknown | Unrecognized artifacts |

## Risk Levels

- **LOW**: documents, claim sets
- **MEDIUM**: code, supply chain policies, physics, chemistry
- **HIGH**: RTL, RISC-V traces, SoC designs, ASIC review packs
- **SAFETY_CRITICAL**: robotics control demos
- **UNKNOWN**: unrecognized artifacts

## Gate IDs

chipgate, evidencepack, replaygate, claimgate, claimlint, unitgate, elementgate, soc_safety, riscv_demo, asic_bench, dtl_accel

## CLI Usage

```bash
python -m chipgate passport --demo
python -m chipgate passport --demo --json
python -m chipgate passport --demo --html report.html
python -m chipgate passport --artifact design.v
python -m chipgate passport --verify-passport passport.json
python -m chipgate passport --export-badge /output/dir --artifact passport.json
python -m chipgate passport --replay --artifact design.v
```

## Modules

- `passport_schema.py` — Schema definitions, constants, dataclasses
- `passport_artifacts.py` — Artifact intake, validation, hashing, leak detection
- `passport_policy.py` — Risk assignment, gate selection, export decisions
- `passport_builder.py` — Full passport build pipeline
- `passport_badges.py` — Badge determination and SVG generation
- `passport_manifest.py` — Hashing, manifest creation, verification
- `passport_replay.py` — Replay command generation and drift detection
- `passport_report.py` — JSON and HTML report generation
- `passport_export.py` — Handoff pack generation
- `passport_examples.py` — Demo fixtures
- `design_passport.py` — Main orchestrator
