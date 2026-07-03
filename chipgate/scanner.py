"""
ChipGate RTL scanner.

Parses Verilog/SystemVerilog files using regex-based analysis and runs all
registered safety and lint rules against the extracted design structure.
"""

import json
import re
import hashlib
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import statuses as st
from .rules import RULES, RULE_BY_ID, Rule, Severity


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class Port:
    name: str
    direction: str  # "input", "output", "inout"
    width: int = 1
    is_reg: bool = False
    is_wire: bool = True


@dataclass
class Assignment:
    target: str
    expression: str
    line_number: int = 0
    is_continuous: bool = True
    is_blocking: bool = True


@dataclass
class AlwaysBlock:
    sensitivity: str = ""
    body_lines: List[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0


@dataclass
class CaseBlock:
    expression: str = ""
    has_default: bool = False
    cases: List[str] = field(default_factory=list)
    start_line: int = 0


@dataclass
class ModuleInfo:
    name: str = ""
    ports: List[Port] = field(default_factory=list)
    assignments: List[Assignment] = field(default_factory=list)
    always_blocks: List[AlwaysBlock] = field(default_factory=list)
    case_blocks: List[CaseBlock] = field(default_factory=list)
    has_assertions: bool = False
    has_reset: bool = False
    has_kill_switch: bool = False
    raw_lines: List[str] = field(default_factory=list)
    file_path: str = ""


@dataclass
class Finding:
    rule_id: str
    severity: str
    description: str
    line_number: int = 0
    signal_name: str = ""
    detail: str = ""


@dataclass
class ScanResult:
    file: str = ""
    module_name: str = ""
    statuses: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    risky_signals: List[str] = field(default_factory=list)
    required_gates: List[str] = field(default_factory=list)
    rules_checked: List[str] = field(default_factory=list)
    public_wording: str = st.PUBLIC_WORDING
    replay_command: str = ""
    certificate_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "module_name": self.module_name,
            "statuses": self.statuses,
            "findings": [asdict(f) for f in self.findings],
            "risky_signals": self.risky_signals,
            "required_gates": self.required_gates,
            "rules_checked": self.rules_checked,
            "public_wording": self.public_wording,
            "replay_command": self.replay_command,
            "certificate_hash": self.certificate_hash,
        }


# ── Safety-critical signal patterns ──────────────────────────────────────────

SAFETY_OUTPUT_PATTERNS = re.compile(
    r"(actuator|motor|relay|valve|heater|laser|solenoid|pump|drive|enable|trigger|fire|deploy)",
    re.IGNORECASE,
)

VERIFICATION_GATE_SIGNALS = {"verifier_ok", "policy_ok", "kill_switch", "sensor_ok", "timeout"}

ACTUATOR_NAMES = {
    "actuator_enable", "actuator_cmd", "motor_enable", "relay_on",
    "valve_open", "heater_on", "laser_enable", "solenoid_on",
    "pump_enable", "drive_enable", "trigger_out", "fire_cmd", "deploy_cmd",
}


# ── Regex Patterns for Verilog Parsing ───────────────────────────────────────

RE_MODULE = re.compile(r"module\s+(\w+)\s*\#", re.IGNORECASE)
RE_MODULE_SIMPLE = re.compile(r"module\s+(\w+)\s*[;(]", re.IGNORECASE)
RE_INPUT = re.compile(r"input\s+(?:reg\s+)?(?:\[\d+:0\]\s+)?(\w+)", re.IGNORECASE)
RE_OUTPUT = re.compile(r"output\s+(?:reg\s+)?(?:\[\d+:0\]\s+)?(\w+)", re.IGNORECASE)
RE_OUTPUT_REG = re.compile(r"output\s+reg\s+(?:\[\d+:0\]\s+)?(\w+)", re.IGNORECASE)
RE_ASSIGN = re.compile(r"assign\s+(\w+)\s*=\s*(.+?)\s*;", re.IGNORECASE)
RE_NB_ASSIGN = re.compile(r"(\w+)\s*<=\s*(.+?)\s*;", re.IGNORECASE)
RE_NB_ASSIGN_FULL = re.compile(r"(\w+)\s*<=\s*(.+)\s*;", re.IGNORECASE)
RE_ALWAYS_SENS = re.compile(
    r"always\s*@\s*\((.*?)\)\s*begin", re.IGNORECASE
)
RE_CASE = re.compile(r"case\s*\((.*?)\)", re.IGNORECASE)
RE_DEFAULT = re.compile(r"\bdefault\s*:", re.IGNORECASE)
RE_ASSERT = re.compile(
    r"\b(assert|cover|assume|restrict)\b", re.IGNORECASE
)
RE_ENDMODULE = re.compile(r"endmodule", re.IGNORECASE)
RE_COMMENT_LINE = re.compile(r"//.*$", re.MULTILINE)
RE_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
RE_KILL_SWITCH = re.compile(
    r"\b(kill_switch|emergency_stop|estop|e_stop|shutdown|abort)\b", re.IGNORECASE
)
RE_RESET = re.compile(
    r"\b(rst|reset|reset_n|rst_n|areset|sreset)\b", re.IGNORECASE
)


