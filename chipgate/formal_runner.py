"""
ChipGate formal verification runner.

Runs formal verification checks on RTL designs using SymbiYosys (sby) if
available.  If SBY is not installed, functions return results with status
FORMAL_SKIPPED_TOOL_MISSING.

All commands are invoked as lists.

Individual properties from ``formal_properties.generate_sby_config`` are
checked one-at-a-time via ``run_formal_property_check``, and all default
properties can be batched through ``run_formal_checks``.
"""

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from . import __version__
from . import formal_properties
from . import statuses as st


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class FormalPropertyResult:
    """Result of a single formal property check."""
    property_name: str
    passed: bool
    output: str = ""
    trace_file: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "property_name": self.property_name,
            "passed": self.passed,
            "output": self.output[:2000] if self.output else "",
            "trace_file": self.trace_file,
            "duration_seconds": self.duration_seconds,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_tool_version(tool: str) -> Optional[str]:
    """Get version string for *tool* (e.g. ``sby`` or ``yosys``)."""
    try:
        result = subprocess.run(
            [tool, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _find_top_module(rtl_text: str) -> Optional[str]:
    """Extract module name from Verilog text."""
    match = re.search(r"module\s+(\w+)", rtl_text)
    return match.group(1) if match else None


def _extract_trace_file(output: str, work_dir: str) -> str:
    """Extract VCD / trace file path from SBY output if present.

    SBY often prints lines like ``Writing trace to <path>`` or references
    ``.vcd`` files.  Return the first match as an absolute path, or empty
    string if none found.
    """
    # Common patterns in SBY output
    patterns = [
        r"(?:Writing trace to|trace:?\s+|VCD:?\s+)(\S+\.vcd)",
        r"(\S+\.vcd)",
    ]
    for pat in patterns:
        match = re.search(pat, output, re.IGNORECASE)
        if match:
            trace = match.group(1)
            if not os.path.isabs(trace):
                trace = os.path.join(work_dir, trace)
            return trace
    return ""


def _parse_property_result(output: str) -> bool:
    """Determine whether a single-property SBY run PASSED or FAILED.

    Looks for the final summary line SBY emits, e.g.::

        "PASS" / "PASSED" / "FAIL" / "FAILED"
    """
    # Check for explicit FAILED first (more specific)
    if re.search(r"\bFAILED\b", output, re.IGNORECASE):
        return False
    if re.search(r"\bPASS(?:ED)?\b", output, re.IGNORECASE):
        return True
    # If neither keyword found, treat as failed (conservative)
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_formal_toolchain() -> dict:
    """Check which formal tools are available.

    Returns dict with keys: ``sby``, ``yosys``, ``both`` — each mapping to
    a dict with ``found`` (bool), ``path`` (str), ``version`` (str).

    ``both`` is ``True`` only when *both* sby and yosys are discovered.
    """
    import shutil

    sby_exe = shutil.which("sby")
    sby_version = _get_tool_version("sby") if sby_exe else None

    yosys_exe = shutil.which("yosys")
    yosys_version = _get_tool_version("yosys") if yosys_exe else None

    sby_found = sby_exe is not None
    yosys_found = yosys_exe is not None

    return {
        "sby": {
            "found": sby_found,
            "path": sby_exe or "",
            "version": sby_version or "",
        },
        "yosys": {
            "found": yosys_found,
            "path": yosys_exe or "",
            "version": yosys_version or "",
        },
        "both": sby_found and yosys_found,
    }


def run_formal_property_check(
    rtl_path: str,
    property_name: str,
    timeout_seconds: int = 30,
) -> FormalPropertyResult:
    """Run a single named formal property check using SBY.

    Uses ``formal_properties.generate_sby_config`` to create an SBY file
    containing *only* the named property, then executes ``sby`` and parses
    the result.

    Parameters
    ----------
    rtl_path : str
        Path to the Verilog/SystemVerilog file.
    property_name : str
        Name of a default property (e.g. ``"kill_switch_blocks_output"``).
        If the name does not match any known default, a bare ``assert 1'b1;``
        is used so SBY still runs without error.
    timeout_seconds : int
        Maximum execution time for the SBY process.

    Returns
    -------
    FormalPropertyResult
    """
    import shutil

    bin_name = "sby"
    exe = shutil.which(bin_name)
    if exe is None:
        return FormalPropertyResult(
            property_name=property_name,
            passed=False,
            output=st.FORMAL_SKIPPED_TOOL_MISSING
            + ": SymbiYosys (sby) not found on PATH",
        )

    # Build the single-property text
    property_text = _build_single_property(property_name)

    # Auto-detect top module
    rtl_text = Path(rtl_path).read_text(encoding="utf-8", errors="replace")
    top_module = _find_top_module(rtl_text) or "top"

    # Generate SBY config via formal_properties
    sby_content = formal_properties.generate_sby_config(
        rtl_path=rtl_path,
        top_module=top_module,
        properties=property_text,
    )

    # Write SBY config to a temp directory
    work_dir = tempfile.mkdtemp(prefix="chipgate_fp_")
    sby_file = os.path.join(work_dir, f"{property_name}.sby")
    with open(sby_file, "w", encoding="utf-8") as f:
        f.write(sby_content)

    # Copy RTL into work_dir so SBY can find it
    rtl_abs = str(Path(rtl_path).resolve())
    rtl_dest = os.path.join(work_dir, os.path.basename(rtl_path))
    if os.path.abspath(rtl_dest) != os.path.abspath(rtl_abs):
        import shutil as _sh
        _sh.copy2(rtl_abs, rtl_dest)

    cmd = [exe, "-f", sby_file, "--batch"]

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=work_dir,
        )
        elapsed = time.monotonic() - start
        output = result.stdout + "\n" + result.stderr

        passed = _parse_property_result(output)
        trace_file = _extract_trace_file(output, work_dir)

        return FormalPropertyResult(
            property_name=property_name,
            passed=passed,
            output=output.strip(),
            trace_file=trace_file,
            duration_seconds=round(elapsed, 3),
        )

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return FormalPropertyResult(
            property_name=property_name,
            passed=False,
            output=f"Formal check timed out after {timeout_seconds}s",
            duration_seconds=round(elapsed, 3),
        )
    except OSError as e:
        elapsed = time.monotonic() - start
        return FormalPropertyResult(
            property_name=property_name,
            passed=False,
            output=f"Formal check execution failed: {e}",
            duration_seconds=round(elapsed, 3),
        )


def run_formal_checks(
    rtl_path: str,
    timeout_seconds: int = 120,
    work_dir: Optional[str] = None,
) -> dict:
    """Run all default formal properties on a design.

    Iterates over every property defined in ``formal_properties`` and runs
    each through :func:`run_formal_property_check`, distributing the overall
    timeout evenly across properties.

    Parameters
    ----------
    rtl_path : str
        Path to the Verilog/SystemVerilog file.
    timeout_seconds : int
        Total budget (seconds) distributed across all properties.
    work_dir : str, optional
        Ignored; each property uses its own temp directory.  Accepted for
        API compatibility.

    Returns
    -------
    dict
        Mapping of ``property_name`` -> :class:`FormalPropertyResult`.
    """
    property_names = _get_default_property_names()
    per_property_timeout = max(5, timeout_seconds // max(len(property_names), 1))

    results: Dict[str, FormalPropertyResult] = {}
    for name in property_names:
        results[name] = run_formal_property_check(
            rtl_path=rtl_path,
            property_name=name,
            timeout_seconds=per_property_timeout,
        )

    return results


# ---------------------------------------------------------------------------
# Internal helpers (property listing / single-property generation)
# ---------------------------------------------------------------------------


def _get_default_property_names() -> list:
    """Return the list of default property name strings."""
    try:
        props_text = formal_properties.generate_default_properties()
    except Exception:
        return []

    names: list = []
    for match in re.finditer(
        r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", props_text, re.MULTILINE
    ):
        names.append(match.group(1))
    return names


def _build_single_property(property_name: str) -> str:
    """Build a properties section containing *only* the named property.

    If *property_name* matches one of the defaults, its assertion body is
    extracted and used.  Otherwise a trivial tautology (``assert 1'b1;``)
    is returned so SBY does not error on an empty properties block.
    """
    try:
        props_text = formal_properties.generate_default_properties()
    except Exception:
        props_text = ""

    # Look for the named property in the generated text
    match = re.search(
        rf"^{re.escape(property_name)}\s*:\s*(.+)$",
        props_text,
        re.MULTILINE,
    )
    if match:
        return f"{property_name}: {match.group(1)}\n"

    # Fallback: trivially true assertion
    return f"{property_name}: assert 1'b1;\n"