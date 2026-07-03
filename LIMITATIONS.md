# ChipGate Lite — Limitations

## What the checker actually does

ChipGate Lite (`chipgate/rtl_check.py`) performs **lint-level structural
analysis of Verilog source text**. It parses modules, ports, always blocks,
continuous assigns, and instantiations with a line/token-based scanner and
applies a fixed, documented rule set. It is fully deterministic: identical
input yields an identical report.

## What it does not do

- It is **not** a synthesizer, simulator, formal equivalence checker, linter
  with full elaboration (no parameter evaluation, no generate expansion, no
  hierarchy resolution across files), or a timing/power tool.
- A `CHIPGATE_PASS` does **not** prove functional correctness, timing
  closure, ASIC fabrication readiness, physical safety, medical safety,
  defence suitability, robotics safety, production readiness, or regulatory
  compliance.
- The `IF_NO_ELSE` and instantiation-detection rules are heuristics and can
  produce false positives/negatives on unusual coding styles; when a module
  contains instantiations, the `UNDRIVEN_OUTPUT` check is skipped because
  port connections are not traced.
- SystemVerilog-specific constructs (`always_ff`, `always_comb`, interfaces,
  packages) are not specially handled; `always_comb`/`always_ff` are treated
  as plain identifiers and their bodies are not analyzed.

Use a real EDA flow (synthesis lint, simulation, formal tools) before
trusting any RTL for hardware. ChipGate Lite is a fast first gate, not the
last one.

## Relationship to the private JARVI3 system

The DesignGuard schema demo (`python -m chipgate --schema-demo`) documents
the JSON request/response format of the private JARVI3 Chip DesignGuard
service. That demo contains no checking logic, no private JARVI3 code, and
no DTL internals. References to SoCGate, ASICBench, RISC-V, and robotics
checks are context/schema illustration only. Evidence hashes and passport
hashes in the demo files are synthetic and represent no real silicon
validation or tapeout evidence.
