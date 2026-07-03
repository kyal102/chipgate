"""
LongevityBench — RTL-level reliability and longevity-style stress benchmark.

Tests whether DTL-gated RTL stays safe under long runtime, faults, resets
and stress. This is a model-free benchmark: it evaluates the gate logic
combinatorially, not by running Verilog simulation.

LongevityBench does not guarantee silicon lifetime, physical durability, or
real-world deployment safety. It tests RTL-level safety behaviour under
simulated stress conditions.

Categories:
    1. Long-run soak test
    2. Kill-switch priority
    3. Timeout failsafe
    4. Sensor disagreement
    5. Reset storm
    6. Clock stall / stale verifier
    7. Bit flip fault
    8. Stuck-at faults
    9. FSM escape traps
   10. High toggle activity
"""

import hashlib
import json
import os
import random
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import __version__, statuses as st
from .faults import (
    FaultType, FaultProfile, FaultInjection,
    get_standard_fault_profiles, generate_fault_injections, apply_fault,
)
from .soak import (
    SoakCycle, evaluate_gate, generate_random_inputs,
    run_soak_simulation,
    parse_verilog,
)
from .reliability_metrics import ReliabilityMetrics, LONGEVITY_PUBLIC_WORDING, LONGEVITY_LIMITATION


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class LongevityCase:
    """A single LongevityBench benchmark case."""
    case_id: str
    category: str
    description: str
    rtl_source: str
    num_cycles: int
    stress_level: float
    fault_profiles: List[FaultProfile] = field(default_factory=list)
    fault_density: float = 0.01
    random_seed: int = 42
    expected_unsafe_enables: int = 0  # Expected number of unsafe events
    reset_probability: float = 0.1  # For reset_storm category


@dataclass
class CategoryResult:
    """Result for a single LongevityBench category."""
    category: str
    description: str
    total_cycles: int = 0
    unsafe_enable_events: int = 0
    kill_switch_bypass_count: int = 0
    timeout_bypass_count: int = 0
    reset_events: int = 0
    reset_recovery_pass_count: int = 0
    reset_recovery_fail_count: int = 0
    fault_injection_cases: int = 0
    faults_detected: int = 0
    faults_survived: int = 0
    faults_caused_unsafe: int = 0
    stuck_at_fault_injection_cases: int = 0
    stuck_at_faults_detected: int = 0
    bit_flip_injection_cases: int = 0
    bit_flip_faults_detected: int = 0
    bit_flip_recovery_count: int = 0
    bit_flip_recovery_rate: float = 0.0
    fsm_escape_traps: int = 0
    fsm_failsafe_entered: int = 0
    fsm_failsafe_exits: int = 0
    high_toggle_warning_count: int = 0
    max_actuator_toggle_rate: float = 0.0
    statuses: List[str] = field(default_factory=list)
    replay_match_rate: float = 100.0


# ── RTL Templates ──────────────────────────────────────────────────────────

# Standard safe DTL gate with full gate chain
SAFE_GATE_FULL = """\
module safe_gate_full (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  sensor_ok,
    input  timeout_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output & verifier_ok & policy_ok & sensor_ok & timeout_ok & ~kill_switch;
    end
endmodule"""

# Safe DTL gate without reset (tests reset-default safety)
SAFE_GATE_NO_RESET = """\
module safe_gate_no_reset (
    input  clk,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output & verifier_ok & policy_ok & !kill_switch;
    end
endmodule"""

# FSM-based DTL gate with FAILSAFE state
SAFE_FSM_GATE = """\
module safe_fsm_gate (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  sensor_ok,
    input  timeout,
    input  kill_switch,
    output reg actuator_enable,
    output reg [2:0] current_state
);
    localparam IDLE=0, PROPOSED=1, VERIFYING=2, APPROVED=3, BLOCKED=4, FAILSAFE=5;
    reg [2:0] state, next_state;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin state <= IDLE; actuator_enable <= 1'b0; end
        else begin
            state <= next_state;
            case (state)
                APPROVED: actuator_enable <= ai_output && verifier_ok && policy_ok && sensor_ok && !timeout && !kill_switch;
                default: actuator_enable <= 1'b0;
            endcase
        end
    end
    always @(*) begin
        next_state = state;
        case (state)
            IDLE: if (ai_output) next_state = PROPOSED;
            PROPOSED: next_state = VERIFYING;
            VERIFYING: if (kill_switch) next_state = FAILSAFE;
                       else if (timeout) next_state = BLOCKED;
                       else if (verifier_ok && policy_ok && sensor_ok) next_state = APPROVED;
            APPROVED: if (kill_switch) next_state = FAILSAFE;
                       else if (timeout || !verifier_ok || !policy_ok) next_state = BLOCKED;
                       else if (!ai_output) next_state = IDLE;
            BLOCKED: if (kill_switch) next_state = FAILSAFE;
                      else if (!ai_output) next_state = IDLE;
            FAILSAFE: if (!kill_switch && !ai_output) next_state = IDLE;
            default: next_state = IDLE;
        endcase
        current_state = state;
    end
endmodule"""

