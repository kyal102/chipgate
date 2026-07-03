"""
ChipGate formal assertion checker.

Prepares designs for formal verification using SymbiYosys (SBY) on top of Yosys.
For the public MVP, this module checks whether a design is structurally ready
for formal verification (has assertions, no problematic constructs).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .scanner import parse_verilog, RE_ASSERT


@dataclass
class FormalCheckResult:
    """Result of formal verification readiness check."""
    ready: bool
    assertion_count: int
    issues: List[str] = field(default_factory=list)
    sby_config: str = ""
    tool_available: bool = False


def yosys_available() -> bool:
    """Check if Yosys is installed."""
    import shutil
    return shutil.which("yosys") is not None


def sby_available() -> bool:
    """Check if SymbiYosys (sby) is installed."""
    import shutil
    return shutil.which("sby") is not None


def check_formal_readiness(file_path: str) -> FormalCheckResult:
    """
    Check whether a Verilog design is structurally ready for formal verification.

    This does not run formal verification itself — it checks:
    1. Whether assertions exist in the design
    2. Whether the design has potentially problematic constructs
    3. Whether SBY/Yosys tools are available
    """
    info = parse_verilog(file_path)
    issues = []
    assertion_count = 0

    # Count assertions
    for line in info.raw_lines:
        matches = RE_ASSERT.findall(line)
        assertion_count += len(matches)

    if assertion_count == 0:
        issues.append("No assertions found — formal verification requires at least one assertion property.")

    # Check for constructs that complicate formal verification
    full_text = "\n".join(info.raw_lines)
    if re.search(r"\$random", full_text, re.IGNORECASE):
        issues.append("Uses $random — non-deterministic, may complicate formal proof.")
    if re.search(r"\$display", full_text, re.IGNORECASE):
        issues.append("Uses $display — simulation-only, ignored in formal verification.")
    if re.search(r"\bdelay\b|\s*#\d+", full_text):
        issues.append("Contains delay constructs — not meaningful for formal verification.")

    # Check tool availability
    tool_available = yosys_available() and sby_available()

    # Generate a sample SBY config if assertions exist
    sby_config = ""
    if assertion_count > 0 and info.name:
        sby_config = _generate_sby_config(file_path, info.name)

    ready = assertion_count > 0 and len([i for i in issues if "No assertions" not in i]) == 0

    return FormalCheckResult(
        ready=ready,
        assertion_count=assertion_count,
        issues=issues,
        sby_config=sby_config,
        tool_available=tool_available,
    )


def _generate_sby_config(file_path: str, module_name: str) -> str:
    """Generate a sample SBY configuration file for formal verification."""
    file_name = Path(file_path).name
    return f"""[options]
mode prove
depth 20

[engines]
smtbmc

[script]
read_verilog {file_name}
prep -top {module_name}

[files]
{file_name}
"""


def run_formal_verification(file_path: str, timeout: int = 300) -> FormalCheckResult:
    """
    Attempt to run SymbiYosys formal verification.

    For the public MVP this checks readiness only. Full SBY execution
    is planned for a future release.
    """
    readiness = check_formal_readiness(file_path)

    if not readiness.ready:
        return readiness

    if not sby_available() or not yosys_available():
        readiness.issues.append(
            "SymbiYosys/Yosys not installed — cannot run formal verification. "
            "Install them for full formal proof support."
        )
        return readiness

    # Future: actually invoke sby here
    readiness.issues.append(
        "Formal verification execution via SBY is planned for a future release."
    )
    return readiness