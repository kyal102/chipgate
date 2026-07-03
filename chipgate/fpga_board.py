"""
ChipGate FPGA board-level synthesis and place-and-route wrapper.

Separates FPGA synthesis and place-and-route into distinct stages
for the FPGABoardBench pipeline, unlike fpga_flow.py which combines
them into a single stage.

Stages:
  1. FPGA Synthesis: Yosys synthesis targeting a specific FPGA family
  2. Place-and-Route: nextpnr placement and routing

Both stages are optional and gracefully skipped when tools are missing.

Does NOT program any physical board.
All commands are invoked as lists.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from . import statuses as st


@dataclass
class FPGASynthResult:
    """Result of FPGA synthesis stage."""
    status: str
    output: str = ""
    command: str = ""
    tool_version: Optional[str] = None
    yosys_available: bool = False
    cell_count: int = 0
    wire_count: int = 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "output": self.output[:2000] if self.output else "",
            "command": self.command,
            "tool_version": self.tool_version,
            "yosys_available": self.yosys_available,
            "cell_count": self.cell_count,
            "wire_count": self.wire_count,
        }


@dataclass
class PlaceRouteResult:
    """Result of FPGA place-and-route stage."""
    status: str
    output: str = ""
    command: str = ""
    tool_version: Optional[str] = None
    nextpnr_available: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "output": self.output[:2000] if self.output else "",
            "command": self.command,
            "tool_version": self.tool_version,
            "nextpnr_available": self.nextpnr_available,
        }


def _find_executable(bins: list) -> Optional[str]:
    """Find the first available executable from a list of names."""
    for name in bins:
        exe = shutil.which(name)
        if exe is not None:
            return exe
    return None


def _get_version(exe: str) -> Optional[str]:
    """Get version string from a tool."""
    try:
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def run_fpga_synthesis(
    rtl_path: str,
    fpga_family: str = "ice40",
    timeout_seconds: int = 120,
    work_dir: Optional[str] = None,
) -> FPGASynthResult:
    """
    Run FPGA-targeted synthesis using Yosys.

    Args:
        rtl_path: Path to the Verilog file.
        fpga_family: Target FPGA family (e.g. "ice40", "ecp5", "xilinx").
        timeout_seconds: Maximum execution time.
        work_dir: Optional working directory.

    Returns:
        FPGASynthResult with synthesis status, output, and cell/wire counts.
    """
    yosys_exe = _find_executable(["yosys"])
    yosys_available = yosys_exe is not None

    if not yosys_available:
        return FPGASynthResult(
            status=st.FPGA_SYNTH_SKIPPED_TOOL_MISSING,
            output="FPGA synthesis skipped: yosys not found",
            yosys_available=False,
        )

    tool_version = _get_version(yosys_exe)

    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="chipgate_fpga_synth_")

    rtl_abs = str(Path(rtl_path).resolve())
    json_out = os.path.join(work_dir, "fpga_synth.json")

    synth_target = f"synth_{fpga_family}" if fpga_family != "generic" else "synth"
    yosys_script = f"""
