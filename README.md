<p align="center"><img src="assets/chipgate_bannor.png" alt="ChipGate banner" width="100%"></p>

# ChipGate

![python](https://img.shields.io/badge/python-3.9%2B-blue) ![tests](https://img.shields.io/badge/tests-806%20passing-brightgreen) ![license](https://img.shields.io/badge/license-MIT-green)

**ChipGate catches unsafe RTL before it becomes silicon.**

ChipGate-lite is a public hardware/RTL verification tool that checks Verilog and SystemVerilog designs for basic safety, lint, simulation, formal-check readiness, and verification-gated output patterns.

## 60-second demo

```bash
git clone https://github.com/kyal102/chipgate
cd chipgate
python -m chipgate scan examples/unsafe_actuator.v
```

Real output:

```text
ChipGate Scan: examples/unsafe_actuator.v
Module: unsafe_actuator

  [FAIL] RTL_SCAN_FAIL
  [FAIL] UNGATED_OUTPUT
  [FAIL] ASSERTION_MISSING
  [INFO] FORMAL_NOT_READY
  [INFO] NEEDS_HUMAN_REVIEW

Findings:
  [CRITICAL] CG001: Missing reset signal — no 'rst' or 'reset' found in sensitivity list or always block
  [CRITICAL] CG006: Hardcoded bypass — 'actuator_enable' directly assigned from 'ai_output' (line 17)
  [CRITICAL] CG007: Actuator 'actuator_enable' not gated by verifier_ok (line 17)
  [CRITICAL] CG008: Actuator 'actuator_enable' not gated by policy_ok (line 17)
  [CRITICAL] CG009: Kill switch / emergency stop path missing for actuator output(s)
  [MEDIUM]   CG010: No assertions found in the design
  [MEDIUM]   CG011: No testbench companion file detected for 'unsafe_actuator'
```

The same scan on `examples/safe_dtl_gate.v` (a verifier-gated design) reports
`RTL_SCAN_PASS` / `SAFETY_GATE_PRESENT`, flagging only its missing assertions.
The test suite (`python -m pytest tests -q`) runs 806 tests.

> **ChipGate checks RTL structure and verification-gated safety patterns. It does not guarantee hardware correctness, silicon readiness, physical safety, regulatory conformance or experimental validity.**

## What It Does

ChipGate scans Verilog/SystemVerilog files and detects:

- Missing reset signals
- Missing default cases in state machines
- Possible latch inference
- Undriven outputs
- Unused inputs
- Hardcoded bypass paths
- Actuator outputs not gated by `verifier_ok`
- Missing `kill_switch` / emergency stop paths
- Missing assertions
- Missing testbenches
- Unsafe bypass paths

### DTL-Specific Checks

Any safety-critical output must be gated by `verifier_ok` / `policy_ok` / `kill_switch` logic before reaching physical actuation.

## Quick Start

```bash
pip install -r requirements.txt

# Run the demo
python -m chipgate --demo

# Scan an unsafe design
python -m chipgate scan examples/unsafe_actuator.v

# Scan a safe gated design
python -m chipgate scan examples/safe_dtl_gate.v

# JSON output
python -m chipgate scan examples/safe_dtl_gate.v --json

# List all rules
python -m chipgate --list-rules

# Version
python -m chipgate --version
```

## Statuses

| Status | Meaning |
|--------|---------|
| `RTL_SCAN_PASS` | All internal checks passed |
| `RTL_SCAN_FAIL` | One or more checks failed |
| `RTL_LINT_PASS` | External lint passed (Verilator) |
| `RTL_LINT_FAIL` | External lint failed |
| `SIMULATION_PASS` | Simulation tests passed |
| `SIMULATION_FAIL` | Simulation tests failed |
| `FORMAL_READY` | Design is ready for formal verification |
| `FORMAL_NOT_READY` | Design needs changes before formal verification |
| `ASSERTION_MISSING` | No assertions found in the design |
| `UNSAFE_BYPASS_PATH` | Unsafe signal bypass detected |
| `UNGATED_OUTPUT` | Safety output not gated by verification signals |
| `SAFETY_GATE_PRESENT` | Proper verification gating detected |
| `NEEDS_HUMAN_REVIEW` | Requires human review |
| `EVIDENCE_PACK_CREATED` | Evidence pack generated successfully |

## Project Structure

```
chipgate/
├── chipgate/                  # Python package
│   ├── adapters/              # Adapter framework (v0.3.0)
│   │   ├── base.py            # Abstract adapter interface
│   │   ├── synthetic_adapter.py  # Built-in synthetic proposals
│   │   ├── jsonl_adapter.py   # External JSONL proposal loader
│   │   └── external_dtl_adapter.example.py  # Template
│   ├── __init__.py
│   ├── __main__.py            # CLI entry point
│   ├── scanner.py             # RTL scanner
│   ├── rules.py               # Safety pattern rules
│   ├── lint.py                # Verilog lint runner (Verilator)
│   ├── simulation.py          # Simulation runner
│   ├── formal.py              # Formal assertion checker
│   ├── safety.py              # Safety-pattern checker
│   ├── evidence.py            # Evidence-pack output
│   ├── replay.py              # Replay command output
│   ├── statuses.py            # Status constants
│   ├── dtl_gate.py            # Demo DTL hardware gate module
│   ├── bench.py               # Benchmark runner (3 modes)
│   ├── bench_cases.py         # 121 synthetic RTL benchmark cases
│   ├── bench_report.py        # HTML report + comparison report
│   ├── cost_model.py          # Verification cost model (mode-aware)
│   ├── noregression.py        # No-regression checker
│   ├── toolchain.py           # Tool detection and version checking
│   ├── verilator_flow.py      # Verilator lint wrapper (Stage 2)
│   ├── yosys_flow.py          # Yosys synthesis wrapper (Stage 3)
│   ├── formal_flow.py         # SymbiYosys formal check wrapper (Stage 4)
│   ├── fpga_flow.py           # FPGA readiness flow wrapper (Stage 5)
│   ├── openlane_flow.py       # ASIC flow readiness wrapper (Stage 6)
│   ├── siliconbench.py        # SiliconReadinessBench runner
│   ├── silicon_artifacts.py   # Artifact hashing and evidence
│   ├── silicon_report.py      # HTML report generation
│   ├── fpgabench.py           # FPGABoardBench runner (Phase 8)
│   ├── board_profiles.py      # Board profile definitions
│   ├── pin_constraints.py     # Pin constraint validation
│   ├── fpga_board.py          # FPGA synthesis wrapper
│   ├── bitstream_readiness.py # Bitstream readiness checks
│   ├── tt_pinout.py           # TinyTapeout pinout mapping (Phase 9)
   ├── openlane_physical.py    # OpenLanePhysicalBench orchestrator (Phase 10)
   ├── openroad_reports.py     # Unified report parsing (Phase 10)
   ├── drc_lvs_parser.py       # DRC/LVS report parser (Phase 10)
   ├── timing_report_parser.py # Timing/area report parser (Phase 10)
   ├── gds_artifacts.py        # GDS artifact hashing (Phase 10)
   ├── physical_score.py       # Physical flow metrics (Phase 10)
   └── physical_report.py      # HTML report generator (Phase 10)
│   ├── tt_wrapper.py          # TinyTapeout wrapper generation
│   ├── tt_docs.py             # TT doc/artifact generation
│   ├── tt_submission_check.py # 15 submission readiness checks
│   ├── tt_report.py           # TT HTML report generation
│   └── tinytapeout_prep.py    # TinyTapeoutPrep orchestrator
│   ├── mutators.py              # Mutation generators (Phase 13)
│   ├── mutationbench.py         # MutationBench orchestrator (Phase 13)
│   ├── mutation_catalog.py      # Mutation category metadata (Phase 13)
│   ├── mutation_runner.py       # Mutation scan runner (Phase 13)
│   ├── mutation_score.py        # Mutation scoring (Phase 13)
│   ├── mutation_report.py       # Mutation HTML/JSON reports (Phase 13)
│   └── mutation_artifacts.py    # Mutation evidence packs (Phase 13)
├── tests/                     # Test suite
├── examples/                  # Example Verilog files + demo JSONL
├── docs/
│   ├── EXAMPLES.md
│   ├── SCHEMA.md
│   ├── LIMITATIONS.md
│   ├── CHIPBENCH.md
│   ├── METRICS.md
│   ├── ADAPTERS.md            # Adapter framework docs
│   ├── HOLDOUT.md             # Private holdout docs
│   ├── DTL_CONNECTED_TESTING.md  # Future model-connected roadmap
│   ├── SILICON_READINESS.md   # SiliconReadinessBench docs
│   ├── TOOLCHAIN.md           # Toolchain setup docs
│   ├── SILICON_LIMITATIONS.md # SiliconReadinessBench limitations
│   ├── FPGABOARD_BENCH.md     # FPGABoardBench docs
│   ├── BOARD_PROFILES.md      # Board profile specs
│   ├── FPGA_LIMITATIONS.md    # FPGABoardBench limitations
│   ├── TINYTAPEOUT_PREP.md    # TinyTapeoutPrep docs
│   ├── TINY_DTL_GATE.md       # Tiny DTL gate explanation
│   └── OPEN_SILICON_LIMITATIONS.md # Open-silicon limitations
│   ├── MUTATIONBENCH.md        # MutationBench docs (Phase 13)
│   ├── MUTATION_CATALOG.md     # Mutation catalog (Phase 13)
│   └── MUTATION_LIMITATIONS.md # Mutation limitations (Phase 13)
├── .github/workflows/ci.yml   # CI pipeline
├── README.md
├── LICENSE
└── requirements.txt
```

## Example: Unsafe Design

```verilog
// unsafe_actuator.v
module unsafe_actuator (
    input  clk,
    input  ai_output,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output;
    end
endmodule
```

**ChipGate output:** `UNGATED_OUTPUT` — `actuator_enable` is directly driven by `ai_output` without verification gating.

## Example: Safe Gated Design

```verilog
// safe_dtl_gate.v
module safe_dtl_gate (
    input  clk,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule
```

**ChipGate output:** `SAFETY_GATE_PRESENT` — proper gating detected.

## DTL-ChipBench (Model-Free DTL Gate Benchmark)

DTL-ChipBench is a **model-free benchmark** that tests the ChipGate/DTL
verification gate itself. It uses deterministic synthetic RTL proposals and
mutation-generated cases to measure whether unsafe or regressive chip-design
changes are blocked before heavier verification is needed.

**What you can honestly claim:**

- ChipGate blocks unsafe RTL patterns.
- ChipGate preserves known-safe gated patterns.
- DTL-ChipBench estimates verification workload reduction under a transparent cost model.
- Replay results are stable.
- Evidence packs are reproducible.

**What DTL-ChipBench does not claim (yet):**

- Any AI model is faster, safer, or better at chip design.
- Real-world chip speedup or silicon safety proven.
- Model-connected benchmarking (this is a future phase).

```bash
# Quick demo (12 representative cases)
python -m chipgate bench --demo

# Full benchmark (121 cases)
python -m chipgate bench

# Full benchmark with HTML report
python -m chipgate bench --html report.html

# JSON output
python -m chipgate bench --json

# Mode-specific runs (v0.3.0)
python -m chipgate bench --mode ungated_baseline --json
python -m chipgate bench --mode chipgate_only --json
python -m chipgate bench --mode external_dtl --adapter proposals.jsonl --json

# Multi-mode comparison (v0.3.0)
python -m chipgate bench --compare-modes --html chipbench_compare.html
```

See [docs/CHIPBENCH.md](docs/CHIPBENCH.md) for full documentation.
See [docs/ADAPTERS.md](docs/ADAPTERS.md) for the adapter framework.
See [docs/DTL_CONNECTED_TESTING.md](docs/DTL_CONNECTED_TESTING.md) for the model-connected roadmap.

## Optional Tool Integration

- **Verilator** — Verilog/SystemVerilog lint (SiliconReadinessBench Stage 2)
- **Yosys** — Synthesis (SiliconReadinessBench Stage 3, FPGA Stage 5)
- **SymbiYosys/SBY** — Formal verification (SiliconReadinessBench Stage 4)
- **nextpnr** — FPGA place-and-route (SiliconReadinessBench Stage 5)
- **OpenLane/OpenROAD** — ASIC flow readiness (SiliconReadinessBench Stage 6)
- **cocotb** — Python-based HDL testbenches (planned)

All tools are optional. See `python -m chipgate silicon --toolchain-status` to check availability.

## Phase 6: ChipSynthBench / PPA-Bench

ChipSynthBench scores RTL candidates using safety, no-regression, longevity and transparent PPA proxy metrics.

```bash
# Demo run (7 candidates)
python -m chipgate synth --demo

# Full run with all 10 candidates
python -m chipgate synth

# JSON output
python -m chipgate synth --json

# HTML report
python -m chipgate synth --html synthbench_report.html

# Show ranked candidates
python -m chipgate synth --rank

# Run from benchmark directory
python -m chipgate synth benchmarks/synthbench_v0 --json
```

See [docs/SYNTHBENCH.md](docs/SYNTHBENCH.md) for full documentation.
See [docs/PPA_METRICS.md](docs/PPA_METRICS.md) for proxy metric details.

## Phase 7: SiliconReadinessBench

SiliconReadinessBench connects ChipGate to optional open-source chip-design tool flows. It checks whether safe RTL candidates are lintable, synthesizable, formally checkable and ASIC/FPGA-flow ready. It does not guarantee real silicon correctness or fabrication readiness.

```bash
# Run demo with 4 built-in designs
python -m chipgate silicon --demo

# Run on benchmark directory
python -m chipgate silicon benchmarks/siliconbench_v0

# JSON output
python -m chipgate silicon benchmarks/siliconbench_v0 --json

# HTML report
python -m chipgate silicon benchmarks/siliconbench_v0 --html silicon_report.html

# Show toolchain status
python -m chipgate silicon --toolchain-status
```

See [docs/SILICON_READINESS.md](docs/SILICON_READINESS.md) for full documentation.
See [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md) for toolchain setup details.
See [docs/SILICON_LIMITATIONS.md](docs/SILICON_LIMITATIONS.md) for limitations.

## Phase 8: FPGABoardBench

FPGABoardBench checks whether safe RTL candidates can move toward FPGA-style hardware testing through board profiles, pin constraints, optional synthesis/place-route tooling, and optional board-test evidence. It does not guarantee ASIC silicon correctness or physical deployment safety.

```bash
# Run demo with 4 built-in designs
python -m chipgate fpga --demo

# Run on benchmark directory with JSON output
python -m chipgate fpga benchmarks/fpgabench_v0 --json

# Generate HTML report
python -m chipgate fpga benchmarks/fpgabench_v0 --html fpga_report.html

# Use a specific board profile
python -m chipgate fpga --demo --board-profile tinyfpga_style

# Show FPGA toolchain status
python -m chipgate fpga --toolchain-status
```

Built-in board profiles: `generic_fpga`, `ice40_generic`, `tinyfpga_style`, `arty_style`.

See [docs/FPGABOARD_BENCH.md](docs/FPGABOARD_BENCH.md) for full documentation.
See [docs/BOARD_PROFILES.md](docs/BOARD_PROFILES.md) for board profile specifications.
See [docs/FPGA_LIMITATIONS.md](docs/FPGA_LIMITATIONS.md) for limitations.

## Phase 9: TinyTapeoutPrep

TinyTapeoutPrep prepares a minimal DTL safety gate for an open silicon submission workflow. It generates TinyTapeout-compatible Verilog (core + wrapper + FSM variant), pinout, docs, testbench, and runs 15 submission readiness checks. It does not guarantee silicon correctness, fabrication readiness, or physical safety.

```bash
# Run demo (generates and validates all artifacts)
python -m chipgate tinytapeout --demo

# JSON output
python -m chipgate tinytapeout --demo --json

# HTML report
python -m chipgate tinytapeout --demo --html tt_report.html

# Generate to specific directory
python -m chipgate tinytapeout --demo /path/to/output
```

See [docs/TINYTAPEOUT_PREP.md](docs/TINYTAPEOUT_PREP.md) for full documentation.
See [docs/TINY_DTL_GATE.md](docs/TINY_DTL_GATE.md) for the gate design explanation.
See [docs/OPEN_SILICON_LIMITATIONS.md](docs/OPEN_SILICON_LIMITATIONS.md) for open-silicon limitations.

## Phase 10: OpenLanePhysicalBench

OpenLanePhysicalBench checks whether a tiny public-safe DTL gate can move from TinyTapeoutPrep toward reproducible ASIC physical-flow readiness using OpenLane/OpenROAD-style configuration checks, report parsing and GDS artifact hashing. It does not guarantee real silicon correctness, timing signoff, fabrication readiness or physical safety.

```bash
# Run demo
python -m chipgate physical --demo

# JSON output
python -m chipgate physical --demo --json

# HTML report
python -m chipgate physical --demo --html physical_report.html

# Toolchain status
python -m chipgate physical --toolchain-status

# Parse fixture reports
python -m chipgate physical --parse-reports benchmarks/openlanephysical_v0/fixtures

# Run with benchmark path
python -m chipgate physical benchmarks/openlanephysical_v0 --json
```

See [docs/OPENLANE_PHYSICAL_BENCH.md](docs/OPENLANE_PHYSICAL_BENCH.md) for full documentation.
See [docs/PHYSICAL_FLOW_LIMITATIONS.md](docs/PHYSICAL_FLOW_LIMITATIONS.md) for physical-flow limitations.
See [docs/GDS_ARTIFACTS.md](docs/GDS_ARTIFACTS.md) for GDS artifact hashing details.

## Phase 11: RealToolchainCI

RealToolchainCI adds CI workflows for Python tests plus optional real hardware toolchain checks. Where Verilator, Yosys, SymbiYosys, OpenLane or OpenROAD are available, ChipGate runs deeper lint, synthesis, formal and physical-readiness checks. Missing optional tools are recorded as skipped rather than treated as failures. It does not guarantee silicon correctness, fabrication readiness, timing signoff, real power, real area or physical safety.

```bash
# Quick mode (Python tests + hygiene + demos)
python -m chipgate ci --quick

# Full mode (quick + real tool stages)
python -m chipgate ci --full

# Toolchain status only
python -m chipgate ci --toolchain-status

# JSON output
python -m chipgate ci --quick --json

# HTML report
python -m chipgate ci --quick --html ci_report.html
python -m chipgate ci --full --html ci_full_report.html
```

Three GitHub Actions workflows are provided:
- **chipgate-ci.yml** — runs on push/PR: unit tests, demos, hygiene checks
- **toolchain-ci.yml** — manual dispatch: installs Verilator/Yosys, runs full CI
- **nightly-toolchain.yml** — daily at 03:00 UTC: full CI + all bench suites

See [docs/REAL_TOOLCHAIN_CI.md](docs/REAL_TOOLCHAIN_CI.md) for full documentation.
See [docs/CI_LIMITATIONS.md](docs/CI_LIMITATIONS.md) for CI limitations.

## Phase 12: FormalGate-Lite

FormalGate-Lite adds formal safety property checks for small DTL-gated RTL
designs. It can generate SBY property files, run optional SymbiYosys/Yosys
checks where available, parse reports and create evidence artifacts. It does not prove
chip correctness, fabrication readiness, timing signoff, physical safety, or
real-world actuation safety.

```bash
# List available formal properties
python -m chipgate formal --list-properties

# Run demo with built-in demo designs
python -m chipgate formal --demo

# Run with custom benchmark path
python -m chipgate formal benchmarks/formalgate_v0 --json

# Generate HTML report
python -m chipgate formal benchmarks/formalgate_v0 --html formal_report.html

# Show toolchain status
python -m chipgate formal --toolchain-status

# Full mode with real SBY/Yosys (if installed)
python -m chipgate formal benchmarks/formalgate_v0 --full --json
```

See [docs/FORMALGATE_LITE.md](docs/FORMALGATE_LITE.md) for full documentation.

## Phase 13: MutationBench

MutationBench attacks safe RTL with thousands of unsafe mutations and bypass attempts. It measures whether ChipGate detects, blocks, records and replays those failures before RTL progresses toward synthesis, FPGA, TinyTapeout or OpenLane/OpenROAD stages. It does not prove full chip correctness, physical safety, fabrication readiness, timing closure or real-world security.

```bash
# Run demo (3 seed designs, 1000 mutations)
python -m chipgate mutation --demo

# Full run with JSON output
python -m chipgate mutation benchmarks/mutationbench_v0 --json

# HTML report
python -m chipgate mutation benchmarks/mutationbench_v0 --html mutation_report.html

# Generate 1000 mutations (generate-only, no scanning)
python -m chipgate mutation --generate 1000

# Generate from specific seed
python -m chipgate mutation --seed safe_dtl_gate.v --generate 1000

# List all 20 mutation categories
python -m chipgate mutation --list-mutators
```

See [docs/MUTATIONBENCH.md](docs/MUTATIONBENCH.md) for full documentation.
See [docs/MUTATION_CATALOG.md](docs/MUTATION_CATALOG.md) for the mutation catalog.
See [docs/MUTATION_LIMITATIONS.md](docs/MUTATION_LIMITATIONS.md) for limitations.

## Roadmap

1. ~~ChipGate-lite scans Verilog~~ Done
2. ~~DTL gate module demo~~ Done
3. ~~DTL-ChipBench — Model-Free DTL Gate Benchmark (v0.2.0)~~ Done
4. ~~DTL-Connected ChipBench — Adapter Framework (v0.3.0)~~ Done
5. ~~LongevityBench — RTL-level reliability benchmark~~ Done
6. ~~ChipSynthBench / PPA-Bench — PPA proxy candidate scoring~~ Done
7. ~~SiliconReadinessBench — Open-source tool-flow readiness checks~~ Done
8. ~~FPGABoardBench — FPGA-oriented readiness and board-style validation (v0.4.0)~~ Done
9. ~~TinyTapeoutPrep — TinyTapeout submission preparation~~ Done
10. ~~OpenLanePhysicalBench — ASIC physical-flow readiness checks (v0.4.0)~~ Done
11. ~~RealToolchainCI — CI workflows for Python tests + optional real toolchain checks (v0.5.0)~~ Done
12. ~~FormalGate-Lite — Formal safety properties for small DTL-gated RTL designs (v0.8.0)~~ Done
13. ~~MutationBench — Mutation stress-test with 20 categories and evidence artifacts (v0.8.0)~~ Done
14. ~~DTL Verified Design Passport — Portable verification records for AI-generated artifacts~~ Done

## Limitations

### Phase 25: DTL Verified Design Passport

```bash
python -m chipgate passport --demo                    # Demo with built-in RTL
python -m chipgate passport --demo --json             # Demo + JSON report
python -m chipgate passport --demo --html report.html # Demo + HTML report
python -m chipgate passport --artifact design.v       # Create passport for file
python -m chipgate passport --verify-passport p.json  # Verify existing passport
python -m chipgate passport --export-badge dir/ --artifact p.json
python -m chipgate passport --replay --artifact design.v
```

The Design Passport creates a portable verification record for AI-generated or user-submitted design artifacts. It records artifact type, risk level, gates run, pass/fail results, evidence hashes, replay commands, badge status, and export decisions. See [docs/DTL_VERIFIED_DESIGN_PASSPORT.md](docs/DTL_VERIFIED_DESIGN_PASSPORT.md) for details.

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) for a full list of known limitations.

## License

MIT