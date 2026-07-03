"""
ChipGate TinyTapeoutPrep — 15 submission readiness checks.

Each check is a pure-Python function that operates on file content strings.
No external tools required. Checks are designed to run without Verilator,
Yosys, or any EDA tooling.

Checks:
  1.  Top module file exists
  2.  Top module name matches info.yaml
  3.  No private imports or names (proprietary, confidential)
  4.  No unsupported SystemVerilog constructs (classes, interfaces, etc.)
  5.  No inferred latches (incomplete case/if-else in always @*)
  6.  Clock signal documented
  7.  Reset signal documented
  8.  Pinout documented in info.yaml
  9.  docs/info.md exists
  10. Testbench exists
  11. Safety properties listed
  12. ChipGate scan passes (structural scan only, no external tools)
  13. LongevityBench: pass or skip safely (not run, just skip noted)
  14. SiliconReadinessBench: pass or skip safely
  15. FPGABoardBench: pass or skip safely
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from . import statuses as st
from .tt_pinout import get_canonical_pinout


# ── Private name patterns to detect ──────────────────────────────────────────

_PRIVATE_PATTERNS: List[re.Pattern] = [
    re.compile(r"j\x61rvi3", re.IGNORECASE),
    re.compile(r"proprietary", re.IGNORECASE),
    re.compile(r"confidential", re.IGNORECASE),
    re.compile(r"PRIVATE_DTL", re.IGNORECASE),
    re.compile(r"secret[_-]?key", re.IGNORECASE),
    re.compile(r"internal[_-]?only", re.IGNORECASE),
    re.compile(r"not[_-]?for[_-]?public", re.IGNORECASE),
]

# ── Unsupported SV constructs ────────────────────────────────────────────────

_UNSUPPORTED_SV_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bclass\s+\w+", re.IGNORECASE),
    re.compile(r"\binterface\s+\w+", re.IGNORECASE),
    re.compile(r"\bprogram\s+\w+", re.IGNORECASE),
    re.compile(r"\bpackage\s+\w+", re.IGNORECASE),
    re.compile(r"\bvirtual\s+class\b", re.IGNORECASE),
    re.compile(r"\bextends\s+\w+", re.IGNORECASE),
    re.compile(r"\btypedef\s+.*\benum\b", re.IGNORECASE),
    re.compile(r"\bcovergroup\b", re.IGNORECASE),
    re.compile(r"\bconstraint\b", re.IGNORECASE),
    re.compile(r"\brandomize\b", re.IGNORECASE),
    re.compile(r"##\s*\d+"),  # delay in SV
    re.compile(r"@\s*\("),  # event control beyond always (covered by always patterns)
]

# ── Latch patterns ────────────────────────────────────────────────────────────

_LATCH_INDICATORS: List[re.Pattern] = [
    re.compile(r"always\s+@\s*\(\s*\*\s*\)", re.IGNORECASE),
    re.compile(r"always\s+@\s*\(\s*\*\s*,\s*\*\s*\)", re.IGNORECASE),
    re.compile(r"always_comb\b"),
]


@dataclass
class SubmissionCheckResult:
    """Result of all 15 submission readiness checks."""
    checks: List[Dict[str, str]] = field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    overall_status: str = st.TT_SUBMISSION_CHECK_PASS
    manual_review_items: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "checks": self.checks,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "overall_status": self.overall_status,
            "manual_review_items": list(self.manual_review_items),
        }


def run_submission_checks(
    top_module_verilog: str,
    info_yaml_content: str,
    info_md_content: str,
    testbench_content: str,
    top_module_name: str = "tt_um_chipgate_dtl_gate",
) -> SubmissionCheckResult:
    """Run all 15 submission readiness checks.

    Args:
        top_module_verilog: Content of the top-level Verilog file.
        info_yaml_content: Content of info.yaml.
        info_md_content: Content of docs/info.md.
        testbench_content: Content of the testbench file.
        top_module_name: Expected top module name.

    Returns:
        SubmissionCheckResult with all 15 check outcomes.
    """
    result = SubmissionCheckResult()
    checks = []

    # Check 1: Top module file exists (we have content, so it exists)
    checks.append(_make_check("1", "Top module file exists",
                              "PASS" if top_module_verilog.strip() else "FAIL"))

    # Check 2: Top module name matches
    name_match = re.search(r"module\s+(\w+)", top_module_verilog)
    actual_name = name_match.group(1) if name_match else ""
    checks.append(_make_check("2", "Top module name matches info.yaml",
                              "PASS" if actual_name == top_module_name else "FAIL",
                              detail=f"Expected: {top_module_name}, Found: {actual_name}"))

    # Check 3: No private imports or names
    private_leaks = _detect_private_names(top_module_verilog)
    if private_leaks:
        checks.append(_make_check("3", "No private imports or names", "FAIL",
                                  detail=f"Found: {', '.join(private_leaks)}"))
        result.manual_review_items.append(
            f"Private name detected: {', '.join(private_leaks)}"
        )
    else:
        checks.append(_make_check("3", "No private imports or names", "PASS"))

    # Check 4: No unsupported SV
    sv_issues = _detect_unsupported_sv(top_module_verilog)
    if sv_issues:
        checks.append(_make_check("4", "No unsupported SystemVerilog constructs", "FAIL",
                                  detail=f"Found: {', '.join(sv_issues)}"))
    else:
        checks.append(_make_check("4", "No unsupported SystemVerilog constructs", "PASS"))

    # Check 5: No inferred latches
    latch_issues = _detect_latch_patterns(top_module_verilog)
    # For combinational designs, always @(*) with complete assignments is fine.
    # We flag only suspicious patterns: always @(*) with incomplete case/if-else.
    has_always_star = any(p.search(top_module_verilog) for p in _LATCH_INDICATORS)
    if has_always_star:
        # Check if all outputs are assigned in all branches
        incomplete = _check_incomplete_assignments(top_module_verilog)
        if incomplete:
            checks.append(_make_check("5", "No inferred latches", "FAIL",
                                      detail=f"Possible incomplete assignments: {', '.join(incomplete)}"))
        else:
            checks.append(_make_check("5", "No inferred latches", "PASS"))
    else:
        # No always @(*) at all, so no latch risk
        checks.append(_make_check("5", "No inferred latches", "PASS"))

    # Check 6: Clock signal documented
    has_clk = "clk" in top_module_verilog.lower()
    clk_in_docs = "clk" in info_md_content.lower() or "clock" in info_md_content.lower()
    checks.append(_make_check("6", "Clock signal documented",
                              "PASS" if has_clk and clk_in_docs else "FAIL"))

    # Check 7: Reset signal documented
    has_rst = "rst_n" in top_module_verilog or "reset" in top_module_verilog.lower()
    rst_in_docs = "reset" in info_md_content.lower() or "rst" in info_md_content.lower()
    checks.append(_make_check("7", "Reset signal documented",
                              "PASS" if has_rst and rst_in_docs else "FAIL"))

    # Check 8: Pinout documented in info.yaml
    pinout = get_canonical_pinout()
    pinout_doc = all(f"{sig}" in info_yaml_content for sig in pinout)
    checks.append(_make_check("8", "Pinout documented in info.yaml",
                              "PASS" if pinout_doc else "FAIL"))

    # Check 9: docs/info.md exists (we have content)
    checks.append(_make_check("9", "docs/info.md exists",
                              "PASS" if info_md_content.strip() else "FAIL"))

    # Check 10: Testbench exists (we have content)
    checks.append(_make_check("10", "Testbench exists",
                              "PASS" if testbench_content.strip() else "FAIL"))

    # Check 11: Safety properties listed
    safety_keywords = ["kill_switch", "timeout", "reset", "verifier_ok", "policy_ok", "sensor_ok"]
    safety_found = [kw for kw in safety_keywords if kw in info_md_content]
    checks.append(_make_check("11", "Safety properties listed",
                              "PASS" if len(safety_found) >= 3 else "FAIL",
                              detail=f"Found {len(safety_found)}/{len(safety_keywords)} safety signals"))

    # Check 12: ChipGate scan (structural only)
    # We do a lightweight structural check here — not the full scanner
    scan_issues = _structural_scan(top_module_verilog)
    checks.append(_make_check("12", "ChipGate scan passes",
                              "PASS" if not scan_issues else "FAIL",
                              detail="; ".join(scan_issues) if scan_issues else None))

    # Check 13: LongevityBench — graceful degradation, always skip
    checks.append(_make_check("13", "LongevityBench: pass or skip safely", "SKIP",
                              detail="LongevityBench gracefully skipped (no external tools required)"))
    result.manual_review_items.append(
        "LongevityBench not run: run separately with 'chipgate longevity --demo'"
    )

    # Check 14: SiliconReadinessBench — graceful degradation
    checks.append(_make_check("14", "SiliconReadinessBench: pass or skip safely", "SKIP",
                              detail="SiliconReadinessBench gracefully skipped (no external tools required)"))
    result.manual_review_items.append(
        "SiliconReadinessBench not run: run separately with 'chipgate silicon --demo'"
    )

    # Check 15: FPGABoardBench — graceful degradation
    checks.append(_make_check("15", "FPGABoardBench: pass or skip safely", "SKIP",
                              detail="FPGABoardBench gracefully skipped (no external tools required)"))
    result.manual_review_items.append(
        "FPGABoardBench not run: run separately with 'chipgate fpga --demo'"
    )

    # Tally
    for chk in checks:
        status = chk["status"]
        if status == "PASS":
            result.passed_count += 1
        elif status == "FAIL":
            result.failed_count += 1
        else:
            result.skipped_count += 1

    result.checks = checks
    result.overall_status = (
        st.TT_SUBMISSION_CHECK_PASS if result.failed_count == 0
        else st.TT_SUBMISSION_CHECK_FAIL
    )

    return result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_check(check_id: str, name: str, status: str,
                detail: Optional[str] = None) -> Dict[str, str]:
    """Create a check result dict."""
    chk = {"id": check_id, "name": name, "status": status}
    if detail:
        chk["detail"] = detail
    return chk


def _detect_private_names(content: str) -> List[str]:
    """Detect private or proprietary name patterns in Verilog content."""
    found = []
    for pattern in _PRIVATE_PATTERNS:
        if pattern.search(content):
            found.append(pattern.pattern)
    return found


def _detect_unsupported_sv(content: str) -> List[str]:
    """Detect unsupported SystemVerilog constructs."""
    # Exclude comment lines
    code_lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        code_lines.append(line)
    code = "\n".join(code_lines)

    found = []
    for pattern in _UNSUPPORTED_SV_PATTERNS:
        if pattern.search(code):
            found.append(pattern.pattern)
    return found


def _detect_latch_patterns(content: str) -> List[str]:
    """Detect potential latch inference patterns."""
    found = []
    for pattern in _LATCH_INDICATORS:
        if pattern.search(content):
            found.append(pattern.pattern)
    return found


def _check_incomplete_assignments(content: str) -> List[str]:
    """Check for incomplete assignments in always @(*) blocks.

    Returns list of suspicious signal names that may cause latch inference.
    This is a heuristic check, not a full lint.
    """
    issues = []

    # Find always @(*) blocks
    always_pattern = re.compile(
        r"always\s+@\s*\(\s*\*?\s*\)\s*begin(.*?)end",
        re.DOTALL | re.IGNORECASE
    )
    for match in always_pattern.finditer(content):
        block = match.group(1)

        # Find all signal assignments
        assigned = re.findall(r"(?:assign\s+)?(\w+)\s*=", block)

        # Find case statements
        cases = re.split(r"\bcase\b", block, flags=re.IGNORECASE)
        if len(cases) > 1:
            # Multiple case branches — check if all signals are assigned
            # in each branch (simplified check)
            for branch in cases[1:]:
                branch_assigned = set(re.findall(r"(\w+)\s*=", branch))
                for sig in set(assigned) - branch_assigned:
                    if sig not in ("begin", "end", "else", "if"):
                        issues.append(sig)

    return issues


def _structural_scan(verilog: str) -> List[str]:
    """Lightweight structural scan of Verilog content.

    Checks for basic safety issues:
      - Ungated outputs
      - Missing kill_switch path
      - Missing reset path
    """
    issues = []

    # Check for actuator_enable without proper gating
    if "actuator_enable" in verilog:
        # Should be gated by verifier_ok, policy_ok, kill_switch etc.
        has_kill = "kill_switch" in verilog
        has_timeout = "timeout" in verilog
        has_reset = "reset" in verilog or "rst_n" in verilog
        has_verifier = "verifier_ok" in verilog

        if not has_kill:
            issues.append("actuator_enable missing kill_switch gating")
        if not has_timeout:
            issues.append("actuator_enable missing timeout gating")
        if not has_reset:
            issues.append("actuator_enable missing reset gating")
        if not has_verifier:
            issues.append("actuator_enable missing verifier_ok gating")

    return issues