# MutationBench Limitations

## Core Limitation Statement

Passing MutationBench does not prove the design is secure, physically safe, fabricated, timing-closed or fully verified. It only means the configured mutation classes were generated and checked, and that detected/escaped results were recorded.

## What MutationBench Tests

MutationBench generates known-unsafe RTL variants using 20 mutation categories and checks whether ChipGate's structural scanner detects the unsafe pattern. This is a form of mutation testing applied to the verification tool itself, not to the hardware design.

## What MutationBench Does NOT Test

1. **Functional correctness** — MutationBench does not verify that the original design functions correctly. It only checks structural patterns.

2. **Timing closure** — No static timing analysis is performed. Mutated designs are not synthesized or timed.

3. **Physical safety** — No DRC, LVS, or physical verification is performed on mutated designs.

4. **Fabrication readiness** — MutationBench does not check GDS, power analysis, or foundry-specific requirements.

5. **Real-world security** — MutationBench tests known mutation classes. It does not model real adversaries or novel attack vectors.

6. **Exhaustive mutation** — The 20 mutation categories cover common bypass patterns but do not cover all possible unsafe RTL transformations.

7. **Semantic equivalence** — MutationBench checks whether ChipGate detects the mutation, not whether the mutation preserves or changes the design's functional behavior.

8. **Multi-module designs** — Current mutation generators work on single-module designs. Multi-module interactions may not be fully tested.

9. **Tool-specific behaviors** — MutationBench does not test how mutated designs behave under specific synthesis, simulation, or formal tools.

10. **State space coverage** — For FSM mutations, only structural transitions are checked. Exhaustive state-space exploration is not performed.

## Escaped Mutations

An escaped mutation means ChipGate's current rule set did not detect the unsafe pattern. This indicates a potential rule gap that should be investigated and potentially hardened. However, an escape does not necessarily mean the design is unsafe in practice — it means the structural scanner missed the pattern.

## Relationship to Other Benchmarks

- MutationBench complements but does not replace FormalGate-Lite, LongevityBench, or physical verification.
- A design that passes MutationBench but fails formal verification has real safety issues that MutationBench cannot detect.
- A design that passes MutationBench but fails physical DRC/LVS has manufacturing issues that MutationBench cannot detect.

## No Claims About

- Silicon correctness
- Fabrication readiness
- Timing closure
- Real power consumption or area
- Physical safety certification
- Real-world security assessment
- Regulatory compliance
- NVIDIA comparison or benchmarking