# ── Parsing ──────────────────────────────────────────────────────────────────

def strip_comments(text: str) -> str:
    """Remove single-line and block comments from Verilog source."""
    text = RE_COMMENT_BLOCK.sub("", text)
    text = RE_COMMENT_LINE.sub("", text)
    return text


def parse_verilog(file_path: str) -> ModuleInfo:
    """Parse a Verilog file and extract module structure."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    raw = path.read_text(encoding="utf-8", errors="replace")
    stripped = strip_comments(raw)
    lines = stripped.splitlines()

    info = ModuleInfo(raw_lines=lines, file_path=str(path.resolve()))

    # Detect module name
    for line in lines:
        m = RE_MODULE.match(line.strip()) or RE_MODULE_SIMPLE.match(line.strip())
        if m:
            info.name = m.group(1)
            break

    # Detect ports
    for line in lines:
        stripped_line = line.strip()
        for m in RE_INPUT.finditer(stripped_line):
            info.ports.append(Port(name=m.group(1), direction="input"))
        for m in RE_OUTPUT.finditer(stripped_line):
            info.ports.append(
                Port(name=m.group(1), direction="output", is_reg=False)
            )
        for m in RE_OUTPUT_REG.finditer(stripped_line):
            for p in info.ports:
                if p.name == m.group(1):
                    p.is_reg = True
                    p.is_wire = False
                    break

    # Detect assignments (continuous)
    for i, line in enumerate(lines, 1):
        m = RE_ASSIGN.match(line.strip())
        if m:
            info.assignments.append(
                Assignment(
                    target=m.group(1),
                    expression=m.group(2).strip(),
                    line_number=i,
                    is_continuous=True,
                )
            )

    # Detect non-blocking assignments anywhere in the file
    # Use search (not match) because assignments can appear after if/else on same line
    for i, line in enumerate(lines, 1):
        m = RE_NB_ASSIGN_FULL.search(line)
        if m:
            # Check if this target is a declared output
            is_output = any(p.name == m.group(1) for p in info.ports)
            if is_output:
                info.assignments.append(
                    Assignment(
                        target=m.group(1),
                        expression=m.group(2).strip(),
                        line_number=i,
                        is_continuous=False,
                        is_blocking=False,
                    )
                )

    # Detect always blocks
    in_always = False
    current_always = AlwaysBlock()
    for i, line in enumerate(lines, 1):
        m = RE_ALWAYS_SENS.match(line.strip())
        if m:
            in_always = True
            current_always = AlwaysBlock(sensitivity=m.group(1), start_line=i)
            continue
        if in_always:
            if re.match(r"^\s*end\s*$", line.strip(), re.IGNORECASE):
                current_always.end_line = i
                info.always_blocks.append(current_always)
                in_always = False
                current_always = AlwaysBlock()
            else:
                current_always.body_lines.append(line.strip())

    # Detect case blocks and defaults
    for i, line in enumerate(lines, 1):
        m = RE_CASE.match(line.strip())
        if m:
            case = CaseBlock(expression=m.group(1), start_line=i)
            # Scan forward for default within this case block
            for j in range(i, min(i + 50, len(lines) + 1)):
                if RE_DEFAULT.search(lines[j - 1]):
                    case.has_default = True
                    break
                if re.match(r"^\s*endcase", lines[j - 1], re.IGNORECASE):
                    break
            info.case_blocks.append(case)

    # Detect assertions
    for line in lines:
        if RE_ASSERT.search(line):
            info.has_assertions = True
            break

    # Detect kill switch
    for line in lines:
        if RE_KILL_SWITCH.search(line):
            info.has_kill_switch = True
            break
        for p in info.ports:
            if RE_KILL_SWITCH.search(p.name):
                info.has_kill_switch = True
                break
        if info.has_kill_switch:
            break

    # Detect reset
    for line in lines:
        if RE_RESET.search(line):
            info.has_reset = True
            break
        for p in info.ports:
            if RE_RESET.search(p.name):
                info.has_reset = True
                break
        if info.has_reset:
            break

    return info


# ── Check Functions ──────────────────────────────────────────────────────────

def check_missing_reset(info: ModuleInfo) -> Optional[Finding]:
    """CG001: Missing reset signal."""
    if not info.has_reset:
        return Finding(
            rule_id="CG001",
            severity="critical",
            description="Missing reset signal — no 'rst' or 'reset' found in sensitivity list or always block",
            detail="Safety-critical designs must have a reset to reach a known state on power-up.",
        )
    return None


def check_missing_default(info: ModuleInfo) -> Optional[Finding]:
    """CG002: Missing default case."""
    for cb in info.case_blocks:
        if not cb.has_default:
            return Finding(
                rule_id="CG002",
                severity="high",
                description=f"Missing default case in case statement for '{cb.expression}'",
                line_number=cb.start_line,
                detail="Missing defaults can cause latches or undefined state in synthesis.",
            )
    return None


def check_latch_inference(info: ModuleInfo) -> Optional[Finding]:
    """CG003: Possible latch inference."""
    for ab in info.always_blocks:
        # Combinational always block (no posedge/negedge)
        if "posedge" not in ab.sensitivity.lower() and "negedge" not in ab.sensitivity.lower():
            # Check if all outputs driven in this block are always assigned
            targets_in_block = set()
            for line in ab.body_lines:
                m = RE_NB_ASSIGN.match(line.strip()) or re.match(
                    r"(\w+)\s*=\s*(.+?)\s*;", line.strip()
                )
                if m:
                    targets_in_block.add(m.group(1))
            # Check for if/else without else
            body_text = "\n".join(ab.body_lines)
            if re.search(r"\bif\b", body_text, re.IGNORECASE) and not re.search(r"\belse\b", body_text, re.IGNORECASE):
                return Finding(
                    rule_id="CG003",
                    severity="high",
                    description="Possible latch inference — incomplete if/else in combinational block",
                    line_number=ab.start_line,
                    detail="Latches in RTL often indicate unintended behaviour and can cause timing issues.",
                )
    return None


def check_undriven_outputs(info: ModuleInfo) -> Optional[Finding]:
    """CG004: Undriven output."""
    output_names = {p.name for p in info.ports if p.direction == "output"}
    driven_targets = {a.target for a in info.assignments}

    # Also check always blocks for blocking assignments
    for ab in info.always_blocks:
        for line in ab.body_lines:
            m = re.match(r"(\w+)\s*<=?\s*(.+?)\s*;", line.strip())
            if m:
                driven_targets.add(m.group(1))

    undriven = output_names - driven_targets
    if undriven:
        return Finding(
            rule_id="CG004",
            severity="critical",
            description=f"Undriven output(s): {', '.join(sorted(undriven))}",
            detail="Undriven outputs float to undefined values, which can cause unpredictable hardware behaviour.",
            signal_name=", ".join(sorted(undriven)),
        )
    return None


def check_unused_inputs(info: ModuleInfo) -> Optional[Finding]:
    """CG005: Unused input."""
    input_names = {p.name for p in info.ports if p.direction == "input"}
    full_text = "\n".join(info.raw_lines)
    # Strip port declarations to find usage elsewhere
    usage_text = RE_COMMENT_LINE.sub("", full_text)
    unused = []
    for inp in input_names:
        # Count occurrences — more than just the declaration line
        pattern = re.compile(rf"\b{re.escape(inp)}\b")
        matches = pattern.findall(usage_text)
        if len(matches) <= 1:  # Only the declaration itself
            unused.append(inp)
    if unused:
        return Finding(
            rule_id="CG005",
            severity="low",
            description=f"Unused input(s): {', '.join(sorted(unused))}",
            detail="Unused inputs may indicate a design error or incomplete connection.",
            signal_name=", ".join(sorted(unused)),
        )
    return None


def _is_actuator_signal(name: str) -> bool:
    """Check if a signal name looks like an actuator/safety output."""
    name_lower = name.lower()
    for pattern in ACTUATOR_NAMES:
        if pattern in name_lower:
            return True
    if SAFETY_OUTPUT_PATTERNS.search(name):
        return True
    return False


def _has_gate_signals(expression: str) -> Tuple[bool, List[str]]:
    """Check if an expression contains verification gate signals."""
    found = []
    expr_lower = expression.lower()
    for gate in VERIFICATION_GATE_SIGNALS:
        if re.search(rf"\b{re.escape(gate)}\b", expr_lower):
            found.append(gate)
    return len(found) > 0, found


def _is_constant(expression: str) -> bool:
    """Check if an expression is a constant value (e.g. 1'b0, 0, 1)."""
    expr = expression.strip().rstrip(";").strip()
    return bool(re.match(r"^(1'[bB][01]+|\d+'[bBhH][0-9a-fA-F_]+|\d+|0)$", expr))


def _has_bypass(expression: str) -> bool:
    """Check if an expression is a trivial pass-through (bypass)."""
    expr = expression.strip().rstrip(";").strip()
    # Constants are not bypasses
    if _is_constant(expression):
        return False
    # Just a single signal name = direct bypass
    if re.match(r"^\w+$", expr):
        return True
    # Only negation of single signal
    if re.match(r"^!\w+$", expr):
        return True
    return False


def _get_actuator_assignments(info: ModuleInfo) -> dict:
    """Group all assignments to actuator signals by target name."""
    groups = {}
    for a in info.assignments:
        if _is_actuator_signal(a.target):
            groups.setdefault(a.target, []).append(a)
    return groups


def _signal_has_gate(actuator_assignments: list, gate_name: str) -> bool:
    """Check if any non-constant assignment to a signal includes the given gate."""
    for a in actuator_assignments:
        if _is_constant(a.expression):
            continue
        _, gates = _has_gate_signals(a.expression)
        if gate_name in gates:
            return True
    return False


def _signal_has_any_gate(actuator_assignments: list) -> bool:
    """Check if any non-constant assignment has any verification gates."""
    for a in actuator_assignments:
        if _is_constant(a.expression):
            continue
        has_gates, _ = _has_gate_signals(a.expression)
        if has_gates:
            return True
    return False


def check_hardcoded_bypass(info: ModuleInfo) -> Optional[Finding]:
    """CG006: Hardcoded bypass — direct assignment from input to actuator."""
    groups = _get_actuator_assignments(info)
    for signal, assignments in groups.items():
        # Check each non-constant assignment individually
        # A bypass in ANY path is unsafe, even if other paths are gated
        for a in assignments:
            if _is_constant(a.expression):
                continue
            if _has_bypass(a.expression):
                return Finding(
                    rule_id="CG006",
                    severity="critical",
                    description=f"Hardcoded bypass — '{signal}' directly assigned from '{a.expression.strip()}'",
                    line_number=a.line_number,
                    detail="A direct bypass skips all verification gates and can cause unsafe actuation.",
                    signal_name=signal,
                )
    return None


def check_verifier_ok_gating(info: ModuleInfo) -> Optional[Finding]:
    """CG007: Actuator output not gated by verifier_ok."""
    groups = _get_actuator_assignments(info)
    for signal, assignments in groups.items():
        # Check ALL non-constant assignments — each path must have the gate
        for a in assignments:
            if _is_constant(a.expression):
                continue
            _, gates = _has_gate_signals(a.expression)
            if "verifier_ok" not in gates:
                return Finding(
                    rule_id="CG007",
                    severity="critical",
                    description=f"Actuator '{signal}' not gated by verifier_ok",
                    line_number=a.line_number,
                    detail="DTL requires that safety-critical outputs pass through a verifier gate before actuation.",
                    signal_name=signal,
                )
    return None


def check_policy_ok_gating(info: ModuleInfo) -> Optional[Finding]:
    """CG008: Actuator output not gated by policy_ok."""
    groups = _get_actuator_assignments(info)
    for signal, assignments in groups.items():
        # Check ALL non-constant assignments
        for a in assignments:
            if _is_constant(a.expression):
                continue
            _, gates = _has_gate_signals(a.expression)
            if "policy_ok" not in gates:
                return Finding(
                    rule_id="CG008",
                    severity="critical",
                    description=f"Actuator '{signal}' not gated by policy_ok",
                    line_number=a.line_number,
                    detail="DTL requires policy compliance checks before enabling physical actuation.",
                    signal_name=signal,
                )
    return None


def check_kill_switch(info: ModuleInfo) -> Optional[Finding]:
    """CG009: Kill switch / emergency stop path missing."""
    has_actuator = any(_is_actuator_signal(a.target) for a in info.assignments)
    if has_actuator and not info.has_kill_switch:
        return Finding(
            rule_id="CG009",
            severity="critical",
            description="Kill switch / emergency stop path missing for actuator output(s)",
            detail="Safety-critical designs must provide a hardware kill-switch or emergency stop input.",
        )
    return None


def check_assertions(info: ModuleInfo) -> Optional[Finding]:
    """CG010: No assertions found."""
    if not info.has_assertions:
        return Finding(
            rule_id="CG010",
            severity="medium",
            description="No assertions found in the design",
            detail="Assertions are essential for verification; their absence makes formal checks impossible.",
        )
    return None


def check_testbench(file_path: str) -> Optional[Finding]:
    """CG011: No testbench companion file detected."""
    path = Path(file_path)
    parent = path.parent
    stem = path.stem

    tb_candidates = [
        parent / f"{stem}_tb.v",
        parent / f"tb_{stem}.v",
        parent / f"{stem}_tb.sv",
        parent / f"tb_{stem}.sv",
        parent / "tb.sv",
        parent / "tb.v",
    ]
    for candidate in tb_candidates:
        if candidate.exists():
            return None

    # Also check if the file itself looks like a testbench
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if re.search(r"\b(initial\s*$|`timescale|module\s+tb_)", content, re.IGNORECASE | re.MULTILINE):
        return None

    return Finding(
        rule_id="CG011",
        severity="medium",
        description=f"No testbench companion file detected for '{stem}'",
        detail="Without a testbench the design cannot be simulated or regression-tested.",
    )


def check_replay_command(info: ModuleInfo) -> Optional[Finding]:
    """CG012: No replay command — design cannot be deterministically re-verified."""
    # This is always flagged at scan time; replay commands are generated by the evidence module
    return Finding(
        rule_id="CG012",
        severity="low",
        description="No replay command generated yet — run with --evidence to generate",
        detail="Replay commands enable deterministic re-verification of results.",
    )


def check_unsafe_bypass_path(info: ModuleInfo) -> Optional[Finding]:
    """CG013: Unsafe bypass path — potential shortcut around safety logic."""
    groups = _get_actuator_assignments(info)
    for signal, assignments in groups.items():
        # If any non-constant assignment has gates, skip
        if _signal_has_any_gate(assignments):
            continue
        for a in assignments:
            if _is_constant(a.expression):
                continue
            if not _has_bypass(a.expression):
                # Complex expression but no safety gates
                return Finding(
                    rule_id="CG013",
                    severity="critical",
                    description=f"Unsafe bypass path — '{signal}' driven by complex expression without verification gates",
                    line_number=a.line_number,
                    detail="Any path that bypasses safety gates is a critical violation.",
                    signal_name=signal,
                )
    return None


def check_safety_gate_present(info: ModuleInfo) -> Optional[Finding]:
    """CG014: Safety gate present — output properly gated."""
    groups = _get_actuator_assignments(info)
    for signal, assignments in groups.items():
        for a in assignments:
            if _is_constant(a.expression):
                continue
            has_gates, found = _has_gate_signals(a.expression)
            if has_gates and len(found) >= 2:
                gates_str = ", ".join(found)
                return Finding(
                    rule_id="CG014",
                    severity="info",
                    description=f"Safety gate present — '{signal}' gated by [{gates_str}]",
                    line_number=a.line_number,
                    detail="The output is gated by verification signals.",
                    signal_name=signal,
                )
    return None


# ── Check Registry ───────────────────────────────────────────────────────────

CHECKS = [
    ("CG001", check_missing_reset),
    ("CG002", check_missing_default),
    ("CG003", check_latch_inference),
    ("CG004", check_undriven_outputs),
    ("CG005", check_unused_inputs),
    ("CG006", check_hardcoded_bypass),
    ("CG007", check_verifier_ok_gating),
    ("CG008", check_policy_ok_gating),
    ("CG009", check_kill_switch),
    ("CG010", check_assertions),
    ("CG013", check_unsafe_bypass_path),
    ("CG014", check_safety_gate_present),
]

CHECKS_NEEDING_FILE = [
    ("CG011", check_testbench),
]


# ── Main Scan Function ───────────────────────────────────────────────────────

def scan_file(file_path: str, generate_replay: bool = True) -> ScanResult:
    """
    Scan a Verilog file and return a ScanResult with all findings.
    """
    info = parse_verilog(file_path)
    result = ScanResult(
        file=str(file_path),
        module_name=info.name,
        rules_checked=[],
        risky_signals=[],
        required_gates=list(VERIFICATION_GATE_SIGNALS),
        public_wording=st.PUBLIC_WORDING,
    )

    # Run module-level checks
    for rule_id, check_fn in CHECKS:
        finding = check_fn(info)
        result.rules_checked.append(rule_id)
        if finding:
            result.findings.append(finding)
            if finding.signal_name:
                result.risky_signals.append(finding.signal_name)

    # Run file-level checks
    for rule_id, check_fn in CHECKS_NEEDING_FILE:
        finding = check_fn(file_path)
        result.rules_checked.append(rule_id)
        if finding:
            result.findings.append(finding)

    # Determine statuses
    has_critical = any(f.severity == "critical" for f in result.findings)
    has_ungated = any(f.rule_id in ("CG006", "CG007", "CG008", "CG013") for f in result.findings)
    has_gate = any(f.rule_id == "CG014" for f in result.findings)
    has_no_assert = any(f.rule_id == "CG010" for f in result.findings)

    if has_ungated:
        result.statuses.append(st.UNGATED_OUTPUT)
    if has_gate:
        result.statuses.append(st.SAFETY_GATE_PRESENT)
    if has_no_assert:
        result.statuses.append(st.ASSERTION_MISSING)
    if any(f.rule_id == "CG013" for f in result.findings):
        result.statuses.append(st.UNSAFE_BYPASS_PATH)

    # Overall pass/fail
    if has_critical or has_ungated:
        result.statuses.insert(0, st.RTL_SCAN_FAIL)
    else:
        result.statuses.insert(0, st.RTL_SCAN_PASS)

    # Formal readiness — needs assertions and no critical findings
    if not has_no_assert and not has_critical:
        result.statuses.append(st.FORMAL_READY)
    else:
        result.statuses.append(st.FORMAL_NOT_READY)

    # Human review if any non-critical findings
    non_critical = [f for f in result.findings if f.severity in ("medium", "low")]
    if non_critical:
        result.statuses.append(st.NEEDS_HUMAN_REVIEW)

    # Replay command
    if generate_replay:
        result.replay_command = f"python -m chipgate scan {file_path} --json"

    # Certificate hash — SHA-256 of the finding set for reproducibility
    findings_json = json.dumps(
        [{"rule_id": f.rule_id, "signal": f.signal_name, "line": f.line_number} for f in result.findings],
        sort_keys=True,
    )
    result.certificate_hash = hashlib.sha256(findings_json.encode()).hexdigest()

    return result


def scan_directory(dir_path: str, recursive: bool = True) -> List[ScanResult]:
    """Scan all .v and .sv files in a directory."""
    path = Path(dir_path)
    pattern = "**/*.v" if recursive else "*.v"
    sv_pattern = "**/*.sv" if recursive else "*.sv"

    files = sorted(set(p for p in path.glob(pattern) if p.is_file()))
    files += sorted(set(p for p in path.glob(sv_pattern) if p.is_file()))

    results = []
    for f in files:
        try:
            results.append(scan_file(str(f)))
        except Exception as e:
            result = ScanResult(
                file=str(f),
                statuses=[st.RTL_SCAN_FAIL],
                findings=[Finding(
                    rule_id="PARSE_ERROR",
                    severity="critical",
                    description=f"Failed to parse file: {e}",
                )],
                rules_checked=[],
                required_gates=list(VERIFICATION_GATE_SIGNALS),
                public_wording=st.PUBLIC_WORDING,
            )
            results.append(result)

    return results