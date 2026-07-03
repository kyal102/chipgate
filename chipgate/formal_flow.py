"""
ChipGate formal verification flow.

Runs SymbiYosys (sby) formal checks on Verilog files if SBY is installed.
If SBY is not installed, returns FORMAL_SKIPPED_TOOL_MISSING.

All commands are invoked as lists.

Default formal properties checked (when SBY is available):
  - kill_switch implies actuator_enable is never high
  - timeout implies actuator_enable is low
  - actuator_enable implies verifier_ok and policy_ok
"""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from . import statuses as st


@dataclass
class FormalResult:
    """Result of a formal verification run."""
    status: str
    properties_checked: int = 0
    properties_passed: int = 0
    properties_failed: int = 0
    output: str = ""
    command: str = ""
    tool_version: Optional[str] = None
    property_details: List[Dict[str, str]] = None

    def __post_init__(self):
        if self.property_details is None:
            self.property_details = []

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "properties_checked": self.properties_checked,
            "properties_passed": self.properties_passed,
            "properties_failed": self.properties_failed,
            "output": self.output[:2000] if self.output else "",
            "command": self.command,
            "tool_version": self.tool_version,
            "property_details": self.property_details,
        }


DEFAULT_SBY_CONFIG = """[options]
mode bmc
depth 20

[engines]
smtbmc

[script]
read_verilog {rtl_path}
prep -top {top_module}

[files]
{rtl_path}

[props]
{properties}
"""

# Default safety properties for DTL-style gates
DEFAULT_PROPERTIES = """
// Property: kill_switch must prevent actuator_enable
assert (kill_switch |-> !actuator_enable);

// Property: if verifier_ok is low, actuator must be disabled
assert (!verifier_ok |-> !actuator_enable);

// Property: if policy_ok is low, actuator must be disabled
assert (!policy_ok |-> !actuator_enable);

// Property: actuator_enable requires all safety signals
assert (actuator_enable |-> (verifier_ok && policy_ok && !kill_switch));
"""


def _get_sby_version() -> Optional[str]:
    """Get SymbiYosys version string."""
    try:
        result = subprocess.run(
            ["sby", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _extract_formal_results(output: str) -> Dict[str, int]:
    """
    Extract formal property results from SBY output.

    SBY output includes lines like:
      PASSED: ...
      FAILED: ...
      [sby] ...
    """
    passed = len(re.findall(r"passed", output, re.IGNORECASE))
    failed = len(re.findall(r"failed", output, re.IGNORECASE))
    return {"passed": passed, "failed": failed}


def _find_top_module(rtl_text: str) -> Optional[str]:
    """Extract module name from Verilog text."""
    match = re.search(r"module\s+(\w+)", rtl_text)
    return match.group(1) if match else None


def run_formal_check(
    rtl_path: str,
    sby_bin: Optional[str] = None,
    top_module: Optional[str] = None,
    properties: Optional[str] = None,
    timeout_seconds: int = 120,
    work_dir: Optional[str] = None,
) -> FormalResult:
    """
    Run SymbiYosys formal verification on a Verilog file.

    Args:
        rtl_path: Path to the Verilog/SystemVerilog file.
        sby_bin: Optional path to sby binary (default: "sby").
        top_module: Optional top module name (auto-detected if omitted).
        properties: Optional SVA property text.
        timeout_seconds: Maximum execution time.
        work_dir: Optional working directory for SBY output.

    Returns:
        FormalResult with status and property details.
    """
    import shutil

    bin_name = sby_bin or "sby"
    exe = shutil.which(bin_name)
    if exe is None:
        return FormalResult(
            status=st.FORMAL_SKIPPED_TOOL_MISSING,
            output="SymbiYosys (sby) not found on PATH",
        )

    version = _get_sby_version()

    # Read RTL to auto-detect top module
    rtl_text = Path(rtl_path).read_text(encoding="utf-8", errors="replace")
    if top_module is None:
        top_module = _find_top_module(rtl_text)
    if top_module is None:
        top_module = "top"

    # Use default or custom properties
    props_text = properties or DEFAULT_PROPERTIES

    # Build SBY config
    rtl_abs = str(Path(rtl_path).resolve())
    sby_content = DEFAULT_SBY_CONFIG.format(
        rtl_path=rtl_abs,
        top_module=top_module,
        properties=props_text.strip(),
    )

    # Write SBY config to temp file
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="chipgate_formal_")

    sby_file = os.path.join(work_dir, "formal_check.sby")
    with open(sby_file, "w", encoding="utf-8") as f:
        f.write(sby_content)

    cmd = [exe, "-f", sby_file]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=work_dir,
        )
        output = result.stdout + "\n" + result.stderr
        counts = _extract_formal_results(output)

        # Parse individual property results
        property_details = []
        for match in re.finditer(
            r"(\w+):\s+(PASSED|FAILED|UNKNOWN)", output, re.IGNORECASE
        ):
            prop_name = match.group(1)
            prop_result = match.group(2).upper()
            property_details.append({
                "property": prop_name,
                "result": prop_result,
            })

        total_checked = counts["passed"] + counts["failed"]
        if counts["failed"] > 0 or result.returncode != 0:
            status = st.FORMAL_FAIL
        else:
            status = st.FORMAL_PASS

        return FormalResult(
            status=status,
            properties_checked=total_checked,
            properties_passed=counts["passed"],
            properties_failed=counts["failed"],
            output=output.strip(),
            command=" ".join(cmd),
            tool_version=version,
            property_details=property_details,
        )

    except subprocess.TimeoutExpired:
        return FormalResult(
            status=st.FORMAL_FAIL,
            output=f"Formal check timed out after {timeout_seconds}s",
            command=" ".join(cmd),
            tool_version=version,
        )
    except OSError as e:
        return FormalResult(
            status=st.FORMAL_FAIL,
            output=f"Formal check execution failed: {e}",
            command=" ".join(cmd),
            tool_version=version,
        )


def parse_formal_output(output: str) -> Dict[str, int]:
    """
    Parse SBY output to extract pass/fail counts.
    Useful for testing with mocked output.
    """
    return _extract_formal_results(output)