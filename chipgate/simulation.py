"""
ChipGate simulation runner.

Provides infrastructure for running simulations via cocotb or Verilator.
For the public MVP, this module is a placeholder that documents the integration
path without requiring external simulators.
"""

import shutil
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SimulationResult:
    """Result of a simulation run."""
    tool: str
    available: bool
    passed: bool
    test_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    output: str = ""
    errors: List[str] = field(default_factory=list)
    command: str = ""


def cocotb_available() -> bool:
    """Check if cocotb is importable."""
    try:
        import cocotb  # noqa: F401
        return True
    except ImportError:
        return False


def verilator_available() -> bool:
    """Check if Verilator is installed."""
    return shutil.which("verilator") is not None


def run_simulation(
    file_path: str,
    tool: str = "auto",
    testbench: Optional[str] = None,
    timeout: int = 120,
) -> SimulationResult:
    """
    Run simulation on a Verilog file.

    Currently a placeholder — full simulation support is planned for
    future integration with cocotb and Verilator.

    Args:
        file_path: Path to the Verilog file to simulate.
        tool: Simulator to use ('auto', 'cocotb', 'verilator').
        testbench: Optional path to a testbench file.
        timeout: Maximum simulation time in seconds.

    Returns:
        SimulationResult with availability status and any results.
    """
    if tool == "auto":
        # Prefer cocotb, fall back to Verilator
        if cocotb_available():
            tool = "cocotb"
        elif verilator_available():
            tool = "verilator"
        else:
            tool = "none"

    if tool == "none" or (tool not in ("cocotb", "verilator")):
        return SimulationResult(
            tool=tool,
            available=False,
            passed=False,
            errors=[
                "No simulator available. Install cocotb or Verilator for simulation support.",
                "  cocotb:  pip install cocotb",
                "  Verilator: https://verilator.org/guide/latest/install.html",
            ],
        )

    # cocotb integration (future)
    if tool == "cocotb":
        return SimulationResult(
            tool="cocotb",
            available=True,
            passed=False,
            errors=["cocotb simulation integration is planned for a future release."],
        )

    # Verilator simulation (future)
    if tool == "verilator":
        return SimulationResult(
            tool="verilator",
            available=True,
            passed=False,
            errors=["Verilator simulation integration is planned for a future release."],
        )

    return SimulationResult(
        tool="none",
        available=False,
        passed=False,
        errors=["No supported simulator configured."],
    )