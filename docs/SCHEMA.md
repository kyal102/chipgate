# ChipGate JSON Schema Reference

Complete reference for all JSON output formats produced by ChipGate, including
the ScanResult, EvidencePack, and supporting schemas.

---

## Table of Contents

- [ScanResult Schema](#scanresult-schema)
- [Finding Schema](#finding-schema)
- [EvidencePack Schema](#evidencepack-schema)
- [LintResult Schema](#lintresult-schema)
- [FormalCheckResult Schema](#formalcheckresult-schema)
- [SafetyAnalysis Schema](#safetyanalysis-schema)
- [SafetyPattern Schema](#safetypattern-schema)
- [Status Constants](#status-constants)
- [Rule Catalogue (CG001–CG014)](#rule-catalogue-cg001cg014)

---

## ScanResult Schema

The primary output of a ChipGate scan. Returned by `scan_file()` and emitted via
the `--json` CLI flag.

```json
{
  "file": "string",
  "module_name": "string",
  "statuses": ["string"],
  "findings": [Finding],
  "risky_signals": ["string"],
  "required_gates": ["string"],
  "rules_checked": ["string"],
  "public_wording": "string",
  "replay_command": "string",
  "certificate_hash": "string"
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `file` | `string` | Absolute or relative path to the scanned Verilog file |
| `module_name` | `string` | Name of the first `module` found in the file; empty if none detected |
| `statuses` | `string[]` | Ordered list of status constants indicating overall scan result |
| `findings` | `Finding[]` | List of all rule violations and informational detections |
| `risky_signals` | `string[]` | Names of signals flagged as safety-critical risks |
| `required_gates` | `string[]` | List of verification gate signals expected by the DTL model |
| `rules_checked` | `string[]` | List of rule IDs that were evaluated during the scan |
| `public_wording` | `string` | Mandatory disclaimer text that must accompany all results |
| `replay_command` | `string` | CLI command to deterministically reproduce this scan |
| `certificate_hash` | `string` | SHA-256 hash of the findings set for integrity verification |

### `required_gates` Values

The `required_gates` array always contains these five signals:

```json
["verifier_ok", "policy_ok", "kill_switch", "sensor_ok", "timeout"]
```

These represent the complete DTL gate chain. A design does not need all five
to pass, but ChipGate reports which are missing via findings.

---

## Finding Schema

A single rule violation or detection result.

```json
{
  "rule_id": "string",
  "severity": "string",
  "description": "string",
  "line_number": "integer",
  "signal_name": "string",
  "detail": "string"
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | `string` | Rule identifier, e.g. `"CG001"`, `"CG014"`. Matches entries in the rule catalogue |
| `severity` | `string` | One of: `"critical"`, `"high"`, `"medium"`, `"low"`, `"info"` |
| `description` | `string` | Human-readable summary of the finding |
| `line_number` | `integer` | Line number in the source file where the issue was detected; `0` if file-level |
| `signal_name` | `string` | Name of the affected signal, if applicable; empty string if not applicable |
| `detail` | `string` | Additional explanation or rationale for the finding |

### Severity Levels

| Severity | Meaning | Impact on Scan |
|----------|---------|----------------|
| `critical` | Direct safety violation or structural error | Causes `RTL_SCAN_FAIL` |
| `high` | Significant code quality issue that may lead to bugs or latches | May contribute to failure |
| `medium` | Missing verification asset (assertions, testbench) | Does not cause scan failure |
| `low` | Minor issue or informational notice | Does not cause scan failure |
| `info` | Positive detection (e.g., safety gate found) | Never a failure indicator |

---

## EvidencePack Schema

An extended output format that wraps a ScanResult with metadata, optional tool
results, and an integrity hash. Generated via the `--evidence` flag.

```json
{
  "chipgate_version": "string",
  "timestamp_utc": "string",
  "public_wording": "string",
  "evidence_pack_hash": "string",
  "file": "string",
  "module_name": "string",
  "statuses": ["string"],
  "findings": [Finding],
  "risky_signals": ["string"],
  "required_gates": ["string"],
  "rules_checked": ["string"],
  "replay_command": "string",
  "certificate_hash": "string",
  "lint": { ... },
  "formal": { ... },
  "safety_analysis": { ... }
}
```

### Fields Beyond ScanResult

| Field | Type | Description |
|-------|------|-------------|
| `chipgate_version` | `string` | ChipGate release version, e.g. `"0.1.0"` |
| `timestamp_utc` | `string` | ISO 8601 UTC timestamp of pack generation |
| `evidence_pack_hash` | `string` | SHA-256 of the entire pack (excluding this field) for tamper detection |
| `lint` | `LintResult?` | Optional; present when `--lint` flag is used |
| `formal` | `FormalCheckResult?` | Optional; present when `--formal` flag is used |
| `safety_analysis` | `SafetyAnalysis?` | Optional; present when `--safety` flag is used |

### Required Fields for Validation

The following fields must be present for an evidence pack to be considered valid:

```
chipgate_version, timestamp_utc, file, statuses, findings, rules_checked,
risky_signals, required_gates, replay_command, certificate_hash, public_wording
```

### Hash Integrity

The `evidence_pack_hash` is computed as:

```
SHA-256(JSON.stringify(pack, sorted_keys=true))
```

where `pack` excludes the `evidence_pack_hash` field itself. To validate:

1. Remove the `evidence_pack_hash` field from the JSON object
2. Re-serialise with sorted keys
3. Compute SHA-256
4. Compare against the stored `evidence_pack_hash`

A mismatch indicates the pack has been tampered with.

### Default File Location

When `--evidence` is used without specifying an output path, the evidence pack
is saved alongside the scanned file:

```
examples/safe_dtl_gate.v  ->  examples/safe_dtl_gate.evidence.json
```

---

## LintResult Schema

Result of an external lint check (currently Verilator only).

```json
{
  "tool": "string",
  "available": "boolean",
  "passed": "boolean",
  "warnings": ["string"],
  "errors": ["string"],
  "command": "string"
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `tool` | `string` | Name of the lint tool; currently always `"verilator"` |
| `available` | `boolean` | `true` if the tool is installed and executable on the system |
| `passed` | `boolean` | `true` if the tool ran and reported zero errors |
| `warnings` | `string[]` | Lines from tool output classified as warnings |
| `errors` | `string[]` | Lines from tool output classified as errors, or skip/error messages |
| `command` | `string` | The full shell command that was executed |

### Graceful Degradation

When Verilator is not installed, the LintResult indicates graceful skip:

```json
{
  "tool": "verilator",
  "available": false,
  "passed": false,
  "warnings": [],
  "errors": ["Verilator not installed — skipping external lint. Run internal scan instead."],
  "command": ""
}
```

---

## FormalCheckResult Schema

Result of the formal verification readiness check.

```json
{
  "ready": "boolean",
  "assertion_count": "integer",
  "issues": ["string"],
  "sby_config": "string",
  "tool_available": "boolean"
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `ready` | `boolean` | `true` if the design has assertions and no blocking issues |
| `assertion_count` | `integer` | Number of `assert`, `cover`, or `assume` statements detected |
| `issues` | `string[]` | List of issues preventing formal readiness |
| `sby_config` | `string` | Generated SBY configuration file content; empty if no assertions |
| `tool_available` | `boolean` | `true` if both Yosys and SBY are installed |

### SBY Config Format

When `assertion_count > 0`, the `sby_config` field contains a ready-to-use
SymbiYosys configuration:

```
[options]
mode prove
depth 20

[engines]
smtbmc

[script]
read_verilog <filename>
prep -top <module_name>

[files]
<filename>
```

Save this to a `.sby` file and run with `sby my_design.sby`.

---

## SafetyAnalysis Schema

Result of the safety pattern analysis, evaluating five safety patterns.

```json
{
  "safety_score": "float",
  "gate_chain_complete": "boolean",
  "critical_gaps": ["string"],
  "patterns": [SafetyPattern]
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `safety_score` | `float` | Composite safety score from `0.0` (no patterns) to `1.0` (all patterns) |
| `gate_chain_complete` | `boolean` | `true` if DTL gate chain and kill switch are both present with no critical gaps |
| `critical_gaps` | `string[]` | List of critical missing patterns; e.g. `["DTL verification gate chain incomplete"]` |
| `patterns` | `SafetyPattern[]` | Detailed results for each of the five safety patterns |

### Scoring Weights

| Pattern | Weight | Condition |
|---------|--------|-----------|
| DTL Gate Chain | 0.40 | `verifier_ok`, `policy_ok`, and `kill_switch` all present |
| Sensor Validation | 0.15 | `sensor_ok` / `sensor_valid` / `sensor_check` signal found |
| Timeout Protection | 0.15 | `timeout` / `watchdog` / `wdog` signal found |
| Failsafe FSM | 0.15 | IDLE/FAILSAFE state machine with `state` signal detected |
| Kill Switch Coverage | 0.15 | `kill_switch` declared and used in actuator gating logic |

---

## SafetyPattern Schema

A single safety pattern detection result within the SafetyAnalysis.

```json
{
  "pattern_name": "string",
  "present": "boolean",
  "description": "string",
  "signals_involved": ["string"],
  "recommendation": "string"
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `pattern_name` | `string` | Name of the pattern: `"DTL Gate Chain"`, `"Sensor Validation"`, `"Timeout Protection"`, `"Failsafe FSM"`, `"Kill Switch Coverage"` |
| `present` | `boolean` | `true` if the pattern was detected in the design |
| `description` | `string` | Explanation of what this pattern checks and why it matters |
| `signals_involved` | `string[]` | Names of signals related to this pattern |
| `recommendation` | `string` | Suggested fix or improvement if the pattern is not present |

---

## Status Constants

Status constants represent possible outcomes of verification checks. They are
returned in the `statuses` array of both ScanResult and EvidencePack outputs.

### Complete List

| Status | Category | Meaning |
|--------|----------|---------|
| `RTL_SCAN_PASS` | Pass | No critical findings; design passes structural safety scan |
| `RTL_SCAN_FAIL` | Fail | One or more critical findings detected |
| `RTL_LINT_PASS` | Pass | External lint tool ran and reported zero errors |
| `RTL_LINT_FAIL` | Fail | External lint tool reported errors or is unavailable |
| `SIMULATION_PASS` | Pass | Simulation ran and all tests passed (future) |
| `SIMULATION_FAIL` | Fail | Simulation reported test failures (future) |
| `FORMAL_READY` | Pass | Design has assertions and is structurally ready for formal verification |
| `FORMAL_NOT_READY` | Fail | Design lacks assertions or has blocking issues for formal verification |
| `ASSERTION_MISSING` | Fail | No `assert`/`cover`/`assume` statements found in the design |
| `UNSAFE_BYPASS_PATH` | Fail | A potential shortcut around safety gates was detected |
| `UNGATED_OUTPUT` | Fail | An actuator output is driven without required verification gates |
| `SAFETY_GATE_PRESENT` | Pass | Output is properly gated by verification signals |
| `NEEDS_HUMAN_REVIEW` | Fail | Non-critical findings require human review |
| `EVIDENCE_PACK_CREATED` | Pass | Evidence pack JSON file was successfully generated |

### Status Categories

**Pass statuses** indicate successful verification of a specific aspect:

```
RTL_SCAN_PASS, RTL_LINT_PASS, SIMULATION_PASS,
FORMAL_READY, SAFETY_GATE_PRESENT, EVIDENCE_PACK_CREATED
```

**Fail statuses** indicate problems that must be addressed:

```
RTL_SCAN_FAIL, RTL_LINT_FAIL, SIMULATION_FAIL,
FORMAL_NOT_READY, ASSERTION_MISSING, UNSAFE_BYPASS_PATH,
UNGATED_OUTPUT, NEEDS_HUMAN_REVIEW
```

### Status Determination Logic

The first status in the `statuses` array is always either `RTL_SCAN_PASS` or
`RTL_SCAN_FAIL`, determined by:

- `RTL_SCAN_FAIL` — if any finding has severity `critical`, or any finding
  matches rule IDs CG006, CG007, CG008, or CG013
- `RTL_SCAN_PASS` — if no critical or ungated-output findings exist

Additional statuses are appended based on detected patterns:
- `UNGATED_OUTPUT` — if CG006, CG007, CG008, or CG013 triggered
- `SAFETY_GATE_PRESENT` — if CG014 triggered
- `ASSERTION_MISSING` — if CG010 triggered
- `UNSAFE_BYPASS_PATH` — if CG013 triggered
- `FORMAL_READY` — if assertions exist and no critical findings
- `FORMAL_NOT_READY` — if assertions are missing or critical findings exist
- `NEEDS_HUMAN_REVIEW` — if any MEDIUM or LOW findings exist
- `EVIDENCE_PACK_CREATED` — if `--evidence` flag was used

---

## Rule Catalogue (CG001–CG014)

ChipGate implements 14 rules organised by severity. Each rule is identified by
a unique `CGxxx` ID.

### Summary Table

| Rule ID | Severity | Category | Description |
|---------|----------|----------|-------------|
| CG001 | `critical` | Structure | Missing reset signal |
| CG002 | `high` | Structure | Missing default case in case/if-else chain |
| CG003 | `high` | Structure | Possible latch inference |
| CG004 | `critical` | Structure | Undriven output |
| CG005 | `low` | Structure | Unused input |
| CG006 | `critical` | Safety | Hardcoded bypass — direct input-to-actuator assignment |
| CG007 | `critical` | Safety | Actuator output not gated by verifier_ok |
| CG008 | `critical` | Safety | Actuator output not gated by policy_ok |
| CG009 | `critical` | Safety | Kill switch / emergency stop path missing |
| CG010 | `medium` | Verification | No assertions found in the design |
| CG011 | `medium` | Verification | No testbench companion file detected |
| CG012 | `low` | Verification | No replay command generated yet |
| CG013 | `critical` | Safety | Unsafe bypass path — complex expression without gates |
| CG014 | `info` | Safety | Safety gate present — output properly gated |

### Detailed Rule Descriptions

#### CG001 — Missing Reset Signal

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Description** | Missing reset signal — no 'rst' or 'reset' found in sensitivity list or always block |
| **Rationale** | Safety-critical designs must have a reset to reach a known state on power-up. |
| **Detects** | Absence of `rst`, `reset`, `rst_n`, `reset_n`, `areset`, or `sreset` in module ports or sensitivity lists |

#### CG002 — Missing Default Case

| Field | Value |
|-------|-------|
| **Severity** | `high` |
| **Description** | Missing default case in case/if-else chain |
| **Rationale** | Missing defaults can cause latches or undefined state in synthesis. |
| **Detects** | `case` statements without a `default:` branch within 50 lines |

#### CG003 — Possible Latch Inference

| Field | Value |
|-------|-------|
| **Severity** | `high` |
| **Description** | Possible latch inference — incomplete assignment in combinational block |
| **Rationale** | Latches in RTL often indicate unintended behaviour and can cause timing issues. |
| **Detects** | Combinational `always` blocks (no `posedge`/`negedge`) with `if` but no `else` |

#### CG004 — Undriven Output

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Description** | Undriven output — output port declared but never assigned |
| **Rationale** | Undriven outputs float to undefined values, which can cause unpredictable hardware behaviour. |
| **Detects** | Output ports that never appear as the target of a continuous or procedural assignment |

#### CG005 — Unused Input

| Field | Value |
|-------|-------|
| **Severity** | `low` |
| **Description** | Unused input — input port declared but never referenced |
| **Rationale** | Unused inputs may indicate a design error or incomplete connection. |
| **Detects** | Input ports that appear only once (in their declaration) |

#### CG006 — Hardcoded Bypass

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Description** | Hardcoded bypass — direct assignment from input to actuator/safety output |
| **Rationale** | A direct bypass skips all verification gates and can cause unsafe actuation. |
| **Detects** | Actuator signals assigned from a single identifier (e.g. `assign out = in;`) |

#### CG007 — Missing verifier_ok Gate

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Description** | Actuator output not gated by verifier_ok |
| **Rationale** | DTL requires that safety-critical outputs pass through a verifier gate before actuation. |
| **Detects** | Actuator signal expressions that do not contain `verifier_ok` |

#### CG008 — Missing policy_ok Gate

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Description** | Actuator output not gated by policy_ok |
| **Rationale** | DTL requires policy compliance checks before enabling physical actuation. |
| **Detects** | Actuator signal expressions that do not contain `policy_ok` |

#### CG009 — Missing Kill Switch

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Description** | Kill switch / emergency stop path missing |
| **Rationale** | Safety-critical designs must provide a hardware kill-switch or emergency stop input. |
| **Detects** | Absence of `kill_switch`, `emergency_stop`, `estop`, `e_stop`, `shutdown`, or `abort` when actuator outputs exist |

#### CG010 — No Assertions

| Field | Value |
|-------|-------|
| **Severity** | `medium` |
| **Description** | No assertions found in the design |
| **Rationale** | Assertions are essential for verification; their absence makes formal checks impossible. |
| **Detects** | No `assert`, `cover`, or `assume` keywords in the source (including comments) |

#### CG011 — No Testbench

| Field | Value |
|-------|-------|
| **Severity** | `medium` |
| **Description** | No testbench companion file detected |
| **Rationale** | Without a testbench the design cannot be simulated or regression-tested. |
| **Detects** | Checks for `design_tb.v`, `tb_design.v`, `tb.v`, `tb.sv` in the same directory, or if the file itself looks like a testbench |

#### CG012 — No Replay Command

| Field | Value |
|-------|-------|
| **Severity** | `low` |
| **Description** | No replay command — design cannot be deterministically re-verified |
| **Rationale** | Replay commands enable deterministic re-verification of results. |
| **Detects** | Always reported during scan; resolved by running with `--evidence` |

#### CG013 — Unsafe Bypass Path

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Description** | Unsafe bypass path — potential shortcut around safety logic |
| **Rationale** | Any path that bypasses safety gates is a critical violation. |
| **Detects** | Actuator signals driven by complex expressions that do not contain any verification gate signals |

#### CG014 — Safety Gate Present

| Field | Value |
|-------|-------|
| **Severity** | `info` |
| **Description** | Safety gate present — output properly gated by verification signals |
| **Rationale** | The output is gated by verifier_ok / policy_ok / kill_switch logic. |
| **Detects** | Actuator signal expressions containing two or more verification gate signals |

### Rules Checked During Scan

The scan function evaluates rules in this order:

1. **Module-level checks** (operate on parsed `ModuleInfo`):
   - CG001, CG002, CG003, CG004, CG005, CG006, CG007, CG008, CG009, CG010, CG013, CG014

2. **File-level checks** (require filesystem access):
   - CG011 (testbench detection)

Note: CG012 is defined in the rule catalogue but is currently informational
and always reported as a finding during scan.