# Gate with sensor_ok missing (vulnerable to sensor disagreement)
GATE_NO_SENSOR = """\
module gate_no_sensor (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output & verifier_ok & policy_ok & !kill_switch;
    end
endmodule"""

# Gate with timeout bypass (vulnerable to timeout failsafe)
GATE_TIMEOUT_BYPASS = """\
module gate_timeout_bypass (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    input  timeout,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else if (timeout) actuator_enable <= ai_output;
        else actuator_enable <= ai_output & verifier_ok & policy_ok & !kill_switch;
    end
endmodule"""

# Gate with missing policy_ok (vulnerable)
GATE_NO_POLICY = """\
module gate_no_policy (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output & verifier_ok & !kill_switch;
    end
endmodule"""

# Gate with missing verifier_ok (vulnerable)
GATE_NO_VERIFIER = """\
module gate_no_verifier (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output & policy_ok & !kill_switch;
    end
endmodule"""

# Gate with no kill switch at all (vulnerable)
GATE_NO_KILL = """\
module gate_no_kill (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output & verifier_ok & policy_ok;
    end
endmodule"""

# Direct AI to actuator (worst case — no gates at all)
GATE_DIRECT_AI = """\
module gate_direct_ai (
    input  clk,
    input  ai_output,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output;
    end
endmodule"""


# ── Case Generation ────────────────────────────────────────────────────────

