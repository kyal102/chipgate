"""
ChipGate reliability metrics for LongevityBench.

Computes aggregate reliability metrics from soak simulation results
and fault injection campaigns. These metrics characterize RTL-level
safety behaviour under stress — they do not guarantee silicon lifetime,
physical durability, or regulatory conformance.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import hashlib
import json


@dataclass
class ReliabilityMetrics:
    """Complete reliability benchmark result."""
    benchmark_name: str = "LongevityBench"
    benchmark_version: str = ""
    timestamp_utc: str = ""
    rtl_source: str = ""
    cycle_count: int = 0
    random_seed: int = 0
    fault_profile: str = ""
    public_wording: str = ""
    limitation: str = ""

    # Core safety counts
    total_cycles: int = 0
    unsafe_enable_events: int = 0
    safe_state_violation_rate: float = 0.0  # per million cycles

    # Kill-switch
    kill_switch_bypass_count: int = 0
    kill_switch_active_cycles: int = 0
    kill_switch_violation_rate: float = 0.0

    # Timeout
    timeout_bypass_count: int = 0
    timeout_active_cycles: int = 0

    # Reset
    reset_events: int = 0
    reset_recovery_pass_count: int = 0
    reset_recovery_fail_count: int = 0
    reset_recovery_pass_rate: float = 0.0

    # Fault injection
    fault_injection_cases: int = 0
    faults_detected: int = 0
    faults_survived: int = 0
    fault_detection_rate: float = 0.0
    faults_caused_unsafe: int = 0

    # Specific fault types
    stuck_at_fault_injection_cases: int = 0
    stuck_at_faults_detected: int = 0
    bit_flip_injection_cases: int = 0
    bit_flip_faults_detected: int = 0
    bit_flip_recovery_count: int = 0
    bit_flip_recovery_rate: float = 0.0

    # FSM
    fsm_escape_traps: int = 0
    fsm_failsafe_entered: int = 0
    fsm_failsafe_exits: int = 0

    # Toggle activity
    high_toggle_warning_count: int = 0
    max_actuator_toggle_rate: float = 0.0  # toggles per 1000 cycles

    # Replay and evidence
    replay_match_rate: float = 100.0
    evidence_packs_created: int = 0
    benchmark_hash: str = ""
    replay_command: str = ""

    # Per-category results
    category_results: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "benchmark_name": self.benchmark_name,
            "benchmark_version": self.benchmark_version,
            "timestamp_utc": self.timestamp_utc,
            "rtl_source_hash": hashlib.sha256(self.rtl_source.encode()).hexdigest()[:16] if self.rtl_source else "",
            "cycle_count": self.cycle_count,
            "random_seed": self.random_seed,
            "fault_profile": self.fault_profile,
            "public_wording": self.public_wording,
            "limitation": self.limitation,
            "total_cycles": self.total_cycles,
            "unsafe_enable_events": self.unsafe_enable_events,
            "safe_state_violation_rate": round(self.safe_state_violation_rate, 6),
            "kill_switch_bypass_count": self.kill_switch_bypass_count,
            "kill_switch_active_cycles": self.kill_switch_active_cycles,
            "kill_switch_violation_rate": round(self.kill_switch_violation_rate, 6),
            "timeout_bypass_count": self.timeout_bypass_count,
            "timeout_active_cycles": self.timeout_active_cycles,
            "reset_events": self.reset_events,
            "reset_recovery_pass_count": self.reset_recovery_pass_count,
            "reset_recovery_fail_count": self.reset_recovery_fail_count,
            "reset_recovery_pass_rate": round(self.reset_recovery_pass_rate, 2),
            "fault_injection_cases": self.fault_injection_cases,
            "faults_detected": self.faults_detected,
            "faults_survived": self.faults_survived,
            "fault_detection_rate": round(self.fault_detection_rate, 2),
            "faults_caused_unsafe": self.faults_caused_unsafe,
            "stuck_at_fault_injection_cases": self.stuck_at_fault_injection_cases,
            "stuck_at_faults_detected": self.stuck_at_faults_detected,
            "bit_flip_injection_cases": self.bit_flip_injection_cases,
            "bit_flip_faults_detected": self.bit_flip_faults_detected,
            "bit_flip_recovery_count": self.bit_flip_recovery_count,
            "bit_flip_recovery_rate": round(self.bit_flip_recovery_rate, 2),
            "fsm_escape_traps": self.fsm_escape_traps,
            "fsm_failsafe_entered": self.fsm_failsafe_entered,
            "fsm_failsafe_exits": self.fsm_failsafe_exits,
            "high_toggle_warning_count": self.high_toggle_warning_count,
            "max_actuator_toggle_rate": round(self.max_actuator_toggle_rate, 2),
            "replay_match_rate": round(self.replay_match_rate, 2),
            "evidence_packs_created": self.evidence_packs_created,
            "benchmark_hash": self.benchmark_hash,
            "replay_command": self.replay_command,
            "category_results": self.category_results,
        }
        return d


LONGEVITY_PUBLIC_WORDING = (
    "LongevityBench tests RTL-level safety behaviour under simulated stress. "
    "It does not guarantee silicon lifetime, physical durability, process reliability, "
    "regulatory conformance or real-world deployment safety."
)

LONGEVITY_LIMITATION = (
    "These results are RTL-level combinatorial simulations, not physical "
    "or Verilog simulation. They do not account for clock-domain crossings, "
    "metastability, setup/hold violations, power supply noise, "
    "electromigration, BTI/HCI/TDDB aging, or thermal stress. "
    "Physical signoff requires formal verification, timing analysis, "
    "and device qualification testing beyond the scope of this tool."
)
