# RealToolchainCI

RealToolchainCI is the ChipGate Phase 11 CI pipeline. It runs Python unit
tests, hygiene checks, and demo commands in every invocation. When real
open-source EDA tools are installed, it runs additional toolchain stages
(Verilator, Yosys, SymbiYosys, OpenLane, OpenROAD) on a safe reference
design. Missing tools are gracefully skipped, never treated as failures.

RealToolchainCI records available open-source hardware toolchain checks and
their outputs. Passing CI does not guarantee silicon correctness, fabrication
readiness, physical safety, timing signoff, real power or real area.

---

## Table of Contents

- [Running RealToolchainCI](#running-realtoolehainci)
- [Output Formats](#output-formats)
- [CI Toolchain Stages](#ci-toolchain-stages)
- [Hygiene Checks](#hygiene-checks)
- [GitHub Actions Workflows](#github-actions-workflows)
- [Status Reference](#status-reference)
- [Metrics Tracked](#metrics-tracked)
- [What the Benchmark Does NOT Prove](#what-the-benchmark-does-not-prove)
- [Missing Tools Are SKIPPED, Not FAIL](#missing-tools-are-skipped-not-fail)
- [Evidence and Artifact Manifest](#evidence-and-artifact-manifest)
- [Quick vs Full Mode](#quick-vs-full-mode)

---

## Running RealToolchainCI

```bash
# Quick mode (default): Python tests + hygiene + demo commands
python -m chipgate ci --quick

# Full mode: quick + real Verilator/Yosys/SBY/OpenLane/OpenROAD stages
python -m chipgate ci --full

# Show toolchain detection status and exit (no pipeline run)
python -m chipgate ci --toolchain-status
```

The `--toolchain-status` flag detects which tools are available on the
current system, prints their paths and versions, and exits without running
the pipeline.

## Output Formats

### Terminal

By default, results are printed to the terminal with ANSI colour coding.

### JSON

```bash
python -m chipgate ci --quick --json
```

Outputs a JSON object containing the full `CIResult` structure: overall
status, timestamp, mode, toolchain status, hygiene results, stage results,
demo results, metrics, public wording, and limitation text.

### HTML

```bash
python -m chipgate ci --quick --html ci_report.html
python -m chipgate ci --full --html ci_full_report.html
```

Generates a self-contained, static, dependency-free HTML report with
inline CSS (no JavaScript). The report includes:

- Summary cards (overall status, tests passed/failed, tools found/missing)
- Toolchain status table
- Hygiene check results
- Stage results table
- Demo command results
- Public disclaimer and limitation text

The HTML report is suitable for archiving as a CI artifact.

---

## CI Toolchain Stages

RealToolchainCI integrates with five open-source EDA tools. Each tool is
detected at runtime. When a tool is available, the corresponding stage
executes; when it is not installed, the stage is marked SKIPPED.

| Stage | Tool | What It Does | Detection |
|-------|------|--------------|-----------|
| Verilator | `verilator` | Runs `--lint-only -Wall` on the safe reference design | `verilator --version` |
| Yosys | `yosys` | Runs `read_verilog`, `hierarchy -check`, `stat` via a temp script | `yosys --version` |
| SymbiYosys | `sby` | Runs a bounded model check (BMC, depth 10) with a generated `.sby` file | `sby --version` |
| OpenLane | `openlane` | Invokes `--help` to verify the tool is accessible (dry-run) | `openlane --version` |
| OpenROAD | `openroad` | Invokes `--version` to verify the tool is accessible (dry-run) | `openroad --version` |

All tool invocations use `subprocess.run()` with explicit argument lists
(no `shell=True`). Each stage has a timeout (30--120 seconds depending
on the tool) to prevent CI hangs.

---

## Hygiene Checks

Before running tool stages, RealToolchainCI scans all Python files in the
`chipgate/` package for the following hygiene conditions:

| Check | What It Detects | Failure Means |
|-------|-----------------|---------------|
| No private imports | Patterns such as `jarvi3`, `PRIVATE_DTL`, `proprietary`, `confidential`, `internal_only`, `not_for_public` | A private or proprietary name was found in the public codebase |
| No secrets | Patterns such as `api_key = '`, `secret_key = '`, `password = '`, `token = '`, `PRIVATE_TOKEN` | A secret or credential pattern was found |
| No shell=True | Literal `shell=True` in any Python source | A subprocess call uses shell interpretation, which is a command-injection risk |
| English-only | CJK characters (U+4E00--U+9FFF, U+3040--U+30FF, U+AC00--U+D7AF) and emoji (U+1F600--U+1F64F) | Non-English or non-ASCII content was found |
| No forbidden overclaim phrases | Phrases like "proves silicon correctness", "fabrication ready", "timing signoff", "real power", "real area", "physically safe", "regulatory conformance", "NVIDIA", "medical device", "defence certification", "robotics certification", "safety-critical deployment" | A forbidden overclaim phrase was found in the codebase |

A hygiene failure causes the overall CI status to be `CI_FAIL` even if
all other stages pass. This ensures the public codebase never contains
private references, secrets, or misleading claims.

---

## GitHub Actions Workflows

Three workflows are provided:

### chipgate-ci.yml (Basic CI)

- **Triggers**: push to `main`/`develop`, pull requests to `main`
- **Matrix**: Python 3.9, 3.10, 3.11, 3.12
- **Steps**: unit tests, all demo commands, `ci --quick`, and inline
  hygiene checks (private imports, secrets, `shell=True`, English-only,
  forbidden overclaim phrases)
- **Additional job**: `lint-python` runs flake8 on the `chipgate/` package

### toolchain-ci.yml (Manual Dispatch)

- **Triggers**: `workflow_dispatch` (manual), push to `main` when
  `chipgate/**` or `tests/**` change
- **Jobs**:
  - `toolchain-checks`: installs Verilator and Yosys, runs `ci --full`,
    uploads JSON and HTML reports (30-day retention)
  - `verilator-stage`: runs Verilator lint on safe and bad-syntax designs
  - `yosys-stage`: runs synthesis on the safe design
- All jobs use `continue-on-error: true` so that missing tools do not
  block the workflow

### nightly-toolchain.yml (Nightly)

- **Triggers**: scheduled daily at 03:00 UTC, `workflow_dispatch` (manual)
- **Steps**: installs Verilator, Yosys, and sby (best-effort), runs
  `ci --full`, the silicon bench, FPGA bench, and physical bench
- **Artifacts**: uploads all reports (90-day retention) and evidence packs

---

## Status Reference

RealToolchainCI introduces 19 new statuses. These are distinct from the
existing scan, bench, and silicon-readiness statuses.

### Overall CI Statuses

| Status | Meaning |
|--------|---------|
| `CI_PASS` | All executed stages passed; no failures, no skips |
| `CI_FAIL` | One or more stages failed (including hygiene) |
| `CI_PARTIAL` | No failures, but at least one stage was SKIPPED (tool missing) |

### Toolchain Detection Statuses

| Status | Meaning |
|--------|---------|
| `TOOLCHAIN_FOUND` | A toolchain tool was detected on the system |
| `TOOLCHAIN_MISSING` | A toolchain tool was not found on the system |

### Per-Stage Statuses (5 tools x 3 outcomes = 15)

| Status | Meaning |
|--------|---------|
| `VERILATOR_CI_PASS` | Verilator lint completed with no errors |
| `VERILATOR_CI_FAIL` | Verilator lint reported errors or timed out |
| `VERILATOR_CI_SKIPPED` | Verilator not installed |
| `YOSYS_CI_PASS` | Yosys synthesis completed successfully |
| `YOSYS_CI_FAIL` | Yosys reported errors or timed out |
| `YOSYS_CI_SKIPPED` | Yosys not installed |
| `SYMBIYOSYS_CI_PASS` | SymbiYosys BMC completed successfully |
| `SYMBIYOSYS_CI_FAIL` | SymbiYosys reported errors or timed out |
| `SYMBIYOSYS_CI_SKIPPED` | SymbiYosys (sby) not installed |
| `OPENLANE_CI_PASS` | OpenLane invocation succeeded (tool accessible) |
| `OPENLANE_CI_FAIL` | OpenLane invocation failed or timed out |
| `OPENLANE_CI_SKIPPED` | OpenLane not installed |
| `OPENROAD_CI_PASS` | OpenROAD invocation succeeded (tool accessible) |
| `OPENROAD_CI_FAIL` | OpenROAD invocation failed or timed out |
| `OPENROAD_CI_SKIPPED` | OpenROAD not installed |

### Artifact Status

| Status | Meaning |
|--------|---------|
| `CI_ARTIFACTS_CREATED` | CI artifact manifest was generated with hashes |

---

## Metrics Tracked

The CI result includes the following metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `overall_status` | string | `CI_PASS`, `CI_FAIL`, or `CI_PARTIAL` |
| `mode` | string | `"quick"` or `"full"` |
| `timestamp_utc` | string | ISO 8601 UTC timestamp |
| `python_tests_passed` | integer | Number of pytest tests that passed |
| `python_tests_failed` | integer | Number of pytest tests that failed |
| `toolchain_tools_found` | integer | Number of EDA tools detected (0--5) |
| `toolchain_tools_missing` | integer | Number of EDA tools not detected (0--5) |
| `artifacts_uploaded` | integer | Number of artifacts recorded |
| `evidence_packs_created` | integer | Number of evidence packs generated |
| `hashes_created` | integer | Number of SHA-256 hashes in the manifest |
| `ci_replay_match_rate` | float | Replay determinism (1.0 = fully deterministic) |

---

## What the Benchmark Does NOT Prove

> Passing RealToolchainCI does not guarantee silicon correctness, fabrication
> readiness, physical safety, timing signoff, real power, real area, safety
> certification, or any comparison to NVIDIA hardware or tools.

Specifically, RealToolchainCI does **not**:

- **Prove silicon correctness** -- a `VERILATOR_CI_PASS` means the
  reference design passed lint; it does not mean the logic is functionally
  correct or free of bugs.
- **Prove fabrication readiness** -- `OPENLANE_CI_PASS` means the tool
  is accessible; it does not mean the design is tapeout-ready.
- **Prove timing signoff** -- no static timing analysis signoff is
  performed.
- **Measure real power** -- no dynamic or leakage power analysis is
  performed.
- **Measure real area** -- no gate-level or die-area measurement is
  performed.
- **Certify for safety-critical use** -- no medical, defence, aerospace,
  or robotics certification is implied or provided.
- **Compare to NVIDIA** -- no benchmarking or comparison against any
  NVIDIA product, tool, or workflow is performed.

---

## Missing Tools Are SKIPPED, Not FAIL

When a tool is not installed on the system, the corresponding stage is
assigned a `*_SKIPPED` status. This is **not** a failure. It means the
tool was not available for this run.

Key points:

- SKIPPED stages are excluded from pass-rate calculations.
- The overall CI status becomes `CI_PARTIAL` (not `CI_FAIL`) when one or
  more stages are skipped but none failed.
- CI results remain valid and artifact manifests are still generated.
- A `CI_PARTIAL` result on a system with no EDA tools installed is
  expected and normal.

This design ensures RealToolchainCI is useful in any environment, from
minimal CI runners (Python only) to fully-equipped EDA workstations.

---

## Evidence and Artifact Manifest

When CI runs, it can produce an artifact manifest containing:

| Field | Description |
|-------|-------------|
| `chipgate_version` | Version string of the running ChipGate |
| `timestamp` | ISO 8601 UTC timestamp |
| `commit_sha` | Git commit SHA (when available) |
| `workflow_name` | GitHub Actions workflow name (when available) |
| `run_id` | GitHub Actions run ID (when available) |
| `overall_status` | Final CI status |
| `mode` | `quick` or `full` |
| `toolchain_status` | Per-tool detection results |
| `python_tests_passed` | Pytest pass count |
| `python_tests_failed` | Pytest fail count |
| `artifact_hashes` | List of SHA-256 hashes for each stage and demo output |
| `hashes_created` | Total number of hashes in the manifest |
| `manifest_hash` | Self-hash of the manifest (first 32 hex characters) |
| `public_wording` | Standard disclaimer text |

Each artifact hash includes the label, SHA-256 digest, and size in bytes,
enabling independent verification that the inputs and outputs have not been
tampered with.

---

## Quick vs Full Mode

### Quick Mode (`--quick`)

Quick mode is the default. It runs:

1. Toolchain detection (which tools are available)
2. Hygiene checks (private imports, secrets, shell=True, English-only,
   overclaim phrases)
3. Python unit tests (`pytest tests/ -q`)
4. Demo commands (bench, longevity, synth, silicon, fpga, tinytapeout,
   physical -- all with `--demo`)

Quick mode does **not** invoke any external EDA tools. It typically
completes in under two minutes.

### Full Mode (`--full`)

Full mode runs everything in quick mode, plus:

5. Verilator lint stage (on the safe reference design)
6. Yosys synthesis stage (on the safe reference design)
7. SymbiYosys BMC stage (on the safe reference design)
8. OpenLane accessibility check
9. OpenROAD accessibility check

Stages 5--9 are only executed if the corresponding tools are installed.
If a tool is missing, the stage is SKIPPED.

| Stage | Quick | Full |
|-------|-------|------|
| Toolchain detection | Yes | Yes |
| Hygiene checks | Yes | Yes |
| Python unit tests | Yes | Yes |
| Demo commands | Yes | Yes |
| Verilator lint | No | Yes (if installed) |
| Yosys synthesis | No | Yes (if installed) |
| SymbiYosys BMC | No | Yes (if installed) |
| OpenLane check | No | Yes (if installed) |
| OpenROAD check | No | Yes (if installed) |