# SiliconReadinessBench Limitations

This document describes what SiliconReadinessBench does NOT do and what its results do NOT prove.

## Core Limitation

> SiliconReadinessBench checks whether safe RTL candidates survive synthesis, formal checks, FPGA flow and ASIC-flow readiness. It does not guarantee silicon correctness, physical safety, real power, real timing signoff, physical durability, regulatory conformance or fabrication readiness. It checks whether RTL passes reproducible open-source tool-flow readiness stages.

## What These Results Are

- Tool-flow readiness checks
- Checks whether RTL was accepted by a specific version of a specific tool in a specific configuration
- Useful for catching integration issues early
- Reproducible given the same tool versions and configurations

## What These Results Are NOT

- Silicon correctness proof
- Physical safety proof
- Real power measurement
- Real timing signoff
- Physical durability assessment
- Regulatory compliance certification
- Fabrication readiness signoff
- Tapeout readiness

## Stage-Specific Limitations

### Verilator Lint (Stage 2)
- Verilator is a simulation-oriented linter, not a complete Lint tool
- Not all synthesis warnings are detected
- Verilator version differences may change warning counts
- Passing Verilator lint does not guarantee the design is bug-free

### Yosys Synthesis (Stage 3)
- Cell and wire counts depend on the Yosys version, target architecture, and synthesis settings
- The default synthesis script uses generic settings, not foundry-specific cells
- Cell counts are not comparable across different tools or configurations
- Area estimates from generic synthesis are not real area measurements

### Formal Verification (Stage 4)
- Only simple BMC (bounded model checking) properties are checked
- BMC depth is limited (default: 20 cycles)
- Properties are generic DTL-style safety properties, not design-specific
- Passing formal checks does not guarantee the design is fully verified
- Missing properties may leave real bugs undetected

### FPGA Readiness (Stage 5)
- Only ice40 family is tested by default
- No actual FPGA board programming or testing
- Timing constraints are not applied
- Resource utilization is not analyzed
- Passing FPGA flow does not guarantee the design works on real hardware

### ASIC Flow Readiness (Stage 6)
- Only checks whether RTL is parseable by the tool
- No floorplanning, placement, routing, or timing analysis
- No DRC or LVS checks
- Does NOT claim tapeout readiness
- Actual ASIC results require full PDK-specific flows

## Environmental Factors

- Results depend on tool versions installed on the system
- Different tool versions may produce different results
- No tool version pinning or lock file mechanism
- CI environments and local environments may produce different results

## What Is Required for Real Silicon Results

- Foundry-qualified PDK
- Complete timing analysis (STA)
- Power analysis (dynamic and leakage)
- DRC and LVS
- Physical verification
- Device qualification testing
- Regulatory compliance review
- Professional tapeout signoff

SiliconReadinessBench provides none of these. It is a pre-silicon readiness filter, not a replacement for professional EDA flows.