"""
ChipGate timing-depth proxy estimator.

Estimates a proxy for combinational timing depth by tracing the
longest boolean/operator chain in RTL expressions. This is NOT
real timing analysis or static timing analysis (STA).

Lower depth suggests potentially faster critical paths, but only
when combined with a passing safety check.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .scanner import parse_verilog, ModuleInfo


@dataclass
class TimingProxyResult:
    """Result of timing-depth proxy estimation for an RTL file."""
    file_path: str
    max_chain_depth: int = 0
    avg_chain_depth: float = 0.0
    total_chains: int = 0
    longest_chain_expr: str = ""
    has_nested_logic: bool = False
    weighted_depth: float = 0.0
    detail: str = ""


def _tokenize_expression(expr: str) -> List[str]:
    """
    Split an expression into tokens (operators, identifiers, numbers).

    Operators increase chain depth; identifiers and numbers are leaves.
    """
    # Remove Verilog line comments
    expr = re.sub(r'//.*$', '', expr)
    # Remove block comments (simple, non-nested)
    expr = re.sub(r'/\*.*?\*/', '', expr, flags=re.DOTALL)

    tokens = re.findall(
        r'[&|~^+\-*/%!=<>]|<<|>>|===|!==|=>|\w+|\?|:',
        expr,
    )
    return tokens


def _estimate_chain_depth(expr: str) -> int:
    """
    Estimate the depth of a boolean/arithmetic chain.

    Uses a simple stack-based approach: operators push depth,
    the maximum depth reached is the chain depth.

    This is a heuristic, not an actual DAG traversal.
    """
    tokens = _tokenize_expression(expr)
    if not tokens:
        return 0

    max_depth = 0
    current_depth = 0
    paren_depth = 0

    for token in tokens:
        if token == '(':
            paren_depth += 1
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif token == ')':
            paren_depth = max(paren_depth - 1, 0)
            current_depth = max(current_depth - 1, 0)
        elif token in ('&', '|', '^', '~', '&&', '||', '!', '+', '-', '*', '/', '%',
                       '==', '!=', '>', '<', '>=', '<=', '<<', '>>', '===', '!==',
                       '?', ':'):
            # Operator increases depth
            current_depth += 1
            max_depth = max(max_depth, current_depth)
            # After binary operator, next operand reduces effective depth
            # (it's a sibling, not nested)
            current_depth = max(current_depth - 1, 0)

    return max_depth


def _extract_expressions(info: ModuleInfo) -> List[str]:
    """Extract all expressions from assignments and always blocks."""
    expressions = []

    # Continuous assignments
    for a in info.assignments:
        if a.expression.strip():
            expressions.append(a.expression)

    # Always block body lines with assignments
    for ab in info.always_blocks:
        for line in ab.body_lines:
            stripped = line.strip()
            # Look for assignment operators
            match = re.match(r'(?:\w+\s*)?<=(.+?);?\s*$', stripped)
            if match:
                expressions.append(match.group(1).strip())
            else:
                match = re.match(r'(?:\w+\s*)?=(?!=)(.+?);?\s*$', stripped)
                if match:
                    expressions.append(match.group(1).strip())

    return expressions


def compute_timing_proxy(file_path: str) -> TimingProxyResult:
    """
    Compute timing-depth proxy for an RTL file.

    This is a structural heuristic based on expression nesting analysis.
    It does NOT represent real STA, clock frequency, or timing signoff.
    """
    info = parse_verilog(file_path)
    expressions = _extract_expressions(info)

    if not expressions:
        return TimingProxyResult(
            file_path=file_path,
            max_chain_depth=0,
            avg_chain_depth=0.0,
            total_chains=0,
            detail="No expressions found",
        )

    depths = []
    longest_expr = ""
    max_depth = 0

    for expr in expressions:
        d = _estimate_chain_depth(expr)
        depths.append(d)
        if d > max_depth:
            max_depth = d
            longest_expr = expr[:80] + ("..." if len(expr) > 80 else "")

    avg_depth = sum(depths) / len(depths) if depths else 0.0

    # Weighted depth: max depth gets higher weight (critical path proxy)
    weighted_depth = 0.7 * max_depth + 0.3 * avg_depth

    # Detect nested logic patterns
    full_text = "\n".join(info.raw_lines)
    has_nested = bool(re.search(r'\(\s*\(', full_text))

    total_chains = len(depths)

    detail = (
        f"expressions={total_chains}, max_depth={max_depth}, "
        f"avg_depth={round(avg_depth, 1)}, nested={has_nested}"
    )

    return TimingProxyResult(
        file_path=file_path,
        max_chain_depth=max_depth,
        avg_chain_depth=round(avg_depth, 2),
        total_chains=total_chains,
        longest_chain_expr=longest_expr,
        has_nested_logic=has_nested,
        weighted_depth=round(weighted_depth, 2),
        detail=detail,
    )


def compute_timing_proxy_from_rtl(rtl_text: str, label: str = "inline") -> TimingProxyResult:
    """Compute timing-depth proxy from RTL text string."""
    import tempfile
    import os

    tmp_dir = tempfile.mkdtemp(prefix="chipgate_synth_")
    tmp_path = os.path.join(tmp_dir, f"{label}.v")
    try:
        with open(tmp_path, "w") as f:
            f.write(rtl_text)
        return compute_timing_proxy(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


def timing_improvement_percent(baseline: float, candidate: float) -> float:
    """
    Calculate percentage improvement in timing-depth proxy.

    Positive = candidate has lower depth (potentially faster).
    Negative = candidate has higher depth (potentially slower).
    """
    if baseline == 0:
        return 0.0
    return round(((baseline - candidate) / baseline) * 100, 1)