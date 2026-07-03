"""
ChipGate RealToolchainCI — CI matrix and command orchestration.

Runs the full CI pipeline: toolchain detection, hygiene checks,
optional real tool stages (Verilator, Yosys, SymbiYosys, OpenLane, OpenROAD),
demo benchmarks, and evidence collection.

Does not guarantee silicon correctness, fabrication readiness, timing
signoff, physical safety, real power or real area.
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, statuses as st
from .ci_toolchain import (
    detect_toolchain,
    run_verilator_stage,
    run_yosys_stage,
    run_symbiyosys_stage,
    run_openlane_stage,
    run_openroad_stage,
    run_hygiene_checks,
    StageResult,
    HygieneResult,
)


# ── Demo commands that don't require EDA tools ───────────────────────────────

_DEMO_COMMANDS = [
    ("bench", ["--demo"]),
    ("longevity", ["--demo"]),
    ("synth", ["--demo"]),
    ("silicon", ["--demo"]),
    ("fpga", ["--demo"]),
    ("tinytapeout", ["--demo"]),
    ("physical", ["--demo"]),
]


@dataclass
class CIResult:
    """Top-level CI result."""
    overall_status: str = st.CI_PASS
    timestamp_utc: str = ""
    mode: str = "quick"  # quick / full
    toolchain_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    hygiene: Dict[str, Any] = field(default_factory=dict)
    stages: List[Dict[str, Any]] = field(default_factory=list)
    demo_results: List[Dict[str, str]] = field(default_factory=list)
    python_tests_passed: int = 0
    python_tests_failed: int = 0
    toolchain_tools_found: int = 0
    toolchain_tools_missing: int = 0
    artifacts_uploaded: int = 0
    evidence_packs_created: int = 0
    hashes_created: int = 0
    ci_replay_match_rate: float = 1.0
    public_wording: str = ""
    limitation: str = ""

    def to_dict(self) -> dict:
        return {
            "overall_status": self.overall_status,
            "timestamp_utc": self.timestamp_utc,
            "mode": self.mode,
            "toolchain_status": self.toolchain_status,
            "hygiene": self.hygiene,
            "stages": self.stages,
            "demo_results": self.demo_results,
            "python_tests_passed": self.python_tests_passed,
            "python_tests_failed": self.python_tests_failed,
            "toolchain_tools_found": self.toolchain_tools_found,
            "toolchain_tools_missing": self.toolchain_tools_missing,
            "artifacts_uploaded": self.artifacts_uploaded,
            "evidence_packs_created": self.evidence_packs_created,
            "hashes_created": self.hashes_created,
            "ci_replay_match_rate": self.ci_replay_match_rate,
            "public_wording": self.public_wording,
            "limitation": self.limitation,
        }


def run_ci(
    mode: str = "quick",
    toolchain_only: bool = False,
) -> CIResult:
    """Run the CI pipeline.

    Args:
        mode: "quick" for Python tests + hygiene + demos,
              "full" for quick + real tool stages.
        toolchain_only: If True, only show toolchain status and exit.

    Returns:
        CIResult with all results.
    """
    result = CIResult(
        timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        mode=mode,
        public_wording=st.CI_PUBLIC_WORDING,
        limitation=st.CI_LIMITATION,
    )

    # ── Step 1: Toolchain detection ──────────────────────────────────────
    result.toolchain_status = detect_toolchain()
    result.toolchain_tools_found = sum(
        1 for v in result.toolchain_status.values() if v.get("found", False)
    )
    result.toolchain_tools_missing = sum(
        1 for v in result.toolchain_status.values() if not v.get("found", False)
    )

    if toolchain_only:
        return result

    # ── Step 2: Hygiene checks ──────────────────────────────────────────
    pkg_dir = str(Path(__file__).parent)
    hygiene = run_hygiene_checks(pkg_dir)
    result.hygiene = hygiene.to_dict()
    if not hygiene.to_dict().get("passed", False):
        result.overall_status = st.CI_FAIL

    # ── Step 3: Python unit tests ───────────────────────────────────────
    _run_python_tests(result)

    # ── Step 4: Demo commands ───────────────────────────────────────────
    _run_demo_commands(result)

    # ── Step 5: Optional real tool stages (full mode) ───────────────────
    if mode == "full":
        _run_tool_stages(result)

    # ── Overall classification ──────────────────────────────────────────
    has_fail = (
        result.python_tests_failed > 0
        or not result.hygiene.get("passed", True)
    )
    has_skip = any(
        s.get("status", "").endswith("_SKIPPED")
        for s in result.stages
    )
    if has_fail:
        result.overall_status = st.CI_FAIL
    elif has_skip:
        result.overall_status = st.CI_PARTIAL
    else:
        result.overall_status = st.CI_PASS

    return result


def _run_python_tests(result: CIResult) -> None:
    """Run Python unit tests and record results."""
    try:
        t0 = time.time()
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests",
            "-v", "0"],
            capture_output=True, text=True, timeout=90,
            cwd=str(Path(__file__).parent.parent),
        )
        duration = time.time() - t0
        output = proc.stdout + proc.stderr
        # Parse passed/failed from unittest summary line
        for line in output.strip().split("\n"):
            line = line.strip()
            if "OK" in line or "passed" in line:
                parts = line.split()
                for p in parts:
                    if p.isdigit():
                        result.python_tests_passed = int(p)
            if "FAIL" in line or "failed" in line:
                parts = line.split()
                for p in parts:
                    try:
                        n = int(p)
                        if n > 0:
                            result.python_tests_failed = n
                    except ValueError:
                        pass
        result.stages.append({
            "stage_name": "python_tests",
            "status": st.CI_PASS if proc.returncode == 0 else st.CI_FAIL,
            "command": f"{sys.executable} -m unittest discover -s tests",
            "duration_seconds": duration,
            "output": output[:1000],
        })
    except (subprocess.TimeoutExpired, OSError) as exc:
        result.python_tests_failed = 1
        result.stages.append({
            "stage_name": "python_tests",
            "status": st.CI_FAIL,
            "command": f"{sys.executable} -m pytest tests/ -q",
            "output": str(exc),
        })


def _run_demo_commands(result: CIResult) -> None:
    """Run all demo commands that don't require EDA tools."""
    for cmd_name, cmd_args in _DEMO_COMMANDS:
        try:
            cmd = [sys.executable, "-m", "chipgate", cmd_name] + cmd_args
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                cwd=str(Path(__file__).parent.parent),
            )
            status = st.CI_PASS if proc.returncode == 0 else st.CI_FAIL
        except (subprocess.TimeoutExpired, OSError) as exc:
            status = st.CI_FAIL
        result.demo_results.append({
            "command": f"chipgate {cmd_name} {' '.join(cmd_args)}",
            "status": status,
        })


def _run_tool_stages(result: CIResult) -> None:
    """Run real toolchain stages in full mode."""
    # Find a safe RTL file to test against
    rtl_path = str(
        Path(__file__).parent.parent
        / "benchmarks" / "siliconbench_v0" / "designs" / "safe_dtl_gate.v"
    )
    if not Path(rtl_path).exists():
        rtl_path = str(
            Path(__file__).parent.parent
            / "examples" / "safe_dtl_gate.v"
        )

    if Path(rtl_path).exists():
        stages_runners = [
            run_verilator_stage,
            run_yosys_stage,
            run_symbiyosys_stage,
            run_openlane_stage,
            run_openroad_stage,
        ]
        for runner in stages_runners:
            sr = runner(rtl_path)
            result.stages.append(sr.to_dict())
    else:
        result.stages.append({
            "stage_name": "tool_stages",
            "status": st.CI_PARTIAL,
            "output": "No safe RTL file found for tool stages",
        })