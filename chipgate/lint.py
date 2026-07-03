"""
ChipGate lint runner.

Attempts to run Verilator for external lint checks. If Verilator is not
installed, the check is skipped gracefully and internal scan results are used.
"""

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LintResult:
    """Result of a lint check."""
    tool: str
    available: bool
    passed: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    command: str = ""


def verilator_available() -> bool:
    """Check if Verilator is installed on the system."""
    return shutil.which("verilator") is not None


def run_verilator_lint(file_path: str, extra_args: Optional[List[str]] = None) -> LintResult:
    """
    Run Verilator in lint-only mode on a Verilog file.

    Verilator is an open-source Verilog/SystemVerilog simulator that also
    performs lint and code-quality checks. When not installed, this function
    returns a graceful skip result rather than failing.
    """
    if not verilator_available():
        return LintResult(
            tool="verilator",
            available=False,
            passed=False,
            command="",
            errors=["Verilator not installed — skipping external lint. Run internal scan instead."],
        )

    cmd = ["verilator", "--lint-only", "-Wall", file_path]
    if extra_args:
        cmd.extend(extra_args)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        passed = proc.returncode == 0

        # Parse output for warnings and errors
        warnings = []
        errors = []
        for line in (proc.stdout + proc.stderr).splitlines():
            lower = line.lower()
            if "%warn" in lower or "warning" in lower:
                warnings.append(line.strip())
            elif "%error" in lower or "error" in lower:
                errors.append(line.strip())

        return LintResult(
            tool="verilator",
            available=True,
            passed=passed,
            warnings=warnings,
            errors=errors,
            command=" ".join(cmd),
        )
    except subprocess.TimeoutExpired:
        return LintResult(
            tool="verilator",
            available=True,
            passed=False,
            errors=["Verilator lint timed out after 60 seconds."],
            command=" ".join(cmd),
        )
    except OSError as e:
        return LintResult(
            tool="verilator",
            available=True,
            passed=False,
            errors=[f"Failed to run Verilator: {e}"],
            command=" ".join(cmd),
        )


def run_lint(file_path: str, extra_args: Optional[List[str]] = None) -> LintResult:
    """
    Run external lint checks. Currently supports Verilator.

    Returns a LintResult. If no external tools are available,
    the result indicates graceful skip.
    """
    return run_verilator_lint(file_path, extra_args)