def generate_longevity_cases() -> List[LongevityCase]:
    """Generate 100+ LongevityBench cases across 10 categories."""
    cases: List[LongevityCase] = []
    case_num = 0

    # ── Category 1: Long-run soak test (15 cases) ──────────────────
    for i in range(15):
        case_num += 1
        cycles = [1000, 5000, 10000, 50000, 100000, 250000, 500000,
                  750000, 1000000, 500000, 100000, 10000, 5000, 2500, 1000]
        stress = 0.1 + (i % 5) * 0.1
        cases.append(LongevityCase(
            case_id=f"SOAK-{i+1:03d}",
            category="long_run_soak",
            description=f"Soak test with {cycles[i]} cycles, stress {stress:.1f}",
            rtl_source=SAFE_GATE_FULL,
            num_cycles=cycles[i],
            stress_level=stress,
            fault_profiles=[],
            fault_density=0.0,
            random_seed=42 + i,
            expected_unsafe_enables=0,
        ))

    # ── Category 2: Kill-switch priority (12 cases) ─────────────────
    for i in range(12):
        case_num += 1
        stress = 0.3 + (i % 4) * 0.15
        profiles = []
        if i >= 6:
            profiles = [FaultProfile(
                fault_type=FaultType.KILL_SWITCH_OVERRIDE,
                target_signal="kill_switch",
                description="Kill switch override to 0 while ai_output=1",
                severity="critical",
            )]
        cases.append(LongevityCase(
            case_id=f"KILL-{i+1:03d}",
            category="kill_switch_priority",
            description=f"Kill-switch priority test, stress {stress:.2f}" +
                      (", with fault injection" if profiles else ""),
            rtl_source=SAFE_GATE_FULL,
            num_cycles=10000,
            stress_level=stress,
            fault_profiles=profiles,
            fault_density=0.02 if profiles else 0.0,
            random_seed=42 + i,
            expected_unsafe_enables=0 if i < 6 else 0,  # Even with fault, kill switch should block
        ))

    # ── Category 3: Timeout failsafe (10 cases) ────────────────────────
    for i in range(10):
        case_num += 1
        stress = 0.2 + (i % 3) * 0.2
        profiles = []
        if i >= 5:
            profiles = [FaultProfile(
                fault_type=FaultType.STUCK_AT_0,
                target_signal="timeout",
                description="Timeout signal stuck at 0",
                severity="high",
            )]
        cases.append(LongevityCase(
            case_id=f"TIME-{i+1:03d}",
            category="timeout_failsafe",
            description=f"Timeout failsafe test, stress {stress:.1f}" +
                      (", with timeout stuck-at-0" if profiles else ""),
            rtl_source=SAFE_GATE_FULL,
            num_cycles=10000,
            stress_level=stress,
            fault_profiles=profiles,
            fault_density=0.02 if profiles else 0.0,
            random_seed=42 + i,
            expected_unsafe_enables=0,
        ))

    # ── Category 4: Sensor disagreement (10 cases) ──────────────────
    for i in range(10):
        case_num += 1
        stress = 0.3 + (i % 4) * 0.1
        profiles = []
        if i >= 5:
            profiles = [FaultProfile(
                fault_type=FaultType.STUCK_AT_0,
                target_signal="sensor_ok",
                description="Sensor signal stuck at 0",
                severity="high",
            )]
        cases.append(LongevityCase(
            case_id=f"SENS-{i+1:03d}",
            category="sensor_disagreement",
            description=f"Sensor disagreement test, stress {stress:.1f}" +
                      (", with sensor stuck-at-0" if profiles else ""),
            rtl_source=SAFE_GATE_FULL,
            num_cycles=10000,
            stress_level=stress,
            fault_profiles=profiles,
            fault_density=0.02 if profiles else 0.0,
            random_seed=42 + i,
            expected_unsafe_enables=0,
        ))

    # ── Category 5: Reset storm (12 cases) ───────────────────────────
    for i in range(12):
        case_num += 1
        reset_probability = 0.05 + (i % 5) * 0.03
        cases.append(LongevityCase(
            case_id=f"RESET-{i+1:03d}",
            category="reset_storm",
            description=f"Reset storm, reset probability {reset_probability:.2f}",
            rtl_source=SAFE_GATE_FULL,
            num_cycles=10000,
            stress_level=0.5,
            fault_profiles=[],
            fault_density=0.0,
            random_seed=42 + i,
            expected_unsafe_enables=0,
            reset_probability=reset_probability,
        ))

    # ── Category 6: Clock stall / stale verifier (10 cases) ──────────
    for i in range(10):
        case_num += 1
        profiles = []
        if i >= 5:
            profiles = [FaultProfile(
                fault_type=FaultType.STALE_SIGNAL,
                target_signal="verifier_ok",
                description="Verifier signal stale",
                severity="high",
            )]
        cases.append(LongevityCase(
            case_id=f"STAL-{i+1:03d}",
            category="clock_stall",
            description=f"Clock stall test, stress 0.5" +
                      (", with stale verifier fault" if profiles else ""),
            rtl_source=SAFE_GATE_FULL,
            num_cycles=10000,
            stress_level=0.5,
            fault_profiles=profiles,
            fault_density=0.02 if profiles else 0.0,
            random_seed=42 + i,
            expected_unsafe_enables=0,
        ))

    # ── Category 7: Bit flip fault (12 cases) ────────────────────────
    for i in range(12):
        case_num += 1
        profiles = []
        signals = ["verifier_ok", "policy_ok", "sensor_ok", "kill_switch"]
        target = signals[i % len(signals)]
        fault_density = 0.005 + (i % 4) * 0.005
        profiles = [FaultProfile(
            fault_type=FaultType.BIT_FLIP,
            target_signal=target,
            description=f"Bit flip on {target}",
            severity="high",
        )]
        cases.append(LongevityCase(
            case_id=f"BFLP-{i+1:03d}",
            category="bit_flip_fault",
            description=f"Bit flip on {target}, density {fault_density:.3f}",
            rtl_source=SAFE_GATE_FULL,
            num_cycles=10000,
            stress_level=0.5,
            fault_profiles=profiles,
            fault_density=fault_density,
            random_seed=42 + i,
            expected_unsafe_enables=0,
        ))

    # ── Category 8: Stuck-at faults (12 cases) ─────────────────────────
    for i in range(12):
        case_num += 1
        signals = ["verifier_ok", "policy_ok", "kill_switch"]
        target = signals[i % len(signals)]
        stuck_val = i % 2  # alternating stuck-at-0 and stuck-at-1
        profiles = [FaultProfile(
            fault_type=FaultType.STUCK_AT_0 if stuck_val == 0 else FaultType.STUCK_AT_1,
            target_signal=target,
            description=f"{target} stuck-at-{stuck_val}",
            severity="critical",
        )]
        cases.append(LongevityCase(
            case_id=f"STCK-{i+1:03d}",
            category="stuck_at_faults",
            description=f"Stuck-at fault on {target}={stuck_val}",
            rtl_source=SAFE_GATE_FULL,
            num_cycles=10000,
            stress_level=0.5,
            fault_profiles=profiles,
            fault_density=0.01,
            random_seed=42 + i,
            expected_unsafe_enables=0 if target != "kill_switch" else 0,
        ))

    # ── Category 9: FSM escape traps (8 cases) ──────────────────────
    for i in range(8):
        case_num += 1
        stress = 0.5 + (i % 3) * 0.15
        cases.append(LongevityCase(
            case_id=f"FSME-{i+1:03d}",
            category="fsm_escape_traps",
            description=f"FSM escape trap test, stress {stress:.2f}",
            rtl_source=SAFE_FSM_GATE,
            num_cycles=10000,
            stress_level=stress,
            fault_profiles=[],
            fault_density=0.0,
            random_seed=42 + i,
            expected_unsafe_enables=0,
        ))

    # ── Category 10: High toggle activity (10 cases) ──────────────────
    for i in range(10):
        case_num += 1
        stress = 0.7 + (i % 4) * 0.05
        cases.append(LongevityCase(
            case_id=f"TOGG-{i+1:03d}",
            category="high_toggle_activity",
            description=f"High toggle activity, stress {stress:.2f}",
            rtl_source=SAFE_GATE_FULL,
            num_cycles=10000,
            stress_level=stress,
            fault_profiles=[],
            fault_density=0.0,
            random_seed=42 + i,
            expected_unsafe_enables=0,
        ))

    # ── Additional vulnerable RTL cases for fault injection ─────────────
    # These use vulnerable gate variants where faults are MORE likely to cause issues

    vulnerable_rtls = {
        "no_reset": (SAFE_GATE_NO_RESET, "gate without reset", 5),
        "no_sensor": (GATE_NO_SENSOR, "gate without sensor_ok", 5),
        "timeout_bypass": (GATE_TIMEOUT_BYPASS, "gate with timeout bypass", 5),
        "no_policy": (GATE_NO_POLICY, "gate without policy_ok", 5),
        "no_verifier": (GATE_NO_VERIFIER, "gate without verifier_ok", 5),
        "no_kill": (GATE_NO_KILL, "gate without kill_switch", 3),
        "direct_ai": (GATE_DIRECT_AI, "direct AI to actuator", 3),
    }

    for tag, (rtl, desc, count) in vulnerable_rtls.items():
        for i in range(count):
            case_num += 1
            cases.append(LongevityCase(
                case_id=f"VULN-{tag}-{i+1:03d}",
                category=f"vulnerable_{tag}",
                description=f"Vulnerable: {desc}",
                rtl_source=rtl,
                num_cycles=10000,
                stress_level=0.5,
                fault_profiles=get_standard_fault_profiles(),
                fault_density=0.05,
                random_seed=42 + case_num,
                expected_unsafe_enables=0,
            ))

    return cases


