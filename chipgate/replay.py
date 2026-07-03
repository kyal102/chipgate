"""
ChipGate replay command output.

Generates deterministic replay commands that allow exact reproduction
of a verification run. This enables auditable, reproducible verification.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .scanner import ScanResult
from . import __version__


@dataclass
class ReplayCommand:
    """A single replay command with metadata."""
    command: str
    description: str
    tool: str = "chipgate"
    version: str = ""


def generate_replay_commands(scan_result: ScanResult) -> List[ReplayCommand]:
    """
    Generate a set of replay commands for a scan result.

    These commands can be saved and re-executed to exactly reproduce
    the verification run.
    """
    commands: List[ReplayCommand] = []
    file_path = scan_result.file

    # Core scan command
    commands.append(ReplayCommand(
        command=f"python -m chipgate scan {file_path}",
        description="Re-run the core RTL safety scan",
        tool="chipgate",
        version=__version__,
    ))

    # Scan with JSON output
    commands.append(ReplayCommand(
        command=f"python -m chipgate scan {file_path} --json",
        description="Re-run scan with structured JSON output",
        tool="chipgate",
        version=__version__,
    ))

    # Scan with evidence pack
    commands.append(ReplayCommand(
        command=f"python -m chipgate scan {file_path} --evidence",
        description="Re-run scan and generate evidence pack",
        tool="chipgate",
        version=__version__,
    ))

    # Scan with lint (optional)
    commands.append(ReplayCommand(
        command=f"python -m chipgate lint {file_path}",
        description="Re-run with external lint (requires Verilator)",
        tool="chipgate+verilator",
        version=__version__,
    ))

    # List rules for reference
    commands.append(ReplayCommand(
        command="python -m chipgate --list-rules",
        description="List all rules that were checked",
        tool="chipgate",
        version=__version__,
    ))

    return commands


def format_replay_script(commands: List[ReplayCommand], shell: str = "bash") -> str:
    """
    Format replay commands as an executable shell script.

    Args:
        commands: List of ReplayCommand objects.
        shell: Shell type ('bash' or 'sh').

    Returns:
        A shell script string.
    """
    shebang = f"#!/usr/bin/env {shell}\n"
    header = (
        f"# ChipGate Replay Script\n"
        f"# Generated for: {commands[0].command.split()[-1] if commands else 'unknown'}\n"
        f"# ChipGate version: {__version__}\n"
        f"# This script reproduces the verification run.\n"
        f"#\n"
        f"# {scan_result.public_wording if hasattr(commands, 'scan_result') else ''}\n"
        f"\n"
        f'set -e\n\n'
    )

    body = ""
    for i, cmd in enumerate(commands, 1):
        body += f"# Step {i}: {cmd.description}\n"
        body += f'echo ">>> Step {i}: {cmd.description}"\n'
        body += f"{cmd.command}\n"
        body += f'echo ""\n\n'

    return shebang + header + body


def format_replay_script_from_result(scan_result: ScanResult, shell: str = "bash") -> str:
    """
    Format replay commands from a ScanResult as an executable shell script.
    """
    commands = generate_replay_commands(scan_result)

    shebang = f"#!/usr/bin/env {shell}\n"
    header = (
        f"# ChipGate Replay Script\n"
        f"# Generated for: {scan_result.file}\n"
        f"# Module: {scan_result.module_name}\n"
        f"# ChipGate version: {__version__}\n"
        f"# Certificate hash: {scan_result.certificate_hash}\n"
        f"#\n"
        f"# {scan_result.public_wording}\n"
        f"\n"
        f'set -e\n\n'
    )

    body = ""
    for i, cmd in enumerate(commands, 1):
        body += f"# Step {i}: {cmd.description}\n"
        body += f'echo ">>> Step {i}: {cmd.description}"\n'
        body += f"{cmd.command}\n"
        body += f'echo ""\n\n'

    return shebang + header + body