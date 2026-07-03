"""
ChipGate Yosys synthesis flow.

Runs Yosys synthesis on a Verilog file if Yosys is installed.
If Yosys is not installed, returns SYNTHESIS_SKIPPED_TOOL_MISSING.

All commands are invoked as lists.
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from . import statuses as st


@dataclass
class SynthesisResult:
    """Result of a Yosys synthesis run."""
    status: str
    cell_count: int = 0
    wire_count: int = 0
    process_count: int = 0
    memory_count: int = 0
    netlist_text: str = ""
    output: str = ""
    command: str = ""
    tool_version: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "cell_count": self.cell_count,
            "wire_count": self.wire_count,
            "process_count": self.process_count,
            "memory_count": self.memory_count,
            "netlist_text": self.netlist_text[:2000] if self.netlist_text else "",
            "output": self.output[:2000] if self.output else "",
            "command": self.command,
            "tool_version": self.tool_version,
        }


def _extract_stats(output: str) -> Dict[str, int]:
    """
    Extract statistics from Yosys output.

    Yosys print_stats output looks like:
      === design_top ===
         Number of cells:              42
         Number of wires:              28
         ...
    """
    stats = {
        "cell_count": 0,
        "wire_count": 0,
        "process_count": 0,
        "memory_count": 0,
    }

    # Try to match "Number of cells: N" pattern
    cell_match = re.search(r"Number of cells:\s+(\d+)", output)
    if cell_match:
        stats["cell_count"] = int(cell_match.group(1))

    wire_match = re.search(r"Number of wires:\s+(\d+)", output)
    if wire_match:
        stats["wire_count"] = int(wire_match.group(1))

    # Memory cells
    mem_match = re.search(r"Number of.*memory.*cells:\s+(\d+)", output, re.IGNORECASE)
    if mem_match:
        stats["memory_count"] = int(mem_match.group(1))

    # Process cells (in Yosys stats)
    proc_match = re.search(r"Number of process cells:\s+(\d+)", output)
    if proc_match:
        stats["process_count"] = int(proc_match.group(1))

    return stats


def _get_yosys_version() -> Optional[str]:
    """Get Yosys version string."""
    try:
        result = subprocess.run(
            ["yosys", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def run_yosys_synthesis(
    rtl_path: str,
    yosys_bin: Optional[str] = None,
    top_module: Optional[str] = None,
    timeout_seconds: int = 120,
    work_dir: Optional[str] = None,
) -> SynthesisResult:
    """
    Run Yosys synthesis on a Verilog file.

    Args:
        rtl_path: Path to the Verilog/SystemVerilog file.
        yosys_bin: Optional path to yosys binary (default: "yosys").
        top_module: Optional top module name.
        timeout_seconds: Maximum execution time.
        work_dir: Optional working directory for output files.

    Returns:
        SynthesisResult with status, stats, and netlist.
    """
    bin_name = yosys_bin or "yosys"
    exe = shutil.which(bin_name)
    if exe is None:
        return SynthesisResult(
            status=st.SYNTHESIS_SKIPPED_TOOL_MISSING,
            output="Yosys not found on PATH",
        )

    version = _get_yosys_version()

    # Build Yosys script
    rtl_abs = str(Path(rtl_path).resolve())
    script_lines = [
        f"read_verilog {rtl_abs}",
    ]
    if top_module:
        script_lines.append(f"hierarchy -top {top_module}")
    else:
        script_lines.append("hierarchy -auto-top")
    script_lines.extend([
        "proc",
        "clean",
        "flatten",
        "opt",
        "memory_map",
        "opt",
        "synth -top",
        "clean",
        "print_stats",
        "stat",
    ])

    yosys_script = "\n".join(script_lines)

    cmd = [exe, "-p", yosys_script]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=work_dir,
        )
        output = result.stdout + "\n" + result.stderr
        stats = _extract_stats(output)

        if result.returncode != 0:
            status = st.SYNTHESIS_FAIL
        else:
            status = st.SYNTHESIS_PASS

        # Try to extract netlist from write_verilog output
        netlist = ""
        # Look for the synthesized netlist section
        netlist_match = re.search(
            r"(\\n|\n)(module\s+\w+.*?endmodule)",
            output,
            re.DOTALL,
        )
        if netlist_match:
            netlist = netlist_match.group(1).strip()

        return SynthesisResult(
            status=status,
            cell_count=stats["cell_count"],
            wire_count=stats["wire_count"],
            process_count=stats["process_count"],
            memory_count=stats["memory_count"],
            netlist_text=netlist,
            output=output.strip(),
            command=" ".join(cmd),
            tool_version=version,
        )

    except subprocess.TimeoutExpired:
        return SynthesisResult(
            status=st.SYNTHESIS_FAIL,
            output=f"Yosys synthesis timed out after {timeout_seconds}s",
            command=" ".join(cmd),
            tool_version=version,
        )
    except OSError as e:
        return SynthesisResult(
            status=st.SYNTHESIS_FAIL,
            output=f"Yosys execution failed: {e}",
            command=" ".join(cmd),
            tool_version=version,
        )


def parse_yosys_stats(output: str) -> Dict[str, int]:
    """
    Parse Yosys output to extract synthesis statistics.
    Useful for testing with mocked output.
    """
    return _extract_stats(output)