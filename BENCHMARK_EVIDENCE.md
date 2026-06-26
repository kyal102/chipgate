# ChipGate Benchmark Evidence Boundary

This public-lite package does not include the private ChipGate synthesis, timing, or safety-rule engine.

The private JARVI3 ChipGate Phase 31K Docker run was used to validate the evidence pipeline around Yosys and nextpnr. Public claims must keep the toolchain boundary attached:

| Tool | Status in Docker run |
| --- | --- |
| Yosys | Available |
| nextpnr-ice40 | Available |
| OpenSTA | Not available in the Ubuntu 24.04 apt image |

Latest private Phase 31K summary:

| Design | Cell count | FPGA area | Critical path | Fmax |
| --- | ---: | ---: | ---: | ---: |
| CLASSIC_SAFE_FSM | 24 | 15 LC | 4.344 ns | 230.203 MHz |
| CLASSIC_REDUNDANT | 16 | 11 LC | 1.547 ns | 646.412 MHz |
| DTL_FASTPATH | 8 | 6 LC | 1.596 ns | 626.566 MHz |

Comparison notes:

- DTL_FASTPATH used fewer synthesized cells and fewer iCE40 logic cells than both classic baselines in this scoped benchmark.
- DTL_FASTPATH was faster than CLASSIC_SAFE_FSM in this scoped nextpnr timing run.
- DTL_FASTPATH was slightly slower than CLASSIC_REDUNDANT in this scoped nextpnr timing run.
- No public claim should imply ASIC timing closure, silicon correctness, fabrication readiness, regulatory approval, or universal chip performance.

