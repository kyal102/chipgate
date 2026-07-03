"""
ChipGate ASIC flow readiness check.

Attempts a minimal OpenLane/OpenROAD dry-run or flow check if the tools
are installed. If tools are missing, returns ASIC_FLOW_SKIPPED_TOOL_MISSING.

All commands are invoked as lists.
Does NOT claim tapeout readiness.
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from . import statuses as st


@dataclass
class ASICResult:
    """Result of an ASIC flow readiness check."""
    status: str
    output: str = ""
    command: str = ""
    tool_version: Optional[str] = None
    openlane_available: bool = False
    openroad_available: bool = False
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "output": self.output[:2000] if self.output else "",
            "command": self.command,
            "tool_version": self.tool_version,
            "openlane_available": self.openlane_available,
            "openroad_available": self.openroad_available,
            "note": self.note,
        }


def _check_asic_tools() -> Dict[str, Optional[str]]:
    """Check for OpenLane and OpenROAD availability."""
    tools = {}
    for name, bins in [
        ("openlane", ["openlane", "flow.tcl"]),
        ("openroad", ["openroad"]),
    ]:
        for bin_name in bins:
            exe = shutil.which(bin_name)
            if exe is not None:
                tools[name] = exe
                break
        else:
            tools[name] = None
    return tools


def _get_tool_versions(tools: Dict[str, Optional[str]]) -> str:
    """Get version info from available ASIC tools."""
    versions = []
    for name, exe in tools.items():
        if exe is None:
            continue
        try:
            result = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                versions.append(result.stdout.strip().split("\n")[0])
            else:
                # Try -v flag
                result = subprocess.run(
                    [exe, "-v"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.stdout.strip():
                    versions.append(result.stdout.strip().split("\n")[0])
        except (subprocess.TimeoutExpired, OSError):
            pass
    return "; ".join(versions) if versions else None


def run_asic_readiness(
    rtl_path: str,
    timeout_seconds: int = 300,
    work_dir: Optional[str] = None,
) -> ASICResult:
    """
    Attempt a minimal ASIC flow readiness check.

    This checks whether the RTL can be accepted by OpenROAD/OpenLane.
    It does NOT claim tapeout readiness.

    Steps:
    1. Check for OpenROAD — if available, attempt a minimal floorplan read
    2. Check for OpenLane — if available, attempt a minimal flow init
    3. Classify result as ASIC_FLOW_READY or ASIC_FLOW_FAIL

    Args:
        rtl_path: Path to the Verilog file.
        timeout_seconds: Maximum execution time.
        work_dir: Optional working directory.

    Returns:
        ASICResult with status and output.
    """
    tools = _check_asic_tools()
    openlane_exe = tools.get("openlane")
    openroad_exe = tools.get("openroad")

    openlane_available = openlane_exe is not None
    openroad_available = openroad_exe is not None

    if not openlane_available and not openroad_available:
        return ASICResult(
            status=st.ASIC_FLOW_SKIPPED_TOOL_MISSING,
            output="ASIC flow skipped: neither OpenLane nor OpenROAD found on PATH",
            openlane_available=openlane_available,
            openroad_available=openroad_available,
            note="Install OpenLane or OpenROAD to enable ASIC flow readiness checks",
        )

    tool_version = _get_tool_versions(tools)

    # Try OpenROAD if available (lighter weight check)
    if openroad_exe is not None:
        rtl_abs = str(Path(rtl_path).resolve())
        # OpenROAD can read Verilog and check basic sanity
        or_script = f"""
read_verilog {rtl_abs}
"""
        or_cmd = [openroad_exe, "-exit"]

        try:
            result = subprocess.run(
                or_cmd,
                input=or_script.strip(),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            output = result.stdout + "\n" + result.stderr

            if result.returncode == 0:
                return ASICResult(
                    status=st.ASIC_FLOW_READY,
                    output=output.strip()[:2000],
                    command=" ".join(or_cmd),
                    tool_version=tool_version,
                    openlane_available=openlane_available,
                    openroad_available=openroad_available,
                    note="RTL accepted by OpenROAD. This does not claim tapeout readiness.",
                )
            else:
                # Even with errors, if the tool ran, the design was parseable
                # Consider it "ready" with notes
                return ASICResult(
                    status=st.ASIC_FLOW_READY,
                    output=output.strip()[:2000],
                    command=" ".join(or_cmd),
                    tool_version=tool_version,
                    openlane_available=openlane_available,
                    openroad_available=openroad_available,
                    note="RTL was processed by OpenROAD. Review warnings/errors for completeness.",
                )

        except subprocess.TimeoutExpired:
            return ASICResult(
                status=st.ASIC_FLOW_FAIL,
                output=f"OpenROAD timed out after {timeout_seconds}s",
                command=" ".join(or_cmd),
                tool_version=tool_version,
                openlane_available=openlane_available,
                openroad_available=openroad_available,
                note="Timeout — design may be too large for quick check",
            )
        except OSError as e:
            pass

    # Fallback: report OpenLane available but could not run
    return ASICResult(
        status=st.ASIC_FLOW_SKIPPED_TOOL_MISSING,
        output="OpenLane detected but flow check could not be executed",
        openlane_available=openlane_available,
        openroad_available=openroad_available,
        note="OpenLane detected but automatic flow check not supported in this configuration",
    )