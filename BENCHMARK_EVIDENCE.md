# ChipGate Benchmark Evidence Boundary

This public-lite package does not include the private ChipGate synthesis, timing, or safety-rule engine.

The private JARVI3 ChipGate Phase 31K Docker run was used to validate the evidence pipeline around Yosys and nextpnr. Public claims must keep the toolchain boundary attached:

| Tool | Status in Docker run |
| --- | --- |
| Yosys | Available |
| nextpnr-ice40 | Available |
| OpenSTA | Available after source build (`sta` 3.1.0) |

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

## Claims Blocked

Do not claim:

- DTL beats all chips.
- DTL beats NVIDIA.
- DTL proves real silicon.
- DTL proves ASIC timing.
- DTL is production ready.
- DTL is universally faster.
- DTL is safety certified.

These claims remain blocked because:

- OpenSTA is now installed and detected, but the current benchmark metrics are still nextpnr-ice40 timing evidence.
- ASIC/static timing evidence using an ASIC Liberty/SDC target is still missing.
- The current timing evidence is nextpnr-ice40 FPGA-style timing evidence.
- No real silicon fabrication or physical test evidence exists yet.

Best public wording:

> ChipGate Phase 31K now includes Docker-reproducible Yosys synthesis, OpenSTA availability, and nextpnr-ice40 timing evidence. In this exact public toolchain run, DTL_FASTPATH preserved the configured safety gate while reporting 8 cells, 6 logic cells, 1.596 ns timing and 626.566 MHz. Compared with the classic safe FSM baseline, it used 66.7% fewer cells, 60% fewer logic cells and reported 172.18% higher Fmax. ASIC/OpenSTA timing metrics, real silicon, production and global chip-superiority claims remain blocked until further evidence exists.
