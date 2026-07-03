# ChipGate Examples

Comprehensive examples demonstrating how to use ChipGate to scan Verilog/SystemVerilog
designs, interpret results, and integrate with optional external tools.

---

## Table of Contents

- [Basic Scanning](#basic-scanning)
- [Example 1: Unsafe Actuator Design](#example-1-unsafe-actuator-design)
- [Example 2: Safe DTL Gate Design](#example-2-safe-dtl-gate-design)
- [Example 3: DTL Gate FSM Design](#example-3-dtl-gate-fsm-design)
- [JSON Output](#json-output)
- [Evidence Pack Generation](#evidence-pack-generation)
- [Safety Analysis Output](#safety-analysis-output)
- [Lint Integration (Verilator)](#lint-integration-verilator)
- [Formal Verification Readiness Checks](#formal-verification-readiness-checks)
- [Replay Script Generation](#replay-script-generation)
- [The DTL Gate Chain Concept](#the-dtl-gate-chain-concept)
- [Running the Demo](#running-the-demo)

---

## Basic Scanning

Scan a single Verilog file with human-readable output:

```bash
python -m chipgate scan path/to/design.v
```

Scan with structured JSON output:

```bash
python -m chipgate scan path/to/design.v --json
```

Scan with all optional analyses enabled:

```bash
python -m chipgate scan path/to/design.v --json --evidence --lint --formal --safety
```

Run external lint only:

```bash
python -m chipgate lint path/to/design.v
```

List all available rules:

```bash
python -m chipgate --list-rules
```

Show version:

```bash
python -m chipgate --version
```

---

## Example 1: Unsafe Actuator Design

This example demonstrates an **intentionally unsafe** design where AI output is
directly connected to an actuator with no safety gates.

### Source (`unsafe_actuator.v`)

```verilog
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

### Scan Command

```bash
python -m chipgate scan examples/unsafe_actuator.v
```

### Expected Output

```
ChipGate Scan: examples/unsafe_actuator.v
Module: unsafe_actuator

  [FAIL] RTL_SCAN_FAIL
  [FAIL] UNGATED_OUTPUT
  [FAIL] UNSAFE_BYPASS_PATH
  [FAIL] ASSERTION_MISSING
  [FAIL] FORMAL_NOT_READY
  [INFO] NEEDS_HUMAN_REVIEW

Findings:
  [CRITICAL] CG001: Missing reset signal — no 'rst' or 'reset' found
  [CRITICAL] CG006: Hardcoded bypass — 'actuator_enable' directly assigned from 'ai_output' (line 6)
  [CRITICAL] CG007: Actuator 'actuator_enable' not gated by verifier_ok (line 6)
  [CRITICAL] CG008: Actuator 'actuator_enable' not gated by policy_ok (line 6)
  [CRITICAL] CG009: Kill switch / emergency stop path missing
  [CRITICAL] CG013: Unsafe bypass path — 'actuator_enable' driven by expression without verification gates (line 6)
  [MEDIUM] CG010: No assertions found in the design
  [MEDIUM] CG011: No testbench companion file detected for 'unsafe_actuator'

Risky signals: actuator_enable

Required gates: verifier_ok, policy_ok, kill_switch, sensor_ok, timeout

Replay: python -m chipgate scan examples/unsafe_actuator.v --json
Hash: a1b2c3d4e5f6...

ChipGate checks RTL structure and verification-gated safety patterns.
It does not guarantee hardware correctness, silicon readiness, physical safety,
regulatory conformance or experimental validity.
```

### Why It Fails

| Rule | Reason |
|------|--------|
| CG001 | No `rst` or `reset` signal exists in the sensitivity list |
| CG006 | `ai_output` is passed directly to `actuator_enable` with no gates |
| CG007 | No `verifier_ok` gate on the actuator output |
| CG008 | No `policy_ok` gate on the actuator output |
| CG009 | No `kill_switch` or emergency stop input exists |
| CG013 | The bypass path skips all verification gates |
| CG010 | No `assert`, `cover`, or `assume` statements found |
| CG011 | No companion testbench file detected |

---

## Example 2: Safe DTL Gate Design

This example demonstrates a properly gated design that follows the
DTL (Decision-Trust-Logic) safety pattern.

### Source (`safe_dtl_gate.v`)

```verilog
module safe_dtl_gate (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
        end
    end
endmodule
```

### Scan Command

```bash
python -m chipgate scan examples/safe_dtl_gate.v
```

### Expected Output

```
ChipGate Scan: examples/safe_dtl_gate.v
Module: safe_dtl_gate

  [PASS] RTL_SCAN_PASS
  [PASS] SAFETY_GATE_PRESENT
  [FAIL] ASSERTION_MISSING
  [FAIL] FORMAL_NOT_READY
  [INFO] NEEDS_HUMAN_REVIEW

Findings:
  [INFO] CG014: Safety gate present — 'actuator_enable' gated by [verifier_ok, policy_ok, kill_switch] (line 9)
  [MEDIUM] CG010: No assertions found in the design
  [MEDIUM] CG011: No testbench companion file detected for 'safe_dtl_gate'

Required gates: verifier_ok, policy_ok, kill_switch, sensor_ok, timeout

Replay: python -m chipgate scan examples/safe_dtl_gate.v --json
Hash: f6e5d4c3b2a1...

ChipGate checks RTL structure and verification-gated safety patterns.
It does not guarantee hardware correctness, silicon readiness, physical safety,
regulatory conformance or experimental validity.
```

### Why It Passes

The design passes RTL_SCAN_PASS because there are **no critical findings**:
- Has a reset signal (`rst_n`) in the sensitivity list — **CG001 clear**
- Actuator is gated by `verifier_ok && policy_ok && !kill_switch` — **CG006/007/008/013 clear**
- Kill switch is declared and used — **CG009 clear**
- Safety gates are detected — **CG014 reports gate presence**

The remaining MEDIUM findings (no assertions, no testbench) are informational
and do not cause a scan failure.

---

## Example 3: DTL Gate FSM Design

This example uses a full finite state machine to enforce the DTL gate chain,
including sensor validation and timeout protection.

### Source (`dtl_gate_fsm.v`)

```verilog
module dtl_gate_fsm (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        ai_output,
    input  wire        verifier_ok,
    input  wire        policy_ok,
    input  wire        sensor_ok,
    input  wire        timeout,
    input  wire        kill_switch,
    output reg         actuator_enable,
    output reg  [2:0]  current_state
);
    // States: IDLE, PROPOSED, VERIFYING, APPROVED, BLOCKED, FAILSAFE
    // ... (full FSM implementation)
endmodule
```

### Scan Command

```bash
python -m chipgate scan examples/dtl_gate_fsm.v
```

### Expected Output

```
ChipGate Scan: examples/dtl_gate_fsm.v
Module: dtl_gate_fsm

  [PASS] RTL_SCAN_PASS
  [PASS] SAFETY_GATE_PRESENT
  [FAIL] ASSERTION_MISSING
  [FAIL] FORMAL_NOT_READY
  [INFO] NEEDS_HUMAN_REVIEW

Findings:
  [INFO] CG014: Safety gate present — 'actuator_enable' gated by
         [verifier_ok, policy_ok, sensor_ok, timeout, kill_switch] (line 71)
  [MEDIUM] CG010: No assertions found in the design
  [MEDIUM] CG011: No testbench companion file detected for 'dtl_gate_fsm'

Required gates: verifier_ok, policy_ok, kill_switch, sensor_ok, timeout

Replay: python -m chipgate scan examples/dtl_gate_fsm.v --json
Hash: 7a8b9c0d1e2f...

ChipGate checks RTL structure and verification-gated safety patterns.
It does not guarantee hardware correctness, silicon readiness, physical safety,
regulatory conformance or experimental validity.
```

### Why the FSM Design Is Stronger

| Feature | Simple DTL Gate | FSM Variant |
|---------|----------------|-------------|
| Reset | Yes | Yes |
| `verifier_ok` gate | Yes | Yes |
| `policy_ok` gate | Yes | Yes |
| `sensor_ok` gate | No | Yes |
| Timeout protection | No | Yes |
| Kill switch | Yes | Yes |
| Failsafe state | No (implicit) | Yes (`FAILSAFE` state) |
| State diagnostics | No | Yes (`current_state` output) |

---

## JSON Output

Use `--json` to produce machine-readable structured output:

```bash
python -m chipgate scan examples/safe_dtl_gate.v --json
```

### Example JSON (safe_dtl_gate.v)

```json
{
  "certificate_hash": "f6e5d4c3b2a1...",
  "file": "examples/safe_dtl_gate.v",
  "findings": [
    {
      "description": "No assertions found in the design",
      "detail": "Assertions are essential for verification; their absence makes formal checks impossible.",
      "line_number": 0,
      "rule_id": "CG010",
      "severity": "medium",
      "signal_name": ""
    },
    {
      "description": "No testbench companion file detected for 'safe_dtl_gate'",
      "detail": "Without a testbench the design cannot be simulated or regression-tested.",
      "line_number": 0,
      "rule_id": "CG011",
      "severity": "medium",
      "signal_name": ""
    },
    {
      "description": "Safety gate present — 'actuator_enable' gated by [verifier_ok, policy_ok, kill_switch]",
      "detail": "The output is gated by verification signals.",
      "line_number": 9,
      "rule_id": "CG014",
      "severity": "info",
      "signal_name": "actuator_enable"
    }
  ],
  "module_name": "safe_dtl_gate",
  "public_wording": "ChipGate checks RTL structure and verification-gated safety patterns. It does not guarantee hardware correctness, silicon readiness, physical safety, regulatory conformance or experimental validity.",
  "replay_command": "python -m chipgate scan examples/safe_dtl_gate.v --json",
  "required_gates": ["verifier_ok", "policy_ok", "kill_switch", "sensor_ok", "timeout"],
  "risky_signals": [],
  "rules_checked": [
    "CG001", "CG002", "CG003", "CG004", "CG005",
    "CG006", "CG007", "CG008", "CG009", "CG010",
    "CG013", "CG014", "CG011"
  ],
  "statuses": [
    "RTL_SCAN_PASS", "SAFETY_GATE_PRESENT",
    "ASSERTION_MISSING", "FORMAL_NOT_READY", "NEEDS_HUMAN_REVIEW"
  ]
}
```

### Example JSON (unsafe_actuator.v)

```json
{
  "certificate_hash": "a1b2c3d4e5f6...",
  "file": "examples/unsafe_actuator.v",
  "findings": [
    {
      "description": "Missing reset signal — no 'rst' or 'reset' found in sensitivity list or always block",
      "detail": "Safety-critical designs must have a reset to reach a known state on power-up.",
      "line_number": 0,
      "rule_id": "CG001",
      "severity": "critical",
      "signal_name": ""
    },
    {
      "description": "Hardcoded bypass — 'actuator_enable' directly assigned from 'ai_output'",
      "detail": "A direct bypass skips all verification gates and can cause unsafe actuation.",
      "line_number": 6,
      "rule_id": "CG006",
      "severity": "critical",
      "signal_name": "actuator_enable"
    },
    {
      "description": "Actuator 'actuator_enable' not gated by verifier_ok",
      "detail": "DTL requires that safety-critical outputs pass through a verifier gate before actuation.",
      "line_number": 6,
      "rule_id": "CG007",
      "severity": "critical",
      "signal_name": "actuator_enable"
    },
    {
      "description": "Actuator 'actuator_enable' not gated by policy_ok",
      "detail": "DTL requires policy compliance checks before enabling physical actuation.",
      "line_number": 6,
      "rule_id": "CG008",
      "severity": "critical",
      "signal_name": "actuator_enable"
    },
    {
      "description": "Kill switch / emergency stop path missing for actuator output(s)",
      "detail": "Safety-critical designs must provide a hardware kill-switch or emergency stop input.",
      "line_number": 0,
      "rule_id": "CG009",
      "severity": "critical",
      "signal_name": ""
    },
    {
      "description": "No assertions found in the design",
      "detail": "Assertions are essential for verification; their absence makes formal checks impossible.",
      "line_number": 0,
      "rule_id": "CG010",
      "severity": "medium",
      "signal_name": ""
    },
    {
      "description": "No testbench companion file detected for 'unsafe_actuator'",
      "detail": "Without a testbench the design cannot be simulated or regression-tested.",
      "line_number": 0,
      "rule_id": "CG011",
      "severity": "medium",
      "signal_name": ""
    },
    {
      "description": "Unsafe bypass path — 'actuator_enable' driven by expression without verification gates",
      "detail": "Any path that bypasses safety gates is a critical violation.",
      "line_number": 6,
      "rule_id": "CG013",
      "severity": "critical",
      "signal_name": "actuator_enable"
    }
  ],
  "module_name": "unsafe_actuator",
  "public_wording": "ChipGate checks RTL structure and verification-gated safety patterns. It does not guarantee hardware correctness, silicon readiness, physical safety, regulatory conformance or experimental validity.",
  "replay_command": "python -m chipgate scan examples/unsafe_actuator.v --json",
  "required_gates": ["verifier_ok", "policy_ok", "kill_switch", "sensor_ok", "timeout"],
  "risky_signals": ["actuator_enable"],
  "rules_checked": [
    "CG001", "CG002", "CG003", "CG004", "CG005",
    "CG006", "CG007", "CG008", "CG009", "CG010",
    "CG013", "CG014", "CG011"
  ],
  "statuses": [
    "RTL_SCAN_FAIL", "UNGATED_OUTPUT", "UNSAFE_BYPASS_PATH",
    "ASSERTION_MISSING", "FORMAL_NOT_READY", "NEEDS_HUMAN_REVIEW"
  ]
}
```

---

## Evidence Pack Generation

Generate a comprehensive, reproducible evidence pack containing all scan
results plus optional lint, formal, and safety analysis data:

```bash
python -m chipgate scan examples/safe_dtl_gate.v --evidence --json --lint --formal --safety
```

This creates a file `examples/safe_dtl_gate.evidence.json` with the following
additional fields beyond the standard scan result:

```json
{
  "chipgate_version": "0.1.0",
  "timestamp_utc": "2025-01-15T10:30:00+00:00",
  "evidence_pack_hash": "sha256:abc123...",
  "...": "(all standard ScanResult fields)",
  "lint": {
    "tool": "verilator",
    "available": false,
    "passed": false,
    "errors": ["Verilator not installed — skipping external lint."],
    "warnings": [],
    "command": ""
  },
  "formal": {
    "ready": false,
    "assertion_count": 0,
    "issues": ["No assertions found — formal verification requires at least one assertion property."],
    "sby_config": "",
    "tool_available": false
  },
  "safety_analysis": {
    "safety_score": 0.7,
    "gate_chain_complete": true,
    "critical_gaps": [],
    "patterns": [
      {
        "pattern_name": "DTL Gate Chain",
        "present": true,
        "description": "The DTL gate chain requires verifier_ok, policy_ok, and kill_switch to gate all safety-critical outputs.",
        "signals_involved": ["verifier_ok", "policy_ok", "kill_switch"]
      },
      {
        "pattern_name": "Sensor Validation",
        "present": false,
        "description": "Sensor validation ensures physical state is verified before actuation.",
        "signals_involved": []
      },
      {
        "pattern_name": "Timeout Protection",
        "present": false,
        "description": "Timeout protection prevents indefinite hanging in unsafe states.",
        "signals_involved": []
      },
      {
        "pattern_name": "Failsafe FSM",
        "present": false,
        "description": "A failsafe FSM ensures the design can transition to a known-safe state.",
        "signals_involved": []
      },
      {
        "pattern_name": "Kill Switch Coverage",
        "present": true,
        "description": "Kill switch must be declared AND used to gate safety-critical outputs.",
        "signals_involved": ["kill_switch"]
      }
    ]
  }
}
```

The evidence pack hash is a SHA-256 of the entire pack content (excluding the
hash field itself), providing tamper detection for the verification record.

---

## Safety Analysis Output

The safety analysis evaluates five key patterns and produces a composite safety
score from 0.0 to 1.0:

```bash
python -m chipgate scan examples/dtl_gate_fsm.v --safety --json
```

### Scoring Breakdown

| Pattern | Weight | Maximum Score |
|---------|--------|---------------|
| DTL Gate Chain | 0.40 | Required gates present |
| Sensor Validation | 0.15 | `sensor_ok` signal found |
| Timeout Protection | 0.15 | `timeout` / `watchdog` signal found |
| Failsafe FSM | 0.15 | IDLE/FAILSAFE state machine detected |
| Kill Switch Coverage | 0.15 | `kill_switch` declared and used in logic |

### Example Safety Score for `dtl_gate_fsm.v`

| Pattern | Present | Score |
|---------|---------|-------|
| DTL Gate Chain | Yes | +0.40 |
| Sensor Validation | Yes | +0.15 |
| Timeout Protection | Yes | +0.15 |
| Failsafe FSM | Yes | +0.15 |
| Kill Switch Coverage | Yes | +0.15 |
| **Total** | | **1.00** |

### Example Safety Score for `safe_dtl_gate.v`

| Pattern | Present | Score |
|---------|---------|-------|
| DTL Gate Chain | Yes | +0.40 |
| Sensor Validation | No | +0.00 |
| Timeout Protection | No | +0.00 |
| Failsafe FSM | No | +0.00 |
| Kill Switch Coverage | Yes | +0.15 |
| **Total** | | **0.55** |

A `gate_chain_complete` value of `true` is reported when the DTL gate chain
and kill switch are both present and no critical gaps are detected.

---

## Lint Integration (Verilator)

When Verilator is installed on the system, ChipGate can invoke it for external
lint analysis:

```bash
python -m chipgate scan examples/safe_dtl_gate.v --lint --json
```

### When Verilator Is Available

```json
{
  "lint": {
    "tool": "verilator",
    "available": true,
    "passed": true,
    "warnings": [],
    "errors": [],
    "command": "verilator --lint-only -Wall examples/safe_dtl_gate.v"
  }
}
```

### When Verilator Is Not Available

```json
{
  "lint": {
    "tool": "verilator",
    "available": false,
    "passed": false,
    "errors": ["Verilator not installed — skipping external lint. Run internal scan instead."],
    "warnings": [],
    "command": ""
  }
}
```

The statuses array will include `RTL_LINT_PASS` or `RTL_LINT_FAIL` accordingly.

### Installing Verilator

```bash
# Ubuntu/Debian
sudo apt install verilator

# macOS (Homebrew)
brew install verilator

# From source
git clone https://github.com/verilator/verilator.git
cd verilator && autoconf && ./configure && make && make install
```

---

## Formal Verification Readiness Checks

ChipGate checks whether a design is structurally ready for formal verification
using SymbiYosys (SBY) on top of Yosys:

```bash
python -m chipgate scan examples/dtl_gate_fsm.v --formal --json
```

### Formal Readiness Criteria

1. **Assertions exist** — The design must contain at least one `assert`, `cover`, or `assume` statement
2. **No problematic constructs** — Checks for `$random`, `$display`, and delay constructs
3. **Tool availability** — Reports whether Yosys and SBY are installed

### When Design Is Ready

```json
{
  "formal": {
    "ready": true,
    "assertion_count": 4,
    "issues": [],
    "sby_config": "[options]\nmode prove\ndepth 20\n\n[engines]\nsmtbmc\n\n[script]\nread_verilog dtl_gate_fsm.v\nprep -top dtl_gate_fsm\n\n[files]\ndtl_gate_fsm.v\n",
    "tool_available": false
  }
}
```

### When Design Is Not Ready

```json
{
  "formal": {
    "ready": false,
    "assertion_count": 0,
    "issues": [
      "No assertions found — formal verification requires at least one assertion property."
    ],
    "sby_config": "",
    "tool_available": false
  }
}
```

The generated `sby_config` field provides a ready-to-use SBY configuration
file that can be saved to `.sby` format and executed with:

```bash
sby my_design.sby
```

---

## Replay Script Generation

Every scan generates a deterministic replay command. The evidence pack
generation includes a full replay script:

```bash
python -m chipgate scan examples/safe_dtl_gate.v --evidence
```

### Generated Replay Script

```bash
#!/usr/bin/env bash
# ChipGate Replay Script
# Generated for: examples/safe_dtl_gate.v
# Module: safe_dtl_gate
# ChipGate version: 0.1.0
# Certificate hash: f6e5d4c3b2a1...
#
# ChipGate checks RTL structure and verification-gated safety patterns.
# It does not guarantee hardware correctness, silicon readiness, physical safety,
# regulatory conformance or experimental validity.

set -e

# Step 1: Re-run the core RTL safety scan
echo ">>> Step 1: Re-run the core RTL safety scan"
python -m chipgate scan examples/safe_dtl_gate.v
echo ""

# Step 2: Re-run scan with structured JSON output
echo ">>> Step 2: Re-run scan with structured JSON output"
python -m chipgate scan examples/safe_dtl_gate.v --json
echo ""

# Step 3: Re-run scan and generate evidence pack
echo ">>> Step 3: Re-run scan and generate evidence pack"
python -m chipgate scan examples/safe_dtl_gate.v --evidence
echo ""

# Step 4: Re-run with external lint (requires Verilator)
echo ">>> Step 4: Re-run with external lint (requires Verilator)"
python -m chipgate lint examples/safe_dtl_gate.v
echo ""

# Step 5: List all rules that were checked
echo ">>> Step 5: List all rules that were checked"
python -m chipgate --list-rules
echo ""
```

The `certificate_hash` in the replay script allows comparison with the original
scan to confirm the results are reproducible and unaltered.

---

## The DTL Gate Chain Concept

The DTL (Decision-Trust-Logic) gate chain is a hardware safety pattern that
enforces multiple verification checkpoints before any AI-proposed output can
reach a physical actuator.

### Gate Chain Diagram

```
    AI / proposed output
            |
    +-------v--------+
    |   policy_ok?   |   Policy compliance check
    +-------+--------+
            |
    +-------v--------+
    |  verifier_ok?  |   Independent verification of output
    +-------+--------+
            |
    +-------v--------+
    |   sensor_ok?   |   Physical sensor validation
    +-------+--------+
            |
    +-------v--------+
    |  timeout_ok?   |   Operation within time limit
    +-------+--------+
            |
    +-------v--------+
    |kill_switch clr?|   Emergency stop NOT activated
    +-------+--------+
            |
    +-------v--------+
    | actuator_enable|   ONLY enabled when ALL gates pass
    +----------------+
```

### Gate Descriptions

| Gate | Signal | Purpose |
|------|--------|---------|
| **Policy Check** | `policy_ok` | Output complies with defined safety policy rules |
| **Verifier** | `verifier_ok` | An independent verifier has approved the output |
| **Sensor** | `sensor_ok` | Physical sensors confirm the environment is safe |
| **Timeout** | `timeout_ok` | Operation completed within its allowed time limit |
| **Kill Switch** | `!kill_switch` | Hardware emergency stop is NOT activated |

### Boolean Logic

```
gate_chain_ok = verifier_ok & policy_ok & sensor_ok & timeout_ok & ~kill_switch
actuator_enable = ai_output & gate_chain_ok
```

On reset (`rst_n` deasserted), `actuator_enable` is forced to `0` (safe default).

### Implementation Targets

The DTL gate can be implemented in:

- **ASIC** — via OpenLane / OpenROAD synthesis flow
- **FPGA** — via Yosys / nextpnr place-and-route
- **Simulation** — via Verilator / cocotb testbenches
- **Formal verification** — via SymbiYosys (SBY) property checking

### Simple Gate vs. FSM Gate

**Simple combinational gate** (`safe_dtl_gate.v`):
- Uses a single `always` block with Boolean AND of all gate signals
- Suitable for basic gating where no sequencing is required
- Lower latency, simpler logic

**FSM-based gate** (`dtl_gate_fsm.v`):
- Uses a state machine: `IDLE -> PROPOSED -> VERIFYING -> APPROVED -> BLOCKED -> FAILSAFE`
- Each state has explicit transitions and conditions
- Provides `current_state` diagnostic output
- More robust against transient faults and timing violations
- Recommended for safety-critical applications

---

## Running the Demo

ChipGate includes an interactive demo that scans both the unsafe and safe
examples side by side:

```bash
python -m chipgate --demo
```

This command:

1. Displays the source of `unsafe_actuator.v` and scans it (expected: FAIL)
2. Displays the source of `safe_dtl_gate.v` and scans it (expected: PASS)
3. Shows the DTL gate chain diagram
4. Prints the public wording disclaimer
