# FPGABoardBench — Limitations and Disclaimers

## Critical Limitations

FPGABoardBench is a static analysis and tool-flow readiness checker. It does NOT provide:

- **ASIC silicon correctness** — FPGA synthesis results do not predict ASIC behaviour
- **Physical durability** — No thermal, electromigration, or aging analysis
- **Regulatory compliance** — No IEC 61508, ISO 26262, or DO-254 certification
- **Medical safety** — No medical device validation (IEC 60601, FDA)
- **Defence validation** — No MIL-STD or DO-254 assurance levels
- **Fabrication readiness** — No tapeout, GDSII, or foundry signoff
- **Hardware deployment readiness** — Passing tool-flow stages does not guarantee correct board operation
- **Timing closure** — No real static timing analysis (STA)
- **Power analysis** — No real dynamic or leakage power measurement
- **Signal integrity** — No IBIS, SI simulation, or EMI analysis

## What FPGABoardBench Actually Checks

FPGABoardBench checks whether:

1. RTL passes ChipGate safety rules (CG001–CG014)
2. Pin assignments match the board profile constraints
3. Safety-critical signals have proper gating evidence
4. RTL can be accepted by Yosys for FPGA-family synthesis
5. RTL can pass nextpnr place-and-route (if tools available)
6. A bitstream can be generated through icepack (if tools available)
7. Optional board-test evidence is consistent with safety expectations

## Tool Limitations

- Results depend on the specific version and configuration of each tool
- A design passing Yosys synthesis for ice40 may fail for a different FPGA family
- Cell count and wire count are tool-specific and not comparable across tools
- Place-and-route success depends on device size and package selection
- Bitstream readiness does not guarantee the design functions correctly on hardware

## Board Profile Limitations

- Board profiles are definitions only — no hardware connection is made
- Pin locations are placeholders — actual pin assignments depend on the physical board
- Maximum IO counts are approximate — verify against actual board documentation
- Forbidden pin lists are advisory — they do not prevent actual hardware connections

## Evidence Record Limitations

- Evidence records use SHA-256 hashes for integrity but do not provide cryptographic signing
- Replay commands reference the CLI interface — they require the same tool versions for exact reproducibility
- Board-test evidence is imported as-is — no independent verification of the test results is performed
- Certificate hashes cover the evidence record structure, not the RTL correctness

## Appropriate Uses

FPGABoardBench is appropriate for:

- Early-stage RTL readiness checking before FPGA prototyping
- Automated CI/CD pipeline gates for RTL safety
- Educational demonstrations of safety-gated RTL patterns
- Benchmarking the ChipGate safety scanner against FPGA-oriented designs

## Inappropriate Uses

FPGABoardBench is NOT appropriate for:

- Production signoff for any safety-critical system
- Comparison against commercial EDA tools or silicon vendors
- Claims of "verified" or "validated" hardware
- Regulatory submissions or compliance evidence
- Performance or timing guarantees