# Toolchain Support

SiliconReadinessBench integrates with optional open-source EDA tools. No tool is required — all are gracefully skipped when not installed.

## Supported Tools

### Verilator
- **Purpose**: Verilog/SystemVerilog lint and simulation
- **Stage**: Stage 2 — Verilator Lint
- **Install**: `apt install verilator` or from [veripool.org](https://www.veripool.org/wiki/verilator)
- **Detection**: `verilator --version`

### Yosys
- **Purpose**: RTL synthesis
- **Stages**: Stage 3 — Synthesis, Stage 5 — FPGA flow
- **Install**: `apt install yosys` or from [yosyshq.net](https://yosyshq.net/yosys/)
- **Detection**: `yosys --version`

### SymbiYosys (sby)
- **Purpose**: Formal verification front-end
- **Stage**: Stage 4 — Formal Safety Check
- **Install**: `apt install sby` or from [symbiyosys.github.io](https://symbiyosys.github.io/)
- **Detection**: `sby --version`

### nextpnr
- **Purpose**: FPGA place-and-route
- **Stage**: Stage 5 — FPGA Readiness
- **Install**: Part of Yosys/FPGA toolchain
- **Detection**: `nextpnr-ice40 --version` (checks multiple family variants)

### OpenLane
- **Purpose**: ASIC RTL-to-GDS flow
- **Stage**: Stage 6 — ASIC Flow Readiness
- **Install**: From [efabless/openlane](https://github.com/efabless/openlane)
- **Detection**: `openlane --version`

### OpenROAD
- **Purpose**: Physical design tool
- **Stage**: Stage 6 — ASIC Flow Readiness
- **Install**: From [The-OpenROAD-Project](https://github.com/The-OpenROAD-Project/OpenROAD)
- **Detection**: `openroad --version`

## Checking Toolchain Status

```bash
python -m chipgate silicon --toolchain-status
```

Example output:
```
ChipGate SiliconReadinessBench — Toolchain Status

  Verilator        found /usr/bin/verilator (Verilator 5.020)
  Yosys            skipped
  SymbiYosys       skipped
  Nextpnr          skipped
  Openlane         skipped
  Openroad         found /usr/bin/openroad (openroad v2.0)

  Toolchain coverage: 2/6 (33%)
```

## Graceful Degradation

When a tool is not installed, the corresponding stage is classified with a `_SKIPPED_TOOL_MISSING` status. This means:

- The benchmark still runs and produces valid results
- Evidence packs are still generated
- The stage is excluded from pass-rate calculations
- No error is raised

This design ensures SiliconReadinessBench is useful in any environment, from minimal CI to fully-equipped EDA workstations.

## Security

All external tool invocations use `subprocess.run()` with explicit argument lists (no `shell=True`). This prevents command injection through design file names or content.