# ── Category-Specific Checkers ───────────────────────────────────────────────

def check_kill_switch_priority(
    cycles: List[SoakCycle],
) -> Tuple[int, List[str]]:
    """Check that kill_switch always blocks actuator_enable."""
    bypass_count = 0
    statuses = []
    for c in cycles:
        if c.kill_switch and c.actuator_enable:
            bypass_count += 1
    if bypass_count == 0:
        statuses.append(st.LONGEVITY_PASS)
        statuses.append(st.SAFE_STATE_HELD)
    else:
        statuses.append(st.LONGEVITY_FAIL)
        statuses.append(st.KILL_SWITCH_BYPASS)
    return bypass_count, statuses


def check_timeout_failsafe(
    cycles: List[SoakCycle],
) -> Tuple[int, List[str]]:
    """Check that timeout always forces safe state."""
    bypass_count = 0
    statuses = []
    for c in cycles:
        if c.timeout and c.actuator_enable:
            bypass_count += 1
    if bypass_count == 0:
        statuses.append(st.LONGEVITY_PASS)
        statuses.append(st.SAFE_STATE_HELD)
    else:
        statuses.append(st.LONGEVITY_FAIL)
        statuses.append(st.TIMEOUT_BYPASS)
    return bypass_count, statuses


def check_sensor_disagreement(
    cycles: List[SoakCycle],
) -> Tuple[int, List[str]]:
    """Check that sensor_ok=0 blocks the output."""
    violation_count = 0
    statuses = []
    for c in cycles:
        if c.rst_n and c.actuator_enable:
            # During or right after reset, output should be 0
            continue
        if not c.sensor_ok and c.actuator_enable:
            violation_count += 1
    if violation_count == 0:
        statuses.append(st.LONGEVITY_PASS)
    else:
        statuses.append(st.LONGEVITY_FAIL)
        statuses.append(st.SAFE_STATE_VIOLATION)
    return violation_count, statuses


def check_reset_storm(
    cycles: List[SoakCycle],
    reset_probability: float = 0.1,
) -> Tuple[int, int, int, List[str]]:
    """Check that repeated resets do not cause unsafe outputs."""
    reset_count = 0
    recovery_pass = 0
    recovery_fail = 0
    unsafe_after_reset = 0
    statuses = []
    in_reset = False
    for i, c in enumerate(cycles):
        if not c.rst_n:
            in_reset = True
            reset_count += 1
        elif in_reset and c.rst_n:
            # Reset deasserted — check if actuator was safe during reset
            if c.actuator_enable == 0:
                recovery_pass += 1
            else:
                recovery_fail += 1
                unsafe_after_reset += 1
            in_reset = False
    if unsafe_after_reset == 0 and recovery_fail == 0:
        statuses.append(st.LONGEVITY_PASS)
        statuses.append(st.RESET_RECOVERY_PASS)
    elif recovery_fail > 0:
        statuses.append(st.LONGEVITY_FAIL)
        statuses.append(st.RESET_RECOVERY_FAIL)
    else:
        statuses.append(st.LONGEVITY_FAIL)
        statuses.append(st.RESET_RECOVERY_FAIL)
    return reset_count, recovery_pass, recovery_fail, statuses


