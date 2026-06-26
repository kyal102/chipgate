# JARVI3 Chip DesignGuard Lite - Limitations

JARVI3 Chip DesignGuard does not prove silicon correctness, ASIC fabrication readiness, timing closure, physical safety, medical safety, defence suitability, robotics safety, production readiness or regulatory compliance. It routes artifacts through configured public checks and records evidence, replay and passport status.

## No Private JARVI3 Logic

This public-lite package does not contain, import, or reference any private JARVI3 internal logic. The actual gate execution, rule evaluation, and decision-making logic are part of the private system.

## No Private DTL Internals

This package does not contain any Digital Twin Laboratory (DTL) internals, proprietary models, or confidential design data. All examples use minimal synthetic Verilog for demonstration purposes only.

## External References Context Only

References to ChipGate, SoCGate, ASICBench, RISC-V checks, and robotics checks in this package are provided for context and schema illustration only. This package does not run or invoke those systems.

## No Real Silicon Evidence

The evidence hashes, passport hashes, and replay commands shown in this package are synthetic demonstrations. They do not represent real silicon validation, tapeout evidence, or production-verified hardware results.