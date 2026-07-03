"""
ChipGate FPGA readiness flow.

Attempts a minimal FPGA place-and-route flow using Yosys + nextpnr
if both tools are installed. If tools are missing, returns
FPGA_FLOW_SKIPPED_TOOL_MISSING.

All commands are invoked as lists.
Does not require an actual FPGA board.
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
class FPGAResult:
    """Result of an FPGA readiness flow run."""
    status: str
    output: str = ""
    command: str = ""
    tool_version: Optional[str] = None
    yosys_available: bool = False
    nextpnr_available: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "output": self.output[:2000] if self.output else "",
            "command": self.command,
            "tool_version": self.tool_version,
            "yosys_available": self.yosys_available,
            "nextpnr_available": self.nextpnr_available,
        }


def _check_tools() -> Dict[str, Optional[str]]:
    """Check for Yosys and nextpnr availability."""
    tools = {}
    for name, bins in [
        ("yosys", ["yosys"]),
        ("nextpnr", ["nextpnr-ice40", "nextpnr-ecp5", "nextpnr-xilinx", "nextpnr-generic"]),
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
    """Get version info from available tools."""
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
        except (subprocess.TimeoutExpired, OSError):
            pass
    return "; ".join(versions) if versions else None


def run_fpga_flow(
    rtl_path: str,
    fpga_family: str = "ice40",
    timeout_seconds: int = 120,
    work_dir: Optional[str] = None,
) -> FPGAResult:
    """
    Attempt a minimal FPGA readiness flow.

    Steps:
    1. Synthesize with Yosys (ice40 family)
    2. Place-and-route with nextpnr
    3. Classify result

    Does not program any physical board.

    Args:
        rtl_path: Path to the Verilog file.
        fpga_family: FPGA family (default: "ice40").
        timeout_seconds: Maximum execution time per tool.
        work_dir: Optional working directory.

    Returns:
        FPGAResult with status and output.
    """
    tools = _check_tools()
    yosys_exe = tools.get("yosys")
    nextpnr_exe = tools.get("nextpnr")

    yosys_available = yosys_exe is not None
    nextpnr_available = nextpnr_exe is not None

    if not yosys_available or not nextpnr_available:
        missing = []
        if not yosys_available:
            missing.append("Yosys")
        if not nextpnr_available:
            missing.append("nextpnr")
        return FPGAResult(
            status=st.FPGA_FLOW_SKIPPED_TOOL_MISSING,
            output=f"FPGA flow skipped: {', '.join(missing)} not found",
            yosys_available=yosys_available,
            nextpnr_available=nextpnr_available,
        )

    tool_version = _get_tool_versions(tools)

    # Create work directory
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="chipgate_fpga_")

    rtl_abs = str(Path(rtl_path).resolve())
    json_out = os.path.join(work_dir, "synth.json")

    # Step 1: Yosys synthesis for FPGA
    yosys_script = f"""
read_verilog {rtl_abs}
hierarchy -auto-top
proc
clean
flatten
synth_ice40 -top
write_json {json_out}
"""
    yosys_cmd = [yosys_exe, "-p", yosys_script.strip()]
    commands_run = [" ".join(yosys_cmd)]
    all_output = ""

    try:
        yosys_result = subprocess.run(
            yosys_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=work_dir,
        )
        all_output += yosys_result.stdout + "\n" + yosys_result.stderr

        if yosys_result.returncode != 0 or not Path(json_out).exists():
            return FPGAResult(
                status=st.FPGA_FLOW_FAIL,
                output=all_output.strip()[:2000],
                command="; ".join(commands_run),
                tool_version=tool_version,
                yosys_available=yosys_available,
                nextpnr_available=nextpnr_available,
            )
    except subprocess.TimeoutExpired:
        return FPGAResult(
            status=st.FPGA_FLOW_FAIL,
            output=f"Yosys timed out after {timeout_seconds}s",
            command="; ".join(commands_run),
            tool_version=tool_version,
            yosys_available=yosys_available,
            nextpnr_available=nextpnr_available,
        )

    # Step 2: nextpnr place-and-route
    # Detect nextpnr binary name for the family
    nextpnr_bin = "nextpnr-" + fpga_family
    nextpnr_cmd = [
        nextpnr_bin,
        "--json", json_out,
        "--json-output", os.path.join(work_dir, "pnr.json"),
    ]
    # Add family-specific options
    if fpga_family == "ice40":
        nextpnr_cmd.extend(["--lp384", "--package", "qn32"])

    commands_run.append(" ".join(nextpnr_cmd))

    try:
        pnr_result = subprocess.run(
            nextpnr_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=work_dir,
        )
        all_output += "\n" + pnr_result.stdout + "\n" + pnr_result.stderr

        if pnr_result.returncode != 0:
            return FPGAResult(
                status=st.FPGA_FLOW_FAIL,
                output=all_output.strip()[:2000],
                command="; ".join(commands_run),
                tool_version=tool_version,
                yosys_available=yosys_available,
                nextpnr_available=nextpnr_available,
            )

        return FPGAResult(
            status=st.FPGA_FLOW_PASS,
            output=all_output.strip()[:2000],
            command="; ".join(commands_run),
            tool_version=tool_version,
            yosys_available=yosys_available,
            nextpnr_available=nextpnr_available,
        )

    except subprocess.TimeoutExpired:
        return FPGAResult(
            status=st.FPGA_FLOW_FAIL,
            output=f"nextpnr timed out after {timeout_seconds}s",
            command="; ".join(commands_run),
            tool_version=tool_version,
            yosys_available=yosys_available,
            nextpnr_available=nextpnr_available,
        )
    except OSError as e:
        return FPGAResult(
            status=st.FPGA_FLOW_FAIL,
            output=f"nextpnr failed: {e}",
            command="; ".join(commands_run),
            tool_version=tool_version,
            yosys_available=yosys_available,
            nextpnr_available=nextpnr_available,
        )