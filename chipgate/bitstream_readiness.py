"""
ChipGate bitstream readiness classification.

If FPGA toolchain tools (yosys, nextpnr, icestorm) are present,
attempt a full synthesis + place-and-route flow and classify the result
as BITSTREAM_READY, BITSTREAM_FAIL, or BITSTREAM_SKIPPED_TOOL_MISSING.

Does NOT claim hardware deployment readiness.
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
class BitstreamReadinessResult:
    """Result of bitstream readiness check."""
    status: str
    output: str = ""
    command: str = ""
    tool_version: Optional[str] = None
    tools_available: Dict[str, bool] = None

    def __post_init__(self):
        if self.tools_available is None:
            self.tools_available = {}

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "output": self.output[:2000] if self.output else "",
            "command": self.command,
            "tool_version": self.tool_version,
            "tools_available": self.tools_available,
        }


def _check_tools() -> Dict[str, Optional[str]]:
    """Check for required bitstream tools."""
    tools: Dict[str, Optional[str]] = {}
    for name, bins in [
        ("yosys", ["yosys"]),
        ("nextpnr", ["nextpnr-ice40", "nextpnr-ecp5", "nextpnr-xilinx", "nextpnr-generic"]),
        ("icestorm", ["icepack"]),
        ("openFPGALoader", ["openFPGALoader"]),
    ]:
        for bin_name in bins:
            exe = shutil.which(bin_name)
            if exe is not None:
                tools[name] = exe
                break
        else:
            tools[name] = None
    return tools


def _get_tool_versions(tools: Dict[str, Optional[str]]) -> Optional[str]:
    """Collect version info from available tools."""
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


def check_bitstream_readiness(
    rtl_path: str,
    fpga_family: str = "ice40",
    timeout_seconds: int = 120,
    work_dir: Optional[str] = None,
) -> BitstreamReadinessResult:
    """
    Check bitstream readiness by running synthesis + place-and-route + pack.

    Steps:
    1. Synthesize with Yosys (target FPGA family)
    2. Place-and-route with nextpnr
    3. Pack with icepack (if available)
    4. Classify result

    Does NOT program any physical board.
    Does NOT claim hardware deployment readiness.

    Args:
        rtl_path: Path to the Verilog file.
        fpga_family: FPGA family (default: "ice40").
        timeout_seconds: Maximum execution time per tool.
        work_dir: Optional working directory.

    Returns:
        BitstreamReadinessResult with status and output.
    """
    tools = _check_tools()
    tools_available = {name: (exe is not None) for name, exe in tools.items()}

    yosys_exe = tools.get("yosys")
    nextpnr_exe = tools.get("nextpnr")
    icepack_exe = tools.get("icestorm")

    # Need at least yosys and nextpnr
    if yosys_exe is None or nextpnr_exe is None:
        missing = []
        if yosys_exe is None:
            missing.append("yosys")
        if nextpnr_exe is None:
            missing.append("nextpnr")
        return BitstreamReadinessResult(
            status=st.BITSTREAM_SKIPPED_TOOL_MISSING,
            output=f"Bitstream readiness skipped: {', '.join(missing)} not found",
            tools_available=tools_available,
        )

    tool_version = _get_tool_versions(tools)

    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="chipgate_bs_")

    rtl_abs = str(Path(rtl_path).resolve())
    json_out = os.path.join(work_dir, "synth.json")
    pnr_out = os.path.join(work_dir, "pnr.json")
    asc_out = os.path.join(work_dir, "output.asc")

    commands_run: list[str] = []
    all_output = ""

    # Step 1: Yosys synthesis
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
    commands_run.append(" ".join(yosys_cmd))

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
            return BitstreamReadinessResult(
                status=st.BITSTREAM_FAIL,
                output=all_output.strip()[:2000],
                command="; ".join(commands_run),
                tool_version=tool_version,
                tools_available=tools_available,
            )
    except subprocess.TimeoutExpired:
        return BitstreamReadinessResult(
            status=st.BITSTREAM_FAIL,
            output=f"Yosys timed out after {timeout_seconds}s",
            command="; ".join(commands_run),
            tool_version=tool_version,
            tools_available=tools_available,
        )

    # Step 2: nextpnr place-and-route
    nextpnr_bin = "nextpnr-" + fpga_family
    nextpnr_cmd = [
        nextpnr_bin,
        "--json", json_out,
        "--json-output", pnr_out,
    ]
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
            return BitstreamReadinessResult(
                status=st.BITSTREAM_FAIL,
                output=all_output.strip()[:2000],
                command="; ".join(commands_run),
                tool_version=tool_version,
                tools_available=tools_available,
            )
    except subprocess.TimeoutExpired:
        return BitstreamReadinessResult(
            status=st.BITSTREAM_FAIL,
            output=f"nextpnr timed out after {timeout_seconds}s",
            command="; ".join(commands_run),
            tool_version=tool_version,
            tools_available=tools_available,
        )

    # Step 3: icepack (optional — for actual bitstream generation)
    if icepack_exe is not None:
        icepack_cmd = [icepack_exe, pnr_out, asc_out]
        commands_run.append(" ".join(icepack_cmd))
        try:
            pack_result = subprocess.run(
                icepack_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=work_dir,
            )
            all_output += "\n" + pack_result.stdout + "\n" + pack_result.stderr

            if pack_result.returncode != 0:
                return BitstreamReadinessResult(
                    status=st.BITSTREAM_FAIL,
                    output=all_output.strip()[:2000],
                    command="; ".join(commands_run),
                    tool_version=tool_version,
                    tools_available=tools_available,
                )
        except subprocess.TimeoutExpired:
            return BitstreamReadinessResult(
                status=st.BITSTREAM_FAIL,
                output=f"icepack timed out after {timeout_seconds}s",
                command="; ".join(commands_run),
                tool_version=tool_version,
                tools_available=tools_available,
            )

    # If we got here, synthesis + PnR (and optionally pack) all passed
    return BitstreamReadinessResult(
        status=st.BITSTREAM_READY,
        output=all_output.strip()[:2000],
        command="; ".join(commands_run),
        tool_version=tool_version,
        tools_available=tools_available,
    )