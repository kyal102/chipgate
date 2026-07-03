# TinyTapeoutPrep

TinyTapeoutPrep prepares a minimal DTL safety gate for an open silicon submission workflow. It generates a complete set of TinyTapeout-compatible artifacts from a small combinational safety gate design, validates them against structural checks, and produces evidence packs for reproducibility.

## What It Does

TinyTapeoutPrep generates and validates:

1. **Core Verilog** — A combinational DTL safety gate (`tiny_dtl_gate.v`)
2. **FSM Variant** — A sequential state-machine variant (`tiny_dtl_gate_fsm.v`)
3. **TinyTapeout Wrapper** — A `tt_um_chipgate_dtl_gate` module conforming to TinyTapeout pin conventions
4. **Pinout Map** — `pinout.json` mapping all signals to `ui_in[0:7]` and `uo_out[0:7]`
5. **Project Metadata** — `info.yaml` with project name, author, description, and pin mapping
6. **Documentation** — `docs/info.md` with pin tables, safety properties, and limitations
7. **Testbench** — `tb_tiny_dtl_gate.v` with 8 test cases covering all safety conditions
8. **Submission Checklist** — `submission_checklist.md` tracking 15 readiness checks
9. **Evidence Pack** — `evidence_pack.json` with SHA-256 hashes of all artifacts

## Quick Start

```bash
# Run demo (generates all artifacts and validates)
python -m chipgate tinytapeout --demo

# JSON output
python -m chipgate tinytapeout --demo --json

# HTML report
python -m chipgate tinytapeout --demo --html tt_report.html

# Generate to specific directory
python -m chipgate tinytapeout --demo /path/to/output

# Run on existing benchmark directory
python -m chipgate tinytapeout benchmarks/tinytapeoutprep_v0 --json
```

## Pin Mapping

TinyTapeout constrains designs to 8 inputs (`ui_in[0:7]`) and 8 outputs (`uo_out[0:7]`).

### Inputs (ui_in[0:7])

| Pin | Signal | Description |
|-----|--------|-------------|
| ui_in[0] | ai_output | AI/autonomous system output request |
| ui_in[1] | verifier_ok | Verification check passed |
| ui_in[2] | policy_ok | Policy compliance check passed |
| ui_in[3] | sensor_ok | Sensor health check passed |
| ui_in[4] | timeout | Operation timeout indicator |
| ui_in[5] | kill_switch | Emergency stop / kill switch |
| ui_in[6] | reset | System reset signal |
| ui_in[7] | reserved | Unused |

### Outputs (uo_out[0:7])

| Pin | Signal | Description |
|-----|--------|-------------|
| uo_out[0] | actuator_enable | Gated actuator enable output |
| uo_out[1] | blocked | Request is blocked |
| uo_out[2] | failsafe | System is in failsafe state |
| uo_out[3] | approved | Request is approved |
| uo_out[4] | evidence_pulse | Evidence pulse |
| uo_out[5:7] | reserved | Unused |

## Core Safety Logic

```
actuator_enable = ai_output && verifier_ok && policy_ok
                  && sensor_ok && !timeout && !kill_switch && !reset
```

The actuator can only be enabled when all verification checks pass and no safety overrides are active.

## 15 Submission Readiness Checks

| # | Check | Description |
|---|-------|-------------|
| 1 | Top module file exists | The top-level Verilog file is non-empty |
| 2 | Top module name matches | Module name matches `info.yaml` |
| 3 | No private imports or names | No proprietary or confidential references |
| 4 | No unsupported SV | No classes, interfaces, or other unsupported constructs |
| 5 | No inferred latches | No incomplete case/if-else in always blocks |
| 6 | Clock signal documented | Clock is present in design and docs |
| 7 | Reset signal documented | Reset is present in design and docs |
| 8 | Pinout documented | All signals listed in `info.yaml` |
| 9 | docs/info.md exists | Documentation file is non-empty |
| 10 | Testbench exists | Testbench file is non-empty |
| 11 | Safety properties listed | Safety signals documented |
| 12 | ChipGate scan passes | Structural safety scan clean |
| 13 | LongevityBench | Pass or skip safely |
| 14 | SiliconReadinessBench | Pass or skip safely |
| 15 | FPGABoardBench | Pass or skip safely |

Checks 13-15 gracefully degrade to SKIP when external tools are unavailable.

## Safety Properties

1. kill_switch forces actuator_enable low
2. timeout forces actuator_enable low
3. reset forces actuator_enable low
4. actuator_enable implies verifier_ok, policy_ok, and sensor_ok
5. FAILSAFE state cannot jump directly to APPROVED (FSM variant)

## CLI Reference

```
python -m chipgate tinytapeout [--demo] [--json] [--html FILE] [--generate-template] [--submission-check] [path]
```

| Flag | Description |
|------|-------------|
| `--demo` | Generate and validate all demo artifacts |
| `--json` | Output results as JSON |
| `--html FILE` | Generate HTML report to FILE |
| `--generate-template` | Generate template artifacts only |
| `--submission-check` | Run submission checks on existing artifacts |
| `path` | Output directory (default: temp directory) |

## Metrics

| Metric | Description |
|--------|-------------|
| designs_generated | Number of Verilog designs generated |
| wrappers_generated | Number of TinyTapeout wrappers created |
| pinout_checks_passed | Number of pinout validations passed |
| submission_checks_passed | Number of the 15 checks that passed |
| submission_checks_failed | Number of the 15 checks that failed |
| submission_checks_skipped | Number of the 15 checks that skipped |
| safety_properties_count | Number of documented safety properties |
| private_leak_count | Number of private/proprietary name detections |
| testbench_count | Number of testbenches generated |
| evidence_packs_created | Number of evidence pack files created |

## Module Structure

| Module | Role |
|--------|------|
| `tt_pinout.py` | Pinout definition, validation, JSON serialisation |
| `tt_wrapper.py` | Core, wrapper, and FSM Verilog generation |
| `tt_docs.py` | info.yaml, info.md, testbench, checklist generation |
| `tt_submission_check.py` | 15 submission readiness checks |
| `tt_report.py` | Static HTML report generation |
| `tinytapeout_prep.py` | Main orchestrator and evidence pack creation |

## Limitations

- Passing TinyTapeoutPrep does not mean the design has been accepted by Tiny Tapeout, fabricated, physically tested, timing-closed, power-characterised, or certified for safety-critical use.
- The generated artifacts passed structural checks only. Actual Tiny Tapeout submission requires official GitHub Actions CI, GDS build, and manual review on tinytapeout.com.
- This is a public demonstration design. It does not guarantee silicon correctness, fabrication readiness, or physical safety.
- Not certified for medical, defence, or robotics use.
- LongevityBench, SiliconReadinessBench, and FPGABoardBench results gracefully degrade to SKIPPED when external tools are unavailable.