read_verilog {rtl_abs}
hierarchy -auto-top
proc
clean
flatten
{synth_target} -top
write_json {json_out}
"""
    yosys_cmd = [yosys_exe, "-p", yosys_script.strip()]

    try:
        yosys_result = subprocess.run(
            yosys_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=work_dir,
        )
        output = (yosys_result.stdout + "\n" + yosys_result.stderr).strip()

        if yosys_result.returncode != 0:
            return FPGASynthResult(
                status=st.FPGA_SYNTH_FAIL,
                output=output[:2000],
                command=" ".join(yosys_cmd),
                tool_version=tool_version,
                yosys_available=True,
            )

        # Parse cell and wire counts from Yosys stats output
        cell_count = 0
        wire_count = 0
        for line in yosys_result.stdout.split("\n"):
            line_lower = line.lower().strip()
            if "Number of cells:" in line_lower:
                cell_count = int(line.split(":")[-1].strip())
            elif "Number of wires:" in line_lower:
                wire_count = int(line.split(":")[-1].strip())

        return FPGASynthResult(
            status=st.FPGA_SYNTH_PASS,
            output=output[:2000],
            command=" ".join(yosys_cmd),
            tool_version=tool_version,
            yosys_available=True,
            cell_count=cell_count,
            wire_count=wire_count,
        )

    except subprocess.TimeoutExpired:
        return FPGASynthResult(
            status=st.FPGA_SYNTH_FAIL,
            output=f"Yosys timed out after {timeout_seconds}s",
            command=" ".join(yosys_cmd),
            tool_version=tool_version,
            yosys_available=True,
        )
    except OSError as e:
        return FPGASynthResult(
            status=st.FPGA_SYNTH_FAIL,
            output=f"Yosys failed: {e}",
            command=" ".join(yosys_cmd),
            tool_version=tool_version,
            yosys_available=True,
        )


def run_place_and_route(
    synth_json_path: str,
    fpga_family: str = "ice40",
    fpga_device: str = "lp384",
    package: str = "qn32",
    timeout_seconds: int = 120,
    work_dir: Optional[str] = None,
) -> PlaceRouteResult:
    """
    Run place-and-route using nextpnr.

    Args:
        synth_json_path: Path to the Yosys synthesis JSON output.
        fpga_family: Target FPGA family.
        fpga_device: Target device (e.g. "lp384", "hx1k").
        package: Package name (e.g. "qn32", "tq144").
        timeout_seconds: Maximum execution time.
        work_dir: Optional working directory.

    Returns:
        PlaceRouteResult with status and output.
    """
    nextpnr_bins = {
        "ice40": ["nextpnr-ice40"],
        "ecp5": ["nextpnr-ecp5"],
        "xilinx": ["nextpnr-xilinx"],
        "generic": ["nextpnr-generic"],
    }
    exe_list = nextpnr_bins.get(fpga_family, ["nextpnr-generic"])
    nextpnr_exe = _find_executable(exe_list)
    nextpnr_available = nextpnr_exe is not None

    if not nextpnr_available:
        return PlaceRouteResult(
            status=st.PLACE_ROUTE_SKIPPED_TOOL_MISSING,
            output=f"Place-and-route skipped: nextpnr not found "
                   f"(looked for: {', '.join(exe_list)})",
            nextpnr_available=False,
        )

    tool_version = _get_version(nextpnr_exe)

    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="chipgate_pnr_")

    pnr_out = os.path.join(work_dir, "pnr.json")

    nextpnr_cmd = [
        nextpnr_exe,
        "--json", synth_json_path,
        "--json-output", pnr_out,
    ]

    # Add device-specific options
    if fpga_family == "ice40":
        nextpnr_cmd.extend([f"--{fpga_device}", "--package", package])

    try:
        pnr_result = subprocess.run(
            nextpnr_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=work_dir,
        )
        output = (pnr_result.stdout + "\n" + pnr_result.stderr).strip()

        if pnr_result.returncode != 0:
            return PlaceRouteResult(
                status=st.PLACE_ROUTE_FAIL,
                output=output[:2000],
                command=" ".join(nextpnr_cmd),
                tool_version=tool_version,
                nextpnr_available=True,
            )

        return PlaceRouteResult(
            status=st.PLACE_ROUTE_PASS,
            output=output[:2000],
            command=" ".join(nextpnr_cmd),
            tool_version=tool_version,
            nextpnr_available=True,
        )

    except subprocess.TimeoutExpired:
        return PlaceRouteResult(
            status=st.PLACE_ROUTE_FAIL,
            output=f"nextpnr timed out after {timeout_seconds}s",
            command=" ".join(nextpnr_cmd),
            tool_version=tool_version,
            nextpnr_available=True,
        )
    except OSError as e:
        return PlaceRouteResult(
            status=st.PLACE_ROUTE_FAIL,
            output=f"nextpnr failed: {e}",
            command=" ".join(nextpnr_cmd),
            tool_version=tool_version,
            nextpnr_available=True,
        )