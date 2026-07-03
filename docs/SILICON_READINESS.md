# SiliconReadinessBench

SiliconReadinessBench checks whether safe RTL candidates survive synthesis, formal checks, FPGA flow and ASIC-flow readiness using optional open-source EDA tools.

## What It Does

SiliconReadinessBench takes Verilog/SystemVerilog designs through a 6-stage pipeline:

1. **RTL Safety Precheck** — Runs the existing ChipGate scanner to check for unsafe patterns, missing resets, ungated outputs, and other safety issues. Unsafe designs are blocked from proceeding to later stages unless explicitly allowed with `--allow-unsafe`.

2. **Verilator Lint** — If Verilator is installed, runs lint checks on the RTL. Captures warning and error counts. Classifies results as `LINT_PASS`, `LINT_FAIL`, or `LINT_SKIPPED_TOOL_MISSING`.

3. **Yosys Synthesis** — If Yosys is installed, synthesizes the RTL and extracts cell count, wire count, process count, and memory count statistics. Classifies results as `SYNTHESIS_PASS`, `SYNTHESIS_FAIL`, or `SYNTHESIS_SKIPPED_TOOL_MISSING`.

4. **Formal Safety Check** — If SymbiYosys (sby) is installed, runs BMC-based formal verification against safety properties such as kill-switch enforcement, verifier gating, and policy gating. Classifies results as `FORMAL_PASS`, `FORMAL_FAIL`, or `FORMAL_SKIPPED_TOOL_MISSING`.

5. **FPGA Readiness** — If Yosys and nextpnr are both installed, attempts a minimal FPGA synthesis and place-and-route flow. Does not program a physical board. Classifies results as `FPGA_FLOW_PASS`, `FPGA_FLOW_FAIL`, or `FPGA_FLOW_SKIPPED_TOOL_MISSING`.

6. **ASIC Flow Readiness** — If OpenROAD or OpenLane is installed, checks whether the RTL can be accepted by the tool. Does NOT claim tapeout readiness. Classifies results as `ASIC_FLOW_READY`, `ASIC_FLOW_FAIL`, or `ASIC_FLOW_SKIPPED_TOOL_MISSING`.

## CLI Usage

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

# Allow unsafe designs to proceed to tool stages
python -m chipgate silicon --demo --allow-unsafe
```

## Toolchain

SiliconReadinessBench supports these optional tools:

| Tool | Purpose | Stage |
|------|---------|-------|
| Verilator | Lint checking | Stage 2 |
| Yosys | Synthesis | Stage 3 |
| SymbiYosys (sby) | Formal verification | Stage 4 |
| nextpnr | FPGA place-and-route | Stage 5 |
| OpenLane | ASIC flow | Stage 6 |
| OpenROAD | ASIC flow | Stage 6 |

No external tool is required. All tools are optional and gracefully skipped when missing.

## Demo Designs

Four built-in demo designs are included:

- `safe_dtl_gate` — Properly gated DTL safety output with async reset. Expected: safety precheck pass.
- `unsafe_direct_actuator` — Ungated direct actuator drive. Expected: safety precheck fail, blocked.
- `safe_fsm_gate` — FSM-gated DTL safety output with default case and reset. Expected: safety precheck pass.
- `bad_syntax` — Intentionally malformed Verilog. Expected: safety precheck fail.

## Evidence

Each design generates an evidence record containing:
- Design ID and RTL hash (SHA-256)
- Per-stage results (safety, lint, synthesis, formal, FPGA, ASIC)
- Tool versions used
- Artifact hashes for reproducibility
- Replay command
- Certificate hash for integrity verification
- Public wording disclaimer

## Metrics

| Metric | Description |
|--------|-------------|
| `designs_tested` | Total number of designs processed |
| `safety_precheck_passed` | Designs that passed ChipGate safety precheck |
| `lint_pass_rate` | Fraction of non-skipped designs that passed Verilator lint |
| `synthesis_pass_rate` | Fraction of non-skipped designs that passed Yosys synthesis |
| `formal_pass_rate` | Fraction of non-skipped designs that passed formal checks |
| `fpga_flow_pass_rate` | Fraction of non-skipped designs that passed FPGA flow |
| `asic_flow_ready_rate` | Fraction of non-skipped designs that passed ASIC flow readiness |
| `cell_count` | Total synthesized cell count (from Yosys stats) |
| `wire_count` | Total synthesized wire count (from Yosys stats) |
| `toolchain_coverage` | Fraction of supported tools found on PATH |
| `artifact_hash_count` | Total number of SHA-256 artifact hashes generated |
| `evidence_packs_created` | Number of evidence records created |
| `replay_match_rate` | Replay command reproducibility rate |

## Public Wording

> SiliconReadinessBench checks whether safe RTL candidates survive synthesis, formal checks, FPGA flow and ASIC-flow readiness. It does not guarantee silicon correctness, physical safety, real power, real timing signoff, physical durability, regulatory conformance or fabrication readiness. It checks whether RTL passes reproducible open-source tool-flow readiness stages.

See [SILICON_LIMITATIONS.md](SILICON_LIMITATIONS.md) for detailed limitations.
See [TOOLCHAIN.md](TOOLCHAIN.md) for toolchain setup details.