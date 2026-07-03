"""
ChipGate area proxy estimator.

Estimates a proxy for design area by counting RTL-level structural elements:
assignments, registers, operators, mux-like expressions, and FSM states.

This is NOT real synthesis area. It is a transparent benchmark proxy metric.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .scanner import parse_verilog, ModuleInfo


@dataclass
class AreaProxyResult:
    """Result of area proxy estimation for an RTL file."""
    file_path: str
    total_assignments: int = 0
    total_registers: int = 0
    total_operators: int = 0
    total_mux_expressions: int = 0
    total_fsm_states: int = 0
    input_count: int = 0
    output_count: int = 0
    wire_count: int = 0
    raw_score: float = 0.0
    weighted_score: float = 0.0
    detail: str = ""


# Weights for each structural element in the area proxy score.
# These are heuristic weights, not measured synthesis data.
WEIGHTS = {
    "assignment": 1.0,
    "register": 3.0,
    "operator": 0.5,
    "mux": 4.0,
    "fsm_state": 5.0,
    "input": 0.5,
    "output": 0.5,
    "wire": 0.3,
}


def _count_operators(text: str) -> int:
    """Count arithmetic and logical operators in RTL text."""
    # Match operators: && || ! & | ^ ~ << >> == != > < >= <= + - * / %
    # Avoid counting operators inside comments or strings (basic filter)
    pattern = r'[&|~^+\-*/%]|={2,}|[<>]=?|<<|>>'
    matches = re.findall(pattern, text)
    return len(matches)


def _count_mux_expressions(info: ModuleInfo) -> int:
    """Estimate number of mux-like expressions (ternary operators, case-based mux)."""
    count = 0
    full_text = "\n".join(info.raw_lines)

    # Ternary operator: condition ? value1 : value2
    count += len(re.findall(r'\?\s*\w+\s*:', full_text))

    # Case blocks (each case acts as a mux selector)
    count += sum(len(cb.cases) for cb in info.case_blocks)
    if any(cb.has_default for cb in info.case_blocks):
        count += 1

    # if/else chains in always blocks
    for ab in info.always_blocks:
        body = "\n".join(ab.body_lines)
        count += len(re.findall(r'\bif\s*\(', body))

    return count


def _count_fsm_states(info: ModuleInfo) -> int:
    """Estimate number of FSM states from case blocks and state definitions."""
    count = 0
    full_text = "\n".join(info.raw_lines)

    # Look for parameter/localparam state definitions
    state_defs = re.findall(
        r'(?:parameter|localparam)\s+\w+\s*=\s*\d+\s*[,;]',
        full_text,
        re.IGNORECASE,
    )
    count += len(state_defs)

    # Look for 2-bit or 3-bit state registers (common FSM encoding)
    state_regs = re.findall(
        r'\breg\s+\[\d+:0\]\s*\w*[Ss]tate\w*\b',
        full_text,
    )
    count += len(state_regs) * 4  # Estimate 4 states per state register

    # Look for named states in case blocks
    for cb in info.case_blocks:
        if 'state' in cb.expression.lower():
            count += len(cb.cases)

    return max(count, 1)  # At least 1 state


def _count_registers(info: ModuleInfo) -> int:
    """Count register declarations."""
    count = 0
    full_text = "\n".join(info.raw_lines)

    # reg [width:name] declarations
    reg_patterns = re.findall(r'\breg\s+(?:\[\d+:0\]\s+)?\w+', full_text)
    count += len(reg_patterns)

    # Also count reg assignments (non-blocking = in always blocks)
    for ab in info.always_blocks:
        body = "\n".join(ab.body_lines)
        count += len(re.findall(r'<=\s*\w+', body))

    return count


def compute_area_proxy(file_path: str) -> AreaProxyResult:
    """
    Compute area proxy score for an RTL file.

    This is a structural heuristic based on RTL text analysis.
    It does NOT represent real synthesis area or physical layout.

    Lower scores suggest a simpler/smaller design, but only when
    combined with a passing safety check.
    """
    info = parse_verilog(file_path)
    full_text = "\n".join(info.raw_lines)

    assignments = len(info.assignments)
    registers = _count_registers(info)
    operators = _count_operators(full_text)
    mux_exprs = _count_mux_expressions(info)
    fsm_states = _count_fsm_states(info)
    inputs = sum(1 for p in info.ports if p.direction == "input")
    outputs = sum(1 for p in info.ports if p.direction == "output")
    wires = sum(1 for p in info.ports if p.is_wire)

    # Raw score: sum of all structural elements
    raw_score = (
        assignments
        + registers
        + operators
        + mux_exprs
        + fsm_states
        + inputs
        + outputs
        + wires
    )

    # Weighted score
    weighted_score = (
        assignments * WEIGHTS["assignment"]
        + registers * WEIGHTS["register"]
        + operators * WEIGHTS["operator"]
        + mux_exprs * WEIGHTS["mux"]
        + fsm_states * WEIGHTS["fsm_state"]
        + inputs * WEIGHTS["input"]
        + outputs * WEIGHTS["output"]
        + wires * WEIGHTS["wire"]
    )

    detail = (
        f"assignments={assignments}, registers={registers}, "
        f"operators={operators}, mux={mux_exprs}, fsm_states={fsm_states}, "
        f"inputs={inputs}, outputs={outputs}, wires={wires}"
    )

    return AreaProxyResult(
        file_path=file_path,
        total_assignments=assignments,
        total_registers=registers,
        total_operators=operators,
        total_mux_expressions=mux_exprs,
        total_fsm_states=fsm_states,
        input_count=inputs,
        output_count=outputs,
        wire_count=wires,
        raw_score=raw_score,
        weighted_score=round(weighted_score, 2),
        detail=detail,
    )


def compute_area_proxy_from_rtl(rtl_text: str, label: str = "inline") -> AreaProxyResult:
    """
    Compute area proxy from RTL text string (writes to temp file internally).

    Used by synthbench when candidates are defined as inline RTL.
    """
    import tempfile
    import os

    tmp_dir = tempfile.mkdtemp(prefix="chipgate_synth_")
    tmp_path = os.path.join(tmp_dir, f"{label}.v")
    try:
        with open(tmp_path, "w") as f:
            f.write(rtl_text)
        return compute_area_proxy(tmp_path)
    finally:
        # Clean up
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


def area_improvement_percent(baseline: float, candidate: float) -> float:
    """
    Calculate percentage improvement in area proxy.

    Positive = candidate is smaller (better).
    Negative = candidate is larger (worse).
    """
    if baseline == 0:
        return 0.0
    return round(((baseline - candidate) / baseline) * 100, 1)