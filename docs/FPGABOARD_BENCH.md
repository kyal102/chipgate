# FPGABoardBench — FPGA-Oriented Readiness Benchmark

## Overview

FPGABoardBench checks whether safe RTL can move from verification into FPGA-style hardware testing. It runs a 6-stage pipeline for each design:

1. **RTL Safety Precheck** — Existing ChipGate scan rules (CG001–CG014)
2. **Board Profile Check** — Validate against a board profile definition
3. **Pin/Constraint Validation** — Check clock, reset, kill switch, pin assignments
4. **FPGA Synthesis Readiness** — Yosys synthesis targeting the FPGA family
5. **Optional Board Evidence Import** — Import JSON board-test results
6. **Bitstream Readiness** — Synthesis + place-and-route + pack readiness

## Public Disclaimer

> FPGABoardBench does not guarantee ASIC silicon correctness, physical durability, regulatory conformance, medical safety, defence validation or fabrication readiness. It checks whether safe RTL can pass FPGA-oriented preparation, pin mapping, simulation, bitstream-readiness checks and optional board-test evidence.

## Usage

```bash
# Run demo with built-in designs
python -m chipgate fpga --demo

# Run with JSON output
python -m chipgate fpga benchmarks/fpgabench_v0 --json

# Generate HTML report
python -m chipgate fpga benchmarks/fpgabench_v0 --html fpga_report.html

# Use a specific board profile
python -m chipgate fpga --demo --board-profile tinyfpga_style

# Show toolchain status
python -m chipgate fpga --toolchain-status

# Allow unsafe designs to proceed
python -m chipgate fpga --demo --allow-unsafe
```

## Board Profiles

| Profile | Description | FPGA Family | Max IO |
|---------|-------------|-------------|--------|
| `generic_fpga` | Generic FPGA, minimal constraints | ice40 | 16 |
| `ice40_generic` | Generic Lattice iCE40 | ice40 | 32 |
| `tinyfpga_style` | TinyFPGA BX-style small board | ice40 | 16 |
| `arty_style` | Digilent Arty A7-style large board | xilinx | 64 |

See [BOARD_PROFILES.md](BOARD_PROFILES.md) for full profile specifications.

## Pin Constraints

Pin constraints are validated for:

- **Clock** — Design must have a clock input matching the board profile
- **Reset** — Design must have a reset input
- **Kill Switch** — Safety-critical designs must have a kill switch input
- **Actuator Gating** — Actuator enable signals must show gate evidence
- **Duplicate Pins** — No pin location may be assigned to two signals
- **Unassigned Safety Outputs** — Safety-critical outputs must have pin assignments
- **Safe Defaults** — Safety-critical outputs must have explicit safe default values
- **IO Count** — Total design IO must not exceed board maximum

Constraints are loaded from JSON files named `<design_id>.constraints.json` in the same directory as the RTL file.

### Constraint File Format

```json
{
    "clk": "PIN_1",
    "rst_n": "PIN_2",
    "kill_switch": "PIN_3",
    "verifier_ok": "PIN_4",
    "policy_ok": "PIN_5",
    "actuator_enable": "PIN_10",
    "safe_out": "PIN_11"
}
```

## Board Test Evidence

FPGABoardBench can import optional board-test evidence from JSON files named `<design_id>.board_evidence.json`:

```json
{
    "board_profile": "generic_fpga",
    "design_id": "safe_dtl_gate",
    "test_cycles": 10000,
    "unsafe_enable_events": 0,
    "kill_switch_bypasses": 0,
    "reset_glitches": 0,
    "tester": "manual_or_ci",
    "notes": "optional"
}
```

If any `unsafe_enable_events` or `kill_switch_bypasses` are non-zero, the evidence is classified as `BOARD_EVIDENCE_FAIL`.

## Stages

### Stage 1: RTL Safety Precheck

Uses the existing ChipGate scanner with all 14 rules (CG001–CG014). Unsafe designs are blocked from proceeding to synthesis unless `--allow-unsafe` is passed.

### Stage 2: Board Profile Check

Validates the board profile name and loads the profile definition (clock pin, reset pin, max IO, FPGA family, etc.).

### Stage 3: Pin/Constraint Validation

Checks all pin constraint rules listed above. If no constraints file is provided, validation is based on RTL port analysis only (clock, reset, kill switch, safe defaults, IO count).

### Stage 4: FPGA Synthesis Readiness

If Yosys is installed, synthesizes the design targeting the board profile's FPGA family. Captures cell count and wire count from Yosys statistics.

### Stage 5: Board Evidence Import

Looks for and classifies board-test evidence files if present.

### Stage 6: Bitstream Readiness

If Yosys and nextpnr are installed, runs the full synthesis + place-and-route + pack flow. Classifies as BITSTREAM_READY, BITSTREAM_FAIL, or BITSTREAM_SKIPPED_TOOL_MISSING.

## Graceful Degradation

All external tools (yosys, nextpnr, icestorm, verilator, cocotb, openFPGALoader) are optional. Missing tools produce `*_SKIPPED_TOOL_MISSING` statuses. No external tool is required for unit tests — mocks and fixture outputs are used.

## Status Constants

See the source code in `chipgate/statuses.py` for the complete list of FPGABoardBench status constants (FPGA_BENCH_PASS, FPGA_BENCH_FAIL, BOARD_PROFILE_VALID, PIN_CONSTRAINT_PASS, etc.).

## Metrics

| Metric | Description |
|--------|-------------|
| `designs_tested` | Number of designs processed |
| `board_profiles_checked` | Board profile validations performed |
| `pin_constraint_pass_rate` | Fraction of designs passing pin constraints |
| `safety_precheck_pass_rate` | Fraction of designs passing safety precheck |
| `fpga_synth_pass_rate` | Fraction of designs passing FPGA synthesis |
| `place_route_pass_rate` | Fraction of designs passing place-and-route |
| `bitstream_ready_rate` | Fraction of designs classified as bitstream ready |
| `board_evidence_attached_count` | Number of designs with board evidence |
| `unsafe_enable_events_from_board_evidence` | Total unsafe events from board evidence |
| `kill_switch_bypass_count_from_board_evidence` | Total kill switch bypasses from evidence |
| `artifact_hash_count` | Total SHA-256 artifact hashes |
| `evidence_packs_created` | Number of evidence records created |
| `toolchain_coverage` | Fraction of tools found |