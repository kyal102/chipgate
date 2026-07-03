"""
ChipGate fault injection engine for LongevityBench.

Provides fault models for testing DTL-gated RTL reliability:
- Stuck-at faults (stuck-at-0, stuck-at-1)
- Bit-flip / transient glitch faults
- Stale signal faults
- Kill-switch priority override simulation

These are combinatorial RTL-level fault models, not physical fault
simulation. They test whether the gate logic produces safe outputs
under fault conditions. This does not guarantee silicon reliability or
physical durability.
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class FaultType(Enum):
    """Types of RTL-level faults that can be injected."""

    STUCK_AT_0 = "stuck_at_0"
    STUCK_AT_1 = "stuck_at_1"
    BIT_FLIP = "bit_flip"
    STALE_SIGNAL = "stale_signal"
    KILL_SWITCH_OVERRIDE = "kill_switch_override"
    RESET_GLITCH = "reset_glitch"


@dataclass
class FaultProfile:
    """Describes a fault to be applied to a target signal."""

    fault_type: FaultType
    target_signal: str
    description: str
    severity: str  # "critical", "high", "medium", "low"


@dataclass
class FaultInjection:
    """A specific fault injection event with timing and injected value."""

    profile: FaultProfile
    cycle_start: int
    cycle_end: int  # -1 for permanent faults
    injected_value: int  # 0 or 1


def get_standard_fault_profiles() -> List[FaultProfile]:
    """
    Return a list of standard fault profiles for all key DTL gate signals.

    Covers stuck-at-0 and stuck-at-1 faults on verifier_ok, policy_ok,
    kill_switch, sensor_ok, and timeout signals. Each profile includes
    a description and severity rating.
    """
    profiles: List[FaultProfile] = [
        # verifier_ok faults
        FaultProfile(
            fault_type=FaultType.STUCK_AT_0,
            target_signal="verifier_ok",
            description=(
                "verifier_ok stuck-at-0: verifier can never approve, "
                "actuator permanently disabled regardless of AI output"
            ),
            severity="critical",
        ),
        FaultProfile(
            fault_type=FaultType.STUCK_AT_1,
            target_signal="verifier_ok",
            description=(
                "verifier_ok stuck-at-1: verifier always appears to approve, "
                "bypassing independent verification"
            ),
            severity="critical",
        ),
        # policy_ok faults
        FaultProfile(
            fault_type=FaultType.STUCK_AT_0,
            target_signal="policy_ok",
            description=(
                "policy_ok stuck-at-0: policy check can never pass, "
                "actuator permanently disabled"
            ),
            severity="critical",
        ),
        FaultProfile(
            fault_type=FaultType.STUCK_AT_1,
            target_signal="policy_ok",
            description=(
                "policy_ok stuck-at-1: policy gate always appears satisfied, "
                "unsafe outputs may pass policy check"
            ),
            severity="critical",
        ),
        # kill_switch faults
        FaultProfile(
            fault_type=FaultType.STUCK_AT_0,
            target_signal="kill_switch",
            description=(
                "kill_switch stuck-at-0: emergency stop can never activate, "
                "failsafe path is blocked"
            ),
            severity="critical",
        ),
        FaultProfile(
            fault_type=FaultType.STUCK_AT_1,
            target_signal="kill_switch",
            description=(
                "kill_switch stuck-at-1: emergency stop permanently active, "
                "actuator always disabled (safe but unavailable)"
            ),
            severity="high",
        ),
        # sensor_ok faults
        FaultProfile(
            fault_type=FaultType.STUCK_AT_0,
            target_signal="sensor_ok",
            description=(
                "sensor_ok stuck-at-0: sensor validation can never pass, "
                "actuator permanently disabled"
            ),
            severity="high",
        ),
        FaultProfile(
            fault_type=FaultType.STUCK_AT_1,
            target_signal="sensor_ok",
            description=(
                "sensor_ok stuck-at-1: sensor check always appears valid, "
                "physical environment hazards may go undetected"
            ),
            severity="critical",
        ),
        # timeout faults
        FaultProfile(
            fault_type=FaultType.STUCK_AT_0,
            target_signal="timeout",
            description=(
                "timeout stuck-at-0: timeout never fires, "
                "operation can hang indefinitely in unsafe states"
            ),
            severity="high",
        ),
        FaultProfile(
            fault_type=FaultType.STUCK_AT_1,
            target_signal="timeout",
            description=(
                "timeout stuck-at-1: timeout permanently asserted, "
                "actuator always disabled (safe but unavailable)"
            ),
            severity="medium",
        ),
    ]
    return profiles


def generate_fault_injections(
    seed: int,
    profiles: List[FaultProfile],
    total_cycles: int,
    fault_density: float = 0.01,
) -> List[FaultInjection]:
    """
    Generate a reproducible set of fault injections for a soak simulation.

    For each fault profile, randomly decides whether to inject based on
    fault_density, then picks a random start cycle and duration. The
    injected value is determined by the fault type:
      - STUCK_AT_0 -> 0
      - STUCK_AT_1 -> 1
      - BIT_FLIP   -> toggles the "expected" value (injected as 1)
      - STALE_SIGNAL -> 0 (stale values treated as deasserted)
      - KILL_SWITCH_OVERRIDE -> 0 (overrides kill switch to inactive)
      - RESET_GLITCH -> 0 (resets are active-low, so glitch = 0)

    Args:
        seed: Random seed for reproducibility.
        profiles: List of FaultProfile to potentially inject.
        total_cycles: Total number of simulation cycles.
        fault_density: Probability (0.0-1.0) that any given profile
            gets an injection event.

    Returns:
        Sorted list of FaultInjection events by cycle_start.
    """
    rng = random.Random(seed)
    injections: List[FaultInjection] = []

    for profile in profiles:
        # Decide whether this profile gets injected at all
        if rng.random() > fault_density:
            continue

        # Determine injected value based on fault type
        if profile.fault_type in (FaultType.STUCK_AT_0, FaultType.STALE_SIGNAL,
                                   FaultType.KILL_SWITCH_OVERRIDE, FaultType.RESET_GLITCH):
            injected_value = 0
        else:
            injected_value = 1

        # Pick a random start cycle
        cycle_start = rng.randint(0, max(0, total_cycles - 1))

        # Pick a random duration (5-50 cycles)
        duration = rng.randint(5, 50)

        # Permanent faults (stuck-at types) end at -1
        if profile.fault_type in (FaultType.STUCK_AT_0, FaultType.STUCK_AT_1):
            cycle_end = -1
        else:
            cycle_end = min(cycle_start + duration, total_cycles)

        injections.append(FaultInjection(
            profile=profile,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            injected_value=injected_value,
        ))

    # Sort by cycle_start for deterministic ordering
    injections.sort(key=lambda inj: inj.cycle_start)
    return injections


def apply_fault(
    signal_value: int,
    injection: Optional[FaultInjection],
    cycle: int,
) -> int:
    """
    Apply a fault injection to a signal value for a given cycle.

    If the injection is active for the specified cycle, the injected
    value overrides the signal value. Otherwise the original signal
    value is returned unchanged.

    Args:
        signal_value: The original signal value (0 or 1).
        injection: The FaultInjection to apply, or None.
        cycle: The current simulation cycle number.

    Returns:
        The signal value after fault injection (0 or 1).
    """
    if injection is None:
        return signal_value

    # Check if the injection is active for this cycle
    if cycle < injection.cycle_start:
        return signal_value

    # -1 means permanent fault, active from cycle_start onward
    if injection.cycle_end == -1:
        return injection.injected_value

    if cycle >= injection.cycle_end:
        return signal_value

    return injection.injected_value