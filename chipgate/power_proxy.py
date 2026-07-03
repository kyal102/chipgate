"""
ChipGate power-toggle proxy estimator.

Estimates a proxy for switching power by analysing toggle-risk
on safety-critical signals and total gate/operator count.

This is NOT real power analysis. It is a transparent benchmark
proxy metric based on structural heuristics.
"""

import re
from dataclasses import dataclass
from typing import List, Set

from .scanner import parse_verilog, ModuleInfo, _is_actuator_signal


@dataclass
class PowerProxyResult:
    """Result of power-toggle proxy estimation for an RTL file."""
    file_path: str
    safety_critical_signal_count: int = 0
    total_signal_toggles: int = 0
    operator_count: int = 0
    register_count: int = 0
    always_block_count: int = 0
    toggle_risk_score: float = 0.0
    weighted_power_proxy: float = 0.0
    detail: str = ""


# Safety-critical signal name patterns (case-insensitive)
SAFETY_CRITICAL_PATTERNS = [
    r'\bactuator\b',
    r'\bkill_switch\b',
    r'\bverifier_ok\b',
    r'\bpolicy_ok\b',
    r'\bai_output\b',
    r'\bsensor\b',
    r'\bwatchdog\b',
    r'\btimeout\b',
    r'\bfailsafe\b',
    r'\bemergency\b',
    r'\benable\b',
    r'\breset\b',
    r'\bclk\b',
    r'\bclk_gate\b',
]


def _count_safety_critical_signals(info: ModuleInfo) -> int:
    """Count signals matching safety-critical patterns."""
    full_text = "\n".join(info.raw_lines)
    found: Set[str] = set()

    for pattern in SAFETY_CRITICAL_PATTERNS:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        found.update(m.lower() for m in matches)

    return len(found)


def _estimate_toggle_risk(info: ModuleInfo) -> float:
    """
    Estimate toggle risk for safety-critical signals.

    Signals that appear in many expressions or always blocks
    have higher toggle risk.
    """
    full_text = "\n".join(info.raw_lines)

    # Count how many times safety signals appear in expressions
    toggle_count = 0
    for pattern in SAFETY_CRITICAL_PATTERNS:
        toggle_count += len(re.findall(pattern, full_text, re.IGNORECASE))

    # Weight by always block activity (sequential logic toggles)
    always_activity = len(info.always_blocks) * 2.0

    # Weight by assignment activity (combinational logic toggles)
    assignment_activity = len(info.assignments) * 0.5

    return toggle_count + always_activity + assignment_activity


def _count_operators(info: ModuleInfo) -> int:
    """Count operators in the RTL text."""
    full_text = "\n".join(info.raw_lines)
    pattern = r'[&|~^+\-*/%]|={2,}|[<>]=?|<<|>>'
    return len(re.findall(pattern, full_text))


def _count_registers(info: ModuleInfo) -> int:
    """Count register declarations."""
    full_text = "\n".join(info.raw_lines)
    return len(re.findall(r'\breg\s+', full_text))


def compute_power_proxy(file_path: str) -> PowerProxyResult:
    """
    Compute power-toggle proxy for an RTL file.

    This is a structural heuristic. It does NOT represent
    real power consumption, dynamic power, leakage power,
    or IR drop analysis.
    """
    info = parse_verilog(file_path)

    safety_signals = _count_safety_critical_signals(info)
    toggle_risk = _estimate_toggle_risk(info)
    operators = _count_operators(info)
    registers = _count_registers(info)
    always_blocks = len(info.always_blocks)

    # Toggle risk score: normalise to 0-100 range
    # Using a simple heuristic scaling
    toggle_risk_score = min(toggle_risk * 1.5, 100.0)

    # Weighted power proxy: combines toggle risk with structural complexity
    weighted_power_proxy = (
        toggle_risk_score * 0.6
        + (operators * 0.2)
        + (registers * 2.0)
        + (always_blocks * 3.0)
    )

    detail = (
        f"safety_signals={safety_signals}, toggle_risk={round(toggle_risk, 1)}, "
        f"operators={operators}, registers={registers}, "
        f"always_blocks={always_blocks}"
    )

    return PowerProxyResult(
        file_path=file_path,
        safety_critical_signal_count=safety_signals,
        total_signal_toggles=int(toggle_risk),
        operator_count=operators,
        register_count=registers,
        always_block_count=always_blocks,
        toggle_risk_score=round(toggle_risk_score, 2),
        weighted_power_proxy=round(weighted_power_proxy, 2),
        detail=detail,
    )


def compute_power_proxy_from_rtl(rtl_text: str, label: str = "inline") -> PowerProxyResult:
    """Compute power-toggle proxy from RTL text string."""
    import tempfile
    import os

    tmp_dir = tempfile.mkdtemp(prefix="chipgate_synth_")
    tmp_path = os.path.join(tmp_dir, f"{label}.v")
    try:
        with open(tmp_path, "w") as f:
            f.write(rtl_text)
        return compute_power_proxy(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


def power_improvement_percent(baseline: float, candidate: float) -> float:
    """
    Calculate percentage improvement in power proxy.

    Positive = candidate has lower power proxy (better).
    Negative = candidate has higher power proxy (worse).
    """
    if baseline == 0:
        return 0.0
    return round(((baseline - candidate) / baseline) * 100, 1)