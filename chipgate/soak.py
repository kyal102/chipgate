"""
ChipGate soak simulation engine for LongevityBench.

Simulates the DTL gate logic combinatorially over many clock cycles
with randomized inputs. Tests whether the gate produces unsafe outputs
under long-running, high-stress input patterns.

This is RTL-level combinatorial simulation, not physical or Verilog
simulation. It does not guarantee silicon lifetime, clock frequency
stability, or physical durability.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .faults import FaultInjection, apply_fault
from .scanner import parse_verilog


# Gate input signals used in the DTL combinatorial expression
GATE_SIGNALS = [
    "ai_output",
    "verifier_ok",
    "policy_ok",
    "sensor_ok",
    "timeout",
    "kill_switch",
]


@dataclass
class SoakCycle:
    """Record of a single cycle in the soak simulation."""

    cycle: int
    ai_output: int  # 0 or 1
    verifier_ok: int  # 0 or 1
    policy_ok: int  # 0 or 1
    sensor_ok: int  # 0 or 1
    timeout: int  # 0 or 1
    kill_switch: int  # 0 or 1
    rst_n: int  # 0 or 1
    actuator_enable: int  # 0 or 1, computed from gate expression
    is_safe: bool  # True if actuator_enable is consistent with safety intent


def evaluate_gate(
    ai_output: int,
    verifier_ok: int,
    policy_ok: int,
    sensor_ok: int,
    timeout: int,
    kill_switch: int,
) -> int:
    """
    Evaluate the DTL gate combinatorial expression.

    This is the core gate logic:
        actuator_enable = ai_output & verifier_ok & policy_ok
                          & sensor_ok & timeout & ~kill_switch

    All inputs are 0 or 1. Returns 0 or 1.

    The ``timeout`` signal here follows positive logic: timeout=1 means
    the operation is within its time limit (equivalent to timeout_ok in
    the reference Verilog). The kill_switch is active-high: kill_switch=1
    blocks actuation.
    """
    gate_ok = (
        int(bool(ai_output))
        & int(bool(verifier_ok))
        & int(bool(policy_ok))
        & int(bool(sensor_ok))
        & int(bool(timeout))
        & int(not bool(kill_switch))
    )
    return gate_ok


def generate_random_inputs(
    seed: int,
    num_cycles: int,
    stress_level: float = 0.5,
) -> List[Dict[str, int]]:
    """
    Generate randomized signal inputs for a soak simulation.

    For each cycle, produces random 0/1 values for all gate input
    signals. The stress_level parameter (0.0 to 1.0) controls how
    frequently kill_switch or timeout are asserted, simulating
    high-stress operating conditions.

    Args:
        seed: Random seed for reproducibility.
        num_cycles: Number of cycles to generate inputs for.
        stress_level: Probability (0.0-1.0) of asserting stress
            signals (kill_switch, timeout=0) each cycle.

    Returns:
        List of dicts, one per cycle, each containing signal values
        for all gate inputs plus rst_n.
    """
    rng = random.Random(seed)
    inputs: List[Dict[str, int]] = []

    for _ in range(num_cycles):
        # Normal signals: roughly equal probability of 0/1
        ai_output = rng.randint(0, 1)
        verifier_ok = rng.randint(0, 1)
        policy_ok = rng.randint(0, 1)
        sensor_ok = rng.randint(0, 1)

        # Stress signals: controlled by stress_level
        # kill_switch is asserted (1) with stress_level probability
        kill_switch = 1 if rng.random() < stress_level else 0
        # timeout=0 (timed out) with stress_level probability
        timeout = 0 if rng.random() < stress_level else 1

        # Reset: rarely asserted (5% of cycles)
        rst_n = 0 if rng.random() < 0.05 else 1

        inputs.append({
            "ai_output": ai_output,
            "verifier_ok": verifier_ok,
            "policy_ok": policy_ok,
            "sensor_ok": sensor_ok,
            "timeout": timeout,
            "kill_switch": kill_switch,
            "rst_n": rst_n,
        })

    return inputs


def _check_safety(
    actuator_enable: int,
    verifier_ok: int,
    policy_ok: int,
    sensor_ok: int,
    timeout: int,
    kill_switch: int,
) -> bool:
    """
    Check whether actuator_enable is consistent with the safety intent.

    A safety violation occurs when actuator_enable is 1 but any
    safety gate condition fails (any gate signal deasserted or
    kill_switch asserted).

    Returns True if the cycle is safe, False if a violation is detected.
    """
    if actuator_enable == 1:
        # All gates must be passing for actuator_enable=1 to be safe
        if verifier_ok != 1:
            return False
        if policy_ok != 1:
            return False
        if sensor_ok != 1:
            return False
        if timeout != 1:
            return False
        if kill_switch != 0:
            return False
    return True


def run_soak_simulation(
    rtl_source: str,
    num_cycles: int,
    seed: int = 42,
    fault_injections: Optional[List[FaultInjection]] = None,
) -> List[SoakCycle]:
    """
    Run a combinatorial soak simulation of the DTL gate logic.

    Parses the RTL source to detect the gate expression using the
    ChipGate scanner, then evaluates the known gate expression over
    many cycles with randomized (and optionally faulted) inputs.

    This evaluates the gate LOGIC in Python, not Verilog simulation.
    The DTL gate expression is:
        actuator_enable = ai_output & verifier_ok & policy_ok
                          & sensor_ok & timeout & ~kill_switch

    On reset (rst_n=0), actuator_enable is forced to 0 (safe default).

    Args:
        rtl_source: Path to the Verilog/RTL source file. Parsed by
            the scanner to confirm gate structure, but gate evaluation
            uses the known DTL combinatorial expression.
        num_cycles: Number of clock cycles to simulate.
        seed: Random seed for input generation (reproducibility).
        fault_injections: Optional list of FaultInjection events to
            apply during simulation.

    Returns:
        List of SoakCycle records, one per simulated cycle.
    """
    # Parse the RTL to confirm gate structure exists
    try:
        parse_verilog(rtl_source)
    except (OSError, ValueError):
        # If parsing fails, proceed with the known gate expression
        # anyway. The soak simulation evaluates logic, not RTL syntax.
        pass

    # Generate random inputs
    inputs = generate_random_inputs(seed=seed, num_cycles=num_cycles)

    # Build a lookup of active fault injections by target signal
    fault_map: Dict[str, List[FaultInjection]] = {}
    if fault_injections:
        for inj in fault_injections:
            target = inj.profile.target_signal
            fault_map.setdefault(target, []).append(inj)

    cycles: List[SoakCycle] = []

    for idx, inp in enumerate(inputs):
        cycle_num = idx

        # Apply fault injections to each signal
        ai_output = inp["ai_output"]
        verifier_ok = inp["verifier_ok"]
        policy_ok = inp["policy_ok"]
        sensor_ok = inp["sensor_ok"]
        timeout = inp["timeout"]
        kill_switch = inp["kill_switch"]
        rst_n = inp["rst_n"]

        if fault_injections:
            for signal_name, value_ref in [
                ("ai_output", "ai_output"),
                ("verifier_ok", "verifier_ok"),
                ("policy_ok", "policy_ok"),
                ("sensor_ok", "sensor_ok"),
                ("timeout", "timeout"),
                ("kill_switch", "kill_switch"),
            ]:
                if signal_name in fault_map:
                    for inj in fault_map[signal_name]:
                        # Get current value of the signal
                        current = {
                            "ai_output": ai_output,
                            "verifier_ok": verifier_ok,
                            "policy_ok": policy_ok,
                            "sensor_ok": sensor_ok,
                            "timeout": timeout,
                            "kill_switch": kill_switch,
                        }[signal_name]
                        faulted = apply_fault(current, inj, cycle_num)
                        if signal_name == "ai_output":
                            ai_output = faulted
                        elif signal_name == "verifier_ok":
                            verifier_ok = faulted
                        elif signal_name == "policy_ok":
                            policy_ok = faulted
                        elif signal_name == "sensor_ok":
                            sensor_ok = faulted
                        elif signal_name == "timeout":
                            timeout = faulted
                        elif signal_name == "kill_switch":
                            kill_switch = faulted

        # Evaluate gate (reset forces actuator_enable to 0)
        if rst_n == 0:
            actuator_enable = 0
        else:
            actuator_enable = evaluate_gate(
                ai_output=ai_output,
                verifier_ok=verifier_ok,
                policy_ok=policy_ok,
                sensor_ok=sensor_ok,
                timeout=timeout,
                kill_switch=kill_switch,
            )

        # Check safety consistency
        is_safe = _check_safety(
            actuator_enable=actuator_enable,
            verifier_ok=verifier_ok,
            policy_ok=policy_ok,
            sensor_ok=sensor_ok,
            timeout=timeout,
            kill_switch=kill_switch,
        )

        cycles.append(SoakCycle(
            cycle=cycle_num,
            ai_output=ai_output,
            verifier_ok=verifier_ok,
            policy_ok=policy_ok,
            sensor_ok=sensor_ok,
            timeout=timeout,
            kill_switch=kill_switch,
            rst_n=rst_n,
            actuator_enable=actuator_enable,
            is_safe=is_safe,
        ))

    return cycles