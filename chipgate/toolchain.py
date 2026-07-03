"""
ChipGate toolchain detection and version checking.

Detects whether optional open-source EDA tools are installed and available.
No external tool is required — all tools are optional and gracefully skipped
when missing.

Tools checked:
- Verilator (lint and simulation)
- Yosys (synthesis)
- SymbiYosys / sby (formal verification)
- nextpnr (FPGA place-and-route)
- OpenLane / OpenROAD (ASIC flow)
"""

import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class ToolStatus:
    """Status of a single tool."""
    name: str
    found: bool
    path: Optional[str] = None
    version: Optional[str] = None
    note: str = ""


@dataclass
class ToolchainReport:
    """Report of all detected tools."""
    tools: Dict[str, ToolStatus] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            name: {
                "found": ts.found,
                "path": ts.path,
                "version": ts.version,
                "note": ts.note,
            }
            for name, ts in self.tools.items()
        }

    @property
    def coverage(self) -> float:
        """Fraction of tools found (0.0 to 1.0)."""
        if not self.tools:
            return 0.0
        found = sum(1 for ts in self.tools.values() if ts.found)
        return found / len(self.tools)

    @property
    def found_count(self) -> int:
        return sum(1 for ts in self.tools.values() if ts.found)

    @property
    def total_count(self) -> int:
        return len(self.tools)


# Tool name -> (executable name, version flag, version parse prefix)
_TOOL_DEFS = {
    "verilator": ("verilator", ["--version"], "Verilator"),
    "yosys": ("yosys", ["--version"], "Yosys"),
    "symbiyosys": ("sby", ["--version"], "sby"),
    "nextpnr": ("nextpnr-ice40", ["--version"], "nextpnr"),
    "openlane": ("openlane", ["--version"], "OpenLane"),
    "openroad": ("openroad", ["--version"], "OpenROAD"),
}


def _run_version_cmd(executable: str, args: List[str]) -> Optional[str]:
    """Run a version command and return the first line of output, or None."""
    try:
        result = subprocess.run(
            [executable] + args,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _find_executable(name: str) -> Optional[str]:
    """Find an executable on PATH. Returns path or None."""
    return shutil.which(name)


def check_toolchain() -> ToolchainReport:
    """
    Check all supported tools and return a ToolchainReport.

    This function is safe to call in any environment. It does not require
    any external tools to be installed.
    """
    report = ToolchainReport()

    for tool_key, (exe_name, version_args, version_prefix) in _TOOL_DEFS.items():
        exe_path = _find_executable(exe_name)
        if exe_path is not None:
            version_line = _run_version_cmd(exe_path, version_args)
            report.tools[tool_key] = ToolStatus(
                name=tool_key,
                found=True,
                path=exe_path,
                version=version_line,
                note=f"found at {exe_path}",
            )
        else:
            report.tools[tool_key] = ToolStatus(
                name=tool_key,
                found=False,
                note="skipped (not found on PATH)",
            )

    return report


def format_toolchain_status(report: ToolchainReport) -> str:
    """Format toolchain status for terminal output."""
    lines = ["ChipGate SiliconReadinessBench — Toolchain Status", ""]
    for name, ts in report.tools.items():
        if ts.found:
            status = f"found {ts.path}"
            if ts.version:
                status += f" ({ts.version})"
        else:
            status = "skipped"
        lines.append(f"  {name.capitalize():<16s} {status}")
    lines.append("")
    lines.append(f"  Toolchain coverage: {report.found_count}/{report.total_count} "
                 f"({report.coverage:.0%})")
    return "\n".join(lines)