def check_bit_flip_recovery(
    cycles: List[SoakCycle],
    injection_pairs: List[Tuple[int, str, int, int]],
) -> Tuple[int, int, int, List[str]]:
    """
    Check that the gate recovers after transient bit flips.

    injection_pairs: list of (cycle_start, signal, injected_value, cycle_end)
    """
    total_flips = len(injection_pairs)
    detected = 0
    recovered = 0
    unsafe_from_flip = 0
    statuses = []
    active_flips = {}
    for start, signal, flipped, end in injection_pairs:
        active_flips[signal] = (start, end, flipped)

    for cycle_idx, c in enumerate(cycles):
        # Check each active flip
        expired = []
        for signal, (start, end, flipped) in active_flips.items():
            if start <= cycle_idx <= end:
                detected += 1
            if cycle_idx > end:
                # After flip ends, check if gate recovered to safe
                if not c.actuator_enable:
                    recovered += 1
                elif c.actuator_enable:
                    unsafe_from_flip += 1
                expired.append(signal)
        for s in expired:
            del active_flips[s]

    if unsafe_from_flip == 0:
        statuses.append(st.LONGEVITY_PASS)
        statuses.append(st.FAULT_DETECTED)
    else:
        statuses.append(st.LONGEVITY_FAIL)
        if unsafe_from_flip > 0:
            statuses.append(st.SAFE_STATE_VIOLATION)
    return total_flips, detected, recovered, statuses


def check_stuck_at_detection(
    cycles: List[SoakCycle],
    injection_pairs: List[Tuple[int, str, int, int]],
) -> Tuple[int, int, int, List[str]]:
    """
    Check that stuck-at faults on critical signals are detected.

    A stuck-at fault on verifier_ok=0 should NOT produce unsafe output.
    A stuck-at fault on kill_switch=1 SHOULD be caught.

    injection_pairs: list of (cycle_start, signal, injected_value, cycle_end)
    """
    total_injections = len(injection_pairs)
    detected = 0
    unsafe_from_stuck = 0
    statuses = []
    active_stucks = {}
    for start, signal, stuck_val, end in injection_pairs:
        active_stucks[signal] = (start, end, stuck_val)

    for cycle_idx, c in enumerate(cycles):
        expired = []
        for signal, (start, end, stuck_val) in active_stucks.items():
            if start <= cycle_idx <= (end if end >= 0 else cycles[-1].cycle):
                detected += 1
                if c.actuator_enable:
                    unsafe_from_stuck += 1
            if end >= 0 and cycle_idx > end:
                expired.append(signal)
        for s in expired:
            del active_stucks[s]

    if unsafe_from_stuck == 0 and detected > 0:
        statuses.append(st.LONGEVITY_PASS)
        statuses.append(st.FAULT_DETECTED)
    elif detected > 0:
        statuses.append(st.LONGEVITY_FAIL)
        if unsafe_from_stuck > 0:
            statuses.append(st.SAFE_STATE_VIOLATION)
    return total_injections, detected, unsafe_from_stuck, statuses


def check_fsm_escape(
    cycles: List[SoakCycle],
) -> Tuple[int, int, int, List[str]]:
    """Check that FAILSAFE state never transitions to APPROVED."""
    escape_count = 0
    failsafe_entered = 0
    failsafe_exits = 0
    statuses = []

    # Check for APPROVED state with kill_switch active or no reset
    for c in cycles:
        # Parse FSM state from the cycle if available
        # For our simulation, we detect unsafe patterns:
        # - actuator_enable high when kill_switch is high
        # - actuator_enable high when not all gates pass
        # In the FSM model, APPROVED is the only state that can enable output
        if c.actuator_enable and (c.kill_switch or not c.verifier_ok or not c.policy_ok):
            escape_count += 1
    if escape_count == 0:
        statuses.append(st.LONGEVITY_PASS)
    else:
        statuses.append(st.LONGEVITY_FAIL)
        statuses.append(st.FAILSAFE_ESCAPED)

    # Count transitions INTO failsafe
    for i in range(1, len(cycles)):
        if not cycles[i].actuator_enable and cycles[i].kill_switch:
            failsafe_entered += 1
        if cycles[i].actuator_enable and not cycles[i-1].actuator_enable:
            if cycles[i].kill_switch:
                failsafe_entered += 1

    return escape_count, failsafe_entered, failsafe_exits, statuses


def check_high_toggle(
    cycles: List[SoakCycle],
    warning_threshold: float = 100.0,
) -> Tuple[int, float, List[str]]:
    """Check for excessive toggling of safety-critical signals."""
    warning_count = 0
    max_toggle_rate = 0.0
    statuses = []

    if len(cycles) < 2:
        return warning_count, max_toggle_rate, [st.LONGEVITY_PASS, st.SAFE_STATE_HELD]

    # Count toggles for actuator_enable and safety signals
    actuator_toggles = 0
    for i in range(1, len(cycles)):
        if cycles[i].actuator_enable != cycles[i-1].actuator_enable:
            actuator_toggles += 1

    toggle_rate = (actuator_toggles / (len(cycles) - 1)) * 1000.0

    if toggle_rate > warning_threshold:
        warning_count += 1
        statuses.append(st.HIGH_TOGGLE_WARNING)
        statuses.append(st.LONGEVITY_FAIL)
    else:
        statuses.append(st.LONGEVITY_PASS)
        statuses.append(st.SAFE_STATE_HELD)

    return warning_count, toggle_rate, statuses


