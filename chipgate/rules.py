"""
ChipGate rule definitions.

Each rule has an id, a human-readable description, a severity level,
and a check function that operates on parsed RTL data.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Rule:
    """A single verification rule."""
    rule_id: str
    description: str
    severity: Severity
    check: Optional[Callable] = None
    rationale: str = ""

    def __repr__(self) -> str:
        return f"Rule({self.rule_id}, {self.severity.value})"


def _rule(rule_id: str, description: str, severity: Severity, rationale: str = "") -> Rule:
    return Rule(rule_id=rule_id, description=description, severity=severity, rationale=rationale)


# ── Rule Catalogue ──────────────────────────────────────────────────────────

RULES: List[Rule] = [
    _rule(
        "CG001",
        "Missing reset signal — no 'rst' or 'reset' found in sensitivity list or always block",
        Severity.CRITICAL,
        "Safety-critical designs must have a reset to reach a known state on power-up.",
    ),
    _rule(
        "CG002",
        "Missing default case in case/if-else chain",
        Severity.HIGH,
        "Missing defaults can cause latches or undefined state in synthesis.",
    ),
    _rule(
        "CG003",
        "Possible latch inference — incomplete assignment in combinational block",
        Severity.HIGH,
        "Latches in RTL often indicate unintended behaviour and can cause timing issues.",
    ),
    _rule(
        "CG004",
        "Undriven output — output port declared but never assigned",
        Severity.CRITICAL,
        "Undriven outputs float to undefined values, which can cause unpredictable hardware behaviour.",
    ),
    _rule(
        "CG005",
        "Unused input — input port declared but never referenced",
        Severity.LOW,
        "Unused inputs may indicate a design error or incomplete connection.",
    ),
    _rule(
        "CG006",
        "Hardcoded bypass — direct assignment from input to actuator/safety output",
        Severity.CRITICAL,
        "A direct bypass skips all verification gates and can cause unsafe actuation.",
    ),
    _rule(
        "CG007",
        "Actuator output not gated by verifier_ok",
        Severity.CRITICAL,
        "DTL requires that safety-critical outputs pass through a verifier gate before actuation.",
    ),
    _rule(
        "CG008",
        "Actuator output not gated by policy_ok",
        Severity.CRITICAL,
        "DTL requires policy compliance checks before enabling physical actuation.",
    ),
    _rule(
        "CG009",
        "Kill switch / emergency stop path missing",
        Severity.CRITICAL,
        "Safety-critical designs must provide a hardware kill-switch or emergency stop input.",
    ),
    _rule(
        "CG010",
        "No assertions found in the design",
        Severity.MEDIUM,
        "Assertions are essential for verification; their absence makes formal checks impossible.",
    ),
    _rule(
        "CG011",
        "No testbench companion file detected",
        Severity.MEDIUM,
        "Without a testbench the design cannot be simulated or regression-tested.",
    ),
    _rule(
        "CG012",
        "No replay command — design cannot be deterministically re-verified",
        Severity.LOW,
        "Replay commands enable deterministic re-verification of results.",
    ),
    _rule(
        "CG013",
        "Unsafe bypass path — potential shortcut around safety logic",
        Severity.CRITICAL,
        "Any path that bypasses safety gates is a critical violation.",
    ),
    _rule(
        "CG014",
        "Safety gate present — output properly gated by verification signals",
        Severity.INFO,
        "The output is gated by verifier_ok / policy_ok / kill_switch logic.",
    ),
]

RULE_BY_ID = {r.rule_id: r for r in RULES}


def get_rules(severity: Optional[Severity] = None) -> List[Rule]:
    """Return rules, optionally filtered by minimum severity."""
    if severity is None:
        return list(RULES)
    severity_order = {Severity.CRITICAL: 5, Severity.HIGH: 4, Severity.MEDIUM: 3, Severity.LOW: 2, Severity.INFO: 1}
    min_level = severity_order.get(severity, 0)
    return [r for r in RULES if severity_order.get(r.severity, 0) >= min_level]