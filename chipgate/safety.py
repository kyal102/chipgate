"""
ChipGate safety-pattern checker.

Provides higher-level safety pattern analysis beyond individual rule checks.
This module analyses the overall safety architecture of a design.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .scanner import (
    ModuleInfo,
    parse_verilog,
    ACTUATOR_NAMES,
    SAFETY_OUTPUT_PATTERNS,
    VERIFICATION_GATE_SIGNALS,
    _is_actuator_signal,
    _has_gate_signals,
)


@dataclass
class SafetyPattern:
    """A detected safety pattern (or lack thereof)."""
    pattern_name: str
    present: bool
    description: str
    signals_involved: List[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class SafetyAnalysis:
    """Overall safety analysis of a design."""
    patterns: List[SafetyPattern] = field(default_factory=list)
    safety_score: float = 0.0  # 0.0 to 1.0
    gate_chain_complete: bool = False
    critical_gaps: List[str] = field(default_factory=list)


def analyze_safety_patterns(file_path: str) -> SafetyAnalysis:
    """
    Perform a comprehensive safety pattern analysis on a Verilog design.

    Checks for:
    1. DTL gate chain: verifier_ok && policy_ok && !kill_switch
    2. Sensor validation path
    3. Timeout protection
    4. Failsafe state machine
    5. Kill switch coverage
    """
    info = parse_verilog(file_path)
    patterns: List[SafetyPattern] = []
    critical_gaps: List[str] = []
    score = 0.0

    # ── Pattern 1: DTL Gate Chain ────────────────────────────────────────
    gate_chain = _check_dtl_gate_chain(info)
    patterns.append(gate_chain)
    if gate_chain.present:
        score += 0.4
    else:
        critical_gaps.append("DTL verification gate chain incomplete")

    # ── Pattern 2: Sensor Validation ─────────────────────────────────────
    sensor_pattern = _check_sensor_validation(info)
    patterns.append(sensor_pattern)
    if sensor_pattern.present:
        score += 0.15

    # ── Pattern 3: Timeout Protection ────────────────────────────────────
    timeout_pattern = _check_timeout_protection(info)
    patterns.append(timeout_pattern)
    if timeout_pattern.present:
        score += 0.15

    # ── Pattern 4: Failsafe State Machine ────────────────────────────────
    fsm_pattern = _check_failsafe_fsm(info)
    patterns.append(fsm_pattern)
    if fsm_pattern.present:
        score += 0.15

    # ── Pattern 5: Kill Switch Coverage ──────────────────────────────────
    kill_pattern = _check_kill_switch_coverage(info)
    patterns.append(kill_pattern)
    if kill_pattern.present:
        score += 0.15

    # Cap score
    score = min(score, 1.0)

    # Determine if gate chain is complete
    gate_chain_complete = (
        gate_chain.present
        and kill_pattern.present
        and not critical_gaps
    )

    return SafetyAnalysis(
        patterns=patterns,
        safety_score=score,
        gate_chain_complete=gate_chain_complete,
        critical_gaps=critical_gaps,
    )


def _check_dtl_gate_chain(info: ModuleInfo) -> SafetyPattern:
    """Check for the core DTL gate chain: ai_output && verifier_ok && policy_ok && !kill_switch."""
    required = ["verifier_ok", "policy_ok", "kill_switch"]
    found_signals = []

    for a in info.assignments:
        if _is_actuator_signal(a.target):
            _, gates = _has_gate_signals(a.expression)
            found_signals.extend(gates)

    # Also check always blocks
    full_text = "\n".join(
        line for ab in info.always_blocks for line in ab.body_lines
    )
    for gate in required:
        import re
        if re.search(rf"\b{re.escape(gate)}\b", full_text, re.IGNORECASE):
            if gate not in found_signals:
                found_signals.append(gate)

    present = all(g in found_signals for g in required)

    return SafetyPattern(
        pattern_name="DTL Gate Chain",
        present=present,
        description=(
            "The DTL gate chain requires verifier_ok, policy_ok, and kill_switch "
            "to gate all safety-critical outputs."
        ),
        signals_involved=found_signals,
        recommendation=(
            "Ensure actuator outputs use: "
            "output = ai_output && verifier_ok && policy_ok && !kill_switch"
        ),
    )


def _check_sensor_validation(info: ModuleInfo) -> SafetyPattern:
    """Check for sensor validation before actuation."""
    import re
    full_text = "\n".join(info.raw_lines)
    has_sensor = bool(re.search(r"\bsensor_ok\b|\bsensor_valid\b|\bsensor_check\b", full_text, re.IGNORECASE))

    return SafetyPattern(
        pattern_name="Sensor Validation",
        present=has_sensor,
        description="Sensor validation ensures physical state is verified before actuation.",
        signals_involved=["sensor_ok"] if has_sensor else [],
        recommendation="Add sensor_ok input and include it in the actuator gating logic.",
    )


def _check_timeout_protection(info: ModuleInfo) -> SafetyPattern:
    """Check for timeout protection mechanism."""
    import re
    full_text = "\n".join(info.raw_lines)
    has_timeout = bool(re.search(r"\btimeout\b|\bwatchdog\b|\bwdog\b", full_text, re.IGNORECASE))

    return SafetyPattern(
        pattern_name="Timeout Protection",
        present=has_timeout,
        description="Timeout protection prevents indefinite hanging in unsafe states.",
        signals_involved=["timeout"] if has_timeout else [],
        recommendation="Add a timeout or watchdog signal to force failsafe after inaction.",
    )


def _check_failsafe_fsm(info: ModuleInfo) -> SafetyPattern:
    """Check for a failsafe state machine pattern."""
    import re
    full_text = "\n".join(info.raw_lines)

    # Look for state machine patterns
    has_fsm = bool(
        re.search(r"\bIDLE\b|\bFAILSAFE\b|\bSAFE\b|\bERROR_STATE\b", full_text, re.IGNORECASE)
        and re.search(r"\bstate\b", full_text, re.IGNORECASE)
    )

    return SafetyPattern(
        pattern_name="Failsafe FSM",
        present=has_fsm,
        description="A failsafe FSM ensures the design can transition to a known-safe state.",
        signals_involved=["state (FSM)"] if has_fsm else [],
        recommendation="Implement a state machine with IDLE, VERIFYING, APPROVED, BLOCKED, and FAILSAFE states.",
    )


def _check_kill_switch_coverage(info: ModuleInfo) -> SafetyPattern:
    """Check that kill_switch is used to gate outputs (not just declared)."""
    import re
    full_text = "\n".join(info.raw_lines)
    has_kill = bool(re.search(r"\bkill_switch\b|\bemergency_stop\b|\bestop\b", full_text, re.IGNORECASE))

    # Check it's actually used in assignments, not just declared
    used_in_logic = False
    if has_kill:
        for a in info.assignments:
            if _is_actuator_signal(a.target):
                if re.search(r"\bkill_switch\b|\bemergency_stop\b|\bestop\b", a.expression, re.IGNORECASE):
                    used_in_logic = True
                    break

    return SafetyPattern(
        pattern_name="Kill Switch Coverage",
        present=has_kill and used_in_logic,
        description="Kill switch must be declared AND used to gate safety-critical outputs.",
        signals_involved=["kill_switch"] if has_kill else [],
        recommendation="Declare kill_switch as input and include !kill_switch in actuator gating.",
    )