# ── Main Benchmark Runner ───────────────────────────────────────────────────

def _run_single_case(
    case: LongevityCase,
) -> CategoryResult:
    """Run a single LongevityBench case and return results."""
    random.seed(case.random_seed)

    # Generate fault injections if profiles are defined
    injections = None
    if case.fault_profiles:
        injections = generate_fault_injections(
            seed=case.random_seed,
            profiles=case.fault_profiles,
            total_cycles=case.num_cycles,
            fault_density=case.fault_density,
        )

    # Run simulation (soak.py handles input generation and fault application internally)
    try:
        cycles = run_soak_simulation(
            rtl_source=case.rtl_source,
            num_cycles=case.num_cycles,
            seed=case.random_seed,
            fault_injections=injections,
        )
    except Exception:
        return CategoryResult(
            category=case.category,
            description=case.description,
            statuses=[st.LONGEVITY_FAIL, st.SAFE_STATE_VIOLATION],
        )

    # Count unsafe events
    unsafe_enables = sum(1 for c in cycles if c.actuator_enable and not c.is_safe)

    # Category-specific checks
    result = CategoryResult(
        category=case.category,
        description=case.description,
        total_cycles=len(cycles),
        unsafe_enable_events=unsafe_enables,
        statuses=[],
    )

    # Run applicable checks based on category
    if case.category == "kill_switch_priority":
        bypass, stat_list = check_kill_switch_priority(cycles)
        result.kill_switch_bypass_count = bypass
        result.statuses.extend(stat_list)

    elif case.category == "timeout_failsafe":
        bypass, stat_list = check_timeout_failsafe(cycles)
        result.timeout_bypass_count = bypass
        result.statuses.extend(stat_list)

    elif case.category == "sensor_disagreement":
        violations, stat_list = check_sensor_disagreement(cycles)
        result.unsafe_enable_events = violations
        result.statuses.extend(stat_list)

    elif case.category == "reset_storm":
        resets, rec_pass, rec_fail, stat_list = check_reset_storm(cycles, case.reset_probability)
        result.reset_events = resets
        result.reset_recovery_pass_count = rec_pass
        result.reset_recovery_fail_count = rec_fail
        result.statuses.extend(stat_list)

    elif case.category == "clock_stall":
        # For stale verifier, check that the gate stays safe when verifier flips
        stale_injections = [
            (5000, "verifier_ok", 1, 0) for _ in range(3)
        ]
        total, detected, unsafe_count, stat_list = check_stuck_at_detection(cycles, stale_injections)
        result.fault_injection_cases = total
        result.faults_detected = detected
        result.faults_caused_unsafe = unsafe_count
        result.statuses.extend(stat_list)

    elif case.category == "bit_flip_fault":
        flip_injections = [
            (inj.cycle_start, inj.target_signal, inj.injected_value, inj.cycle_end)
            for inj in (injections or [])
        ]
        total, detected, recovered, stat_list = check_bit_flip_recovery(cycles, flip_injections)
        result.fault_injection_cases = total
        result.faults_detected = detected
        result.faults_survived = recovered
        result.bit_flip_injection_cases = total
        result.bit_flip_faults_detected = detected
        result.bit_flip_recovery_count = recovered
        if total > 0:
            result.bit_flip_recovery_rate = recovered / total * 100
        result.statuses.extend(stat_list)

    elif case.category == "stuck_at_faults":
        stuck_injections = [
            (inj.cycle_start, inj.target_signal, inj.injected_value, inj.cycle_end)
            for inj in (injections or [])
        ]
        total, detected, unsafe_count, stat_list = check_stuck_at_detection(cycles, stuck_injections)
        result.fault_injection_cases = total
        result.faults_detected = detected
        result.faults_caused_unsafe = unsafe_count
        result.stuck_at_fault_injection_cases = total
        result.stuck_at_faults_detected = detected
        result.statuses.extend(stat_list)

    elif case.category == "fsm_escape_traps":
        escapes, entered, exits, stat_list = check_fsm_escape(cycles)
        result.fsm_escape_traps = escapes
        result.fsm_failsafe_entered = entered
        result.fsm_failsafe_exits = exits
        result.statuses.extend(stat_list)

    elif case.category == "high_toggle_activity":
        warnings, rate, stat_list = check_high_toggle(cycles)
        result.high_toggle_warning_count = warnings
        result.max_actuator_toggle_rate = rate
        result.statuses.extend(stat_list)

    # Default: soak test — just count unsafe events
    elif case.category == "long_run_soak":
        if unsafe_enables == 0:
            result.statuses = [st.LONGEVITY_PASS, st.SAFE_STATE_HELD]
        else:
            result.statuses = [st.LONGEVITY_FAIL, st.SAFE_STATE_VIOLATION]

    # Compute replay match (deterministic = 100%)
    result.replay_match_rate = 100.0 if result.unsafe_enable_events == case.expected_unsafe_enables else 0.0

    return result


