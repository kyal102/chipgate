# Open Silicon Limitations

This document describes what ChipGate's open-silicon preparation features do and do not guarantee. These limitations apply to all phases that generate or validate artifacts intended for open silicon submission workflows, including TinyTapeoutPrep (Phase 9), SiliconReadinessBench (Phase 7), and FPGABoardBench (Phase 8).

## What ChipGate Checks

ChipGate performs structural and text-based analysis of RTL source code. Its checks include:

- Module naming and file existence
- Pin mapping validation against target constraints
- Detection of private or proprietary name references
- Detection of unsupported SystemVerilog constructs
- Heuristic detection of potential latch inference
- Documentation completeness (clock, reset, pinout)
- Safety property coverage (gating signals, kill switch, timeout, reset)
- Lightweight structural scan for ungated outputs

## What ChipGate Does NOT Check

ChipGate does not perform and cannot guarantee:

- **Silicon correctness**: No timing analysis, no DRC/LVS, no foundry signoff
- **Physical safety**: No electrical verification, no thermal analysis, no reliability testing
- **Real power consumption**: No dynamic or leakage power measurement
- **Real area**: No gate-level area estimation after synthesis
- **Timing closure**: No STA, no clock tree synthesis, no hold/setup analysis
- **Fabrication readiness**: No GDS generation, no DRC-clean layout
- **Regulatory compliance**: No IEC 61508, no ISO 26262, no DO-254, no medical device certification
- **Real hardware testing**: No board-level verification, no oscilloscope measurements
- **Tiny Tapeout acceptance**: No official CI integration, no GDS build verification

## Graceful Degradation

Several benchmark stages depend on external EDA tools (Verilator, Yosys, SymbiYosys, nextpnr, OpenLane). When these tools are unavailable, the checks gracefully degrade to a SKIPPED status rather than failing. This means:

- A SKIPPED status is neutral, not an endorsement
- A design with all SKIPPED tool checks has not been verified by any EDA tool
- Manual review and separate tool runs are still required

## Evidence Packs

Evidence packs contain SHA-256 hashes of generated artifacts. These provide:

- Reproducibility verification
- Artifact integrity checking
- Audit trail for review processes

They do not provide:

- Fabrication signoff
- Timing closure evidence
- Power or area measurements
- Safety certification

## Honest Claims

You can honestly claim:

- ChipGate generated structurally valid TinyTapeout-compatible artifacts
- The artifacts passed 15 structural readiness checks
- The design implements verification-gated actuator control
- Evidence packs are reproducible with SHA-256 verification
- Safety properties are documented and checkable

You cannot honestly claim:

- The design is ready for fabrication
- The design has been accepted by Tiny Tapeout
- The design is timing-closed or power-characterised
- The design is certified for any safety-critical application
- The design has been tested on real hardware
- The design is suitable for medical, defence, or robotics use