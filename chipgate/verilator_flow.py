"""
ChipGate Verilator lint flow.

Runs Verilator lint on a Verilog file if Verilator is installed.
If Verilator is not installed, returns LINT_SKIPPED_TOOL_MISSING.

All commands are invoked as lists.
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

from . import statuses as st


@dataclass
class LintResult:
    """Result of a Verilator lint run."""
    status: str
    warning_count: int = 0
    error_count: int = 0
    output: str = ""
    command: str = ""
    tool_version: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "output": self.output[:2000] if self.output else "",
            "command": self.command,
            "tool_version": self.tool_version,
        }


def _extract_counts(output: str) -> Tuple[int, int]:
    """
    Extract warning and error counts from Verilator output.

    Verilator outputs lines like:
      %Warning-UNDRIVEN: ...
      %Error: ...
    We count unique warning/error markers.
    """
    warnings = len(re.findall(r"%Warning-", output))
    errors = len(re.findall(r"%Error", output))
    return warnings, errors


def _get_verilator_version() -> Optional[str]:
    """Get Verilator version string."""
    try:
        result = subprocess.run(
            ["verilator", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def run_verilator_lint(
    rtl_path: str,
    verilator_bin: Optional[str] = None,
    timeout_seconds: int = 60,
) -> LintResult:
    """
    Run Verilator lint on a Verilog file.

    Args:
        rtl_path: Path to the Verilog/SystemVerilog file.
        verilator_bin: Optional path to verilator binary (default: "verilator").
        timeout_seconds: Maximum execution time.

    Returns:
        LintResult with status, counts, and output.
    """
    bin_name = verilator_bin or "verilator"
    exe = shutil.which(bin_name)
    if exe is None:
        return LintResult(
            status=st.LINT_SKIPPED_TOOL_MISSING,
            output="Verilator not found on PATH",
        )

    version = _get_verilator_version()

    cmd = [
        exe,
        "--lint-only",
        "--no-timing",
        "-Wall",
        str(rtl_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        output = result.stdout + "\n" + result.stderr
        warnings, errors = _extract_counts(output)

        if errors > 0 or result.returncode != 0:
            status = st.LINT_FAIL
        else:
            status = st.LINT_PASS

        return LintResult(
            status=status,
            warning_count=warnings,
            error_count=errors,
            output=output.strip(),
            command=" ".join(cmd),
            tool_version=version,
        )

    except subprocess.TimeoutExpired:
        return LintResult(
            status=st.LINT_FAIL,
            output=f"Verilator lint timed out after {timeout_seconds}s",
            command=" ".join(cmd),
            tool_version=version,
        )
    except OSError as e:
        return LintResult(
            status=st.LINT_FAIL,
            output=f"Verilator execution failed: {e}",
            command=" ".join(cmd),
            tool_version=version,
        )


def parse_verilator_output(output: str) -> Tuple[int, int]:
    """
    Parse Verilator output to extract warning/error counts.
    Useful for testing with mocked output.
    """
    return _extract_counts(output)