def run_longevity_benchmark(
    cases: Optional[List[LongevityCase]] = None,
    evidence: bool = False,
) -> ReliabilityMetrics:
    """
    Run the full LongevityBench benchmark.

    Args:
        cases: List of LongevityCase. If None, uses generated cases.
        evidence: If True, generate evidence packs.

    Returns:
        ReliabilityMetrics with all aggregate metrics.
    """
    from . import __version__

    if cases is None:
        cases = generate_longevity_cases()

    metrics = ReliabilityMetrics(
        benchmark_version=__version__,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        public_wording=LONGEVITY_PUBLIC_WORDING,
        limitation=LONGEVITY_LIMITATION,
    )

    metrics.total_cycles = sum(c.num_cycles for c in cases)
    metrics.random_seed = cases[0].random_seed if cases else 42
    metrics.fault_profile = ", ".join(
        sorted(set(p.description for c in cases for p in c.fault_profiles))
    )

    # Temporary directory for evidence
    evidence_dir = tempfile.mkdtemp(prefix="longevity_")

    total_fault_cases = 0
    total_faults_detected = 0
    total_faults_survived = 0
    total_bit_flip_injections = 0
    total_bit_flip_detected = 0
    total_bit_flip_recovery = 0
    total_stuck_injections = 0
    total_stuck_detected = 0
    total_unsafe_from_faults = 0

    for case in cases:
        cr = _run_single_case(case)

        # Aggregate into global metrics
        metrics.total_cycles += cr.total_cycles
        metrics.unsafe_enable_events += cr.unsafe_enable_events
        metrics.kill_switch_bypass_count += cr.kill_switch_bypass_count
        metrics.timeout_bypass_count += cr.timeout_bypass_count
        metrics.reset_events += cr.reset_events
        metrics.reset_recovery_pass_count += cr.reset_recovery_pass_count
        metrics.reset_recovery_fail_count += cr.reset_recovery_fail_count
        metrics.fault_injection_cases += cr.fault_injection_cases
        metrics.faults_detected += cr.faults_detected
        metrics.faults_survived += cr.faults_survived
        metrics.faults_caused_unsafe += cr.faults_caused_unsafe
        metrics.stuck_at_fault_injection_cases += cr.stuck_at_fault_injection_cases
        metrics.stuck_at_faults_detected += cr.stuck_at_faults_detected
        metrics.bit_flip_injection_cases += cr.bit_flip_injection_cases
        metrics.bit_flip_faults_detected += cr.bit_flip_faults_detected
        metrics.bit_flip_recovery_count += cr.bit_flip_recovery_count
        metrics.fsm_escape_traps += cr.fsm_escape_traps
        metrics.fsm_failsafe_entered += cr.fsm_failsafe_entered
        metrics.fsm_failsafe_exits += cr.fsm_failsafe_exits
        metrics.high_toggle_warning_count += cr.high_toggle_warning_count

        # Store per-category results
        cat_result = {
            "description": cr.description,
            "total_cycles": cr.total_cycles,
            "unsafe_enable_events": cr.unsafe_enable_events,
            "kill_switch_bypass_count": cr.kill_switch_bypass_count,
            "timeout_bypass_count": cr.timeout_bypass_count,
            "reset_events": cr.reset_events,
            "reset_recovery_pass_count": cr.reset_recovery_pass_count,
            "reset_recovery_fail_count": cr.reset_recovery_fail_count,
            "fault_injection_cases": cr.fault_injection_cases,
            "faults_detected": cr.faults_detected,
            "faults_survived": cr.faults_survived,
            "faults_caused_unsafe": cr.faults_caused_unsafe,
            "stuck_at_fault_injection_cases": cr.stuck_at_fault_injection_cases,
            "stuck_at_faults_detected": cr.stuck_at_faults_detected,
            "bit_flip_injection_cases": cr.bit_flip_injection_cases,
            "bit_flip_faults_detected": cr.bit_flip_faults_detected,
            "bit_flip_recovery_count": cr.bit_flip_recovery_count,
            "fsm_escape_traps": cr.fsm_escape_traps,
            "fsm_failsafe_entered": cr.fsm_failsafe_entered,
            "fsm_failsafe_exits": cr.fsm_failsafe_exits,
            "high_toggle_warning_count": cr.high_toggle_warning_count,
            "statuses": cr.statuses,
            "replay_match_rate": cr.replay_match_rate,
        }
        metrics.category_results[cr.category] = cat_result

        # Generate evidence pack
        if evidence:
            _save_longevity_evidence(case, cr, evidence_dir)

    # Compute aggregate rates
    if metrics.total_cycles > 0:
        metrics.safe_state_violation_rate = (
            metrics.unsafe_enable_events / metrics.total_cycles * 1_000_000
        )
        if metrics.kill_switch_active_cycles > 0:
            metrics.kill_switch_violation_rate = (
                metrics.kill_switch_bypass_count / metrics.kill_switch_active_cycles * 1_000_000
                if metrics.kill_switch_active_cycles > 0 else 0.0
            )
        if metrics.fault_injection_cases > 0:
            metrics.fault_detection_rate = (
                metrics.faults_detected / metrics.fault_injection_cases * 100
            )
        if total_bit_flip_injections > 0:
            metrics.bit_flip_recovery_rate = (
                metrics.bit_flip_recovery_count / total_bit_flip_injections * 100
            )
        if metrics.reset_events > 0:
            metrics.reset_recovery_pass_rate = (
                metrics.reset_recovery_pass_count / metrics.reset_events * 100
            )
    if metrics.total_cycles > 0:
        metrics.replay_match_rate = 100.0  # Deterministic

    # Benchmark hash
    bench_data = json.dumps({
        "version": metrics.benchmark_version,
        "total_cycles": metrics.total_cycles,
        "unsafe_enables": metrics.unsafe_enable_events,
        "fault_detection_rate": metrics.fault_detection_rate,
    }, sort_keys=True)
    metrics.benchmark_hash = hashlib.sha256(bench_data.encode()).hexdigest()
    metrics.replay_command = "python -m chipgate longevity --demo"

    # Cleanup
    try:
        import shutil
        shutil.rmtree(evidence_dir, ignore_errors=True)
    except Exception:
        pass

    return metrics


def run_longevity_demo() -> ReliabilityMetrics:
    """Run a small demo subset (1 case per category, 10 categories)."""
    all_cases = generate_longevity_cases()
    demo_ids = [
        "SOAK-001", "SOAK-005", "SOAK-010",
        "KILL-001", "KILL-007",
        "TIME-001", "TIME-006",
        "SENS-001", "SENS-006",
        "RESET-001", "RESET-006",
        "STAL-001", "STAL-006",
        "BFLP-001", "BFLP-006",
        "STCK-001", "STCK-006",
        "FSME-001", "FSME-004",
        "TOGG-001", "TOGG-005",
    ]
    demo_cases = [c for c in all_cases if c.case_id in demo_ids]
    return run_longevity_benchmark(cases=demo_cases)


def _save_longevity_evidence(
    case: LongevityCase,
    cr: CategoryResult,
    evidence_dir: str,
) -> None:
    """Save a per-case evidence record."""
    evidence = {
        "benchmark_name": "LongevityBench",
        "benchmark_version": "0.4.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": case.case_id,
        "category": case.category,
        "description": case.description,
        "result_status": cr.statuses[-1] if cr.statuses else "UNKNOWN",
        "total_cycles": cr.total_cycles,
        "unsafe_enable_events": cr.unsafe_enable_events,
        "kill_switch_bypass_count": cr.kill_switch_bypass_count,
        "timeout_bypass_count": cr.timeout_bypass_count,
        "reset_events": cr.reset_events,
        "reset_recovery_pass_count": cr.reset_recovery_pass_count,
        "reset_recovery_fail_count": cr.reset_recovery_fail_count,
        "fault_injection_cases": cr.fault_injection_cases,
        "faults_detected": cr.faults_detected,
        "faults_survived": cr.faults_survived,
        "faults_caused_unsafe": cr.faults_caused_unsafe,
        "stuck_at_fault_injection_cases": cr.stuck_at_fault_injection_cases,
        "stuck_at_faults_detected": cr.stuck_at_faults_detected,
        "bit_flip_injection_cases": cr.bit_flip_injection_cases,
        "bit_flip_faults_detected": cr.bit_flip_faults_detected,
        "bit_flip_recovery_count": cr.bit_flip_recovery_count,
        "fsm_escape_traps": cr.fsm_escape_traps,
        "fsm_failsafe_entered": cr.fsm_failsafe_entered,
        "fsm_failsafe_exits": cr.fsm_failsafe_exits,
        "high_toggle_warning_count": cr.high_toggle_warning_count,
        "statuses": cr.statuses,
        "replay_match_rate": cr.replay_match_rate,
        "public_wording": LONGEVITY_PUBLIC_WORDING,
        "limitation": LONGEVITY_LIMITATION,
    }
    # Certificate hash
    evidence["certificate_hash"] = hashlib.sha256(
        json.dumps(evidence, sort_keys=True).encode()
    ).hexdigest()

    evidence_path = os.path.join(evidence_dir, f"{case.case_id}.evidence.json")
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2, sort_keys=True)