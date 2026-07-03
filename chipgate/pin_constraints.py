"""
ChipGate pin and constraint validation for FPGA designs.

Validates that:
  - clock signal exists
  - reset signal exists
  - kill_switch input exists for safety-critical designs
  - actuator_enable is not mapped directly without gate evidence
  - no unassigned safety-critical outputs
  - no duplicate pin assignments
  - no unsafe output defaults (active-high actuators without explicit safe default)

Accepts constraints in two forms:
  1. A constraints JSON file mapping signal names to pin locations
  2. Direct RTL port analysis when no constraints file is provided
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from . import statuses as st
from .board_profiles import BoardProfile, get_board_profile


# Known safety-critical output signal patterns
_SAFETY_OUTPUT_PATTERNS = re.compile(
    r"(actuator|motor|relay|valve|heater|laser|solenoid|pump|drive|"
    r"trigger|fire|deploy|enable).*_out",
    re.IGNORECASE,
)

# Actuator enable signal patterns
_ACTUATOR_ENABLE_PATTERNS = re.compile(
    r"(actuator|motor|relay|valve|heater|laser|solenoid|pump|drive|"
    r"trigger|fire|deploy).*enable",
    re.IGNORECASE,
)


@dataclass
class PinConstraintResult:
    """Result of pin/constraint validation."""
    status: str
    checks: List[Dict[str, str]] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "checks": self.checks,
            "details": self.details,
        }


def _extract_ports(rtl_text: str) -> Dict[str, str]:
    """
    Extract port names and directions from Verilog text.

    Returns dict mapping port_name -> direction ("input" or "output").
    """
    ports: Dict[str, str] = {}

    # Match module port declarations: input clk, input rst_n, output reg [7:0] data_out
    # Also match: input wire clk, output wire [3:0] leds
    pattern = re.compile(
        r"^\s*(input|output)\s+(?:wire\s+|reg\s+)?(?:\[\d+:\d+\]\s+)?"
        r"(\w+)",
        re.MULTILINE,
    )

    for match in pattern.finditer(rtl_text):
        direction = match.group(1)
        port_name = match.group(2)
        # Filter out common non-port keywords
        if port_name not in ("begin", "end", "module", "endmodule"):
            ports[port_name] = direction

    return ports


def _find_clock_signal(ports: Dict[str, str], profile: BoardProfile) -> Tuple[bool, str]:
    """Check if a clock signal exists."""
    clock_name = profile.clock_pin_placeholder
    # Check for exact match or common clock naming patterns
    clock_candidates = {clock_name, "clk", "clock", "sys_clk"}
    for candidate in clock_candidates:
        if candidate in ports and ports[candidate] == "input":
            return True, f"Clock signal found: {candidate}"
    return False, f"No clock signal found (expected: {clock_name})"


def _find_reset_signal(ports: Dict[str, str], profile: BoardProfile) -> Tuple[bool, str]:
    """Check if a reset signal exists."""
    reset_name = profile.reset_pin_placeholder
    reset_candidates = {reset_name, "rst", "rst_n", "reset", "reset_n"}
    for candidate in reset_candidates:
        if candidate in ports and ports[candidate] == "input":
            return True, f"Reset signal found: {candidate}"
    return False, f"No reset signal found (expected: {reset_name})"


def _find_kill_switch(ports: Dict[str, str]) -> Tuple[bool, str]:
    """Check if a kill_switch input exists."""
    kill_candidates = {"kill_switch", "kill_switch_n", "estop", "emergency_stop"}
    for candidate in kill_candidates:
        if candidate in ports and ports[candidate] == "input":
            return True, f"Kill switch found: {candidate}"
    return False, "Kill switch input not found"


def _check_direct_actuator_mapping(
    rtl_text: str,
    constraints: Dict[str, str],
    profile: BoardProfile,
) -> Tuple[bool, str]:
    """
    Check that actuator enable signals are not directly mapped without
    gate evidence in the RTL.

    Evidence of gating: the RTL contains verifier_ok or policy_ok gating
    logic for the actuator signal.
    """
    actuator_signals = set()
    for port_name in constraints:
        if _ACTUATOR_ENABLE_PATTERNS.search(port_name):
            actuator_signals.add(port_name)

    if not actuator_signals:
        return True, "No actuator enable signals found in constraints"

    for sig in actuator_signals:
        # Check if this signal is gated by safety signals in the RTL
        # Look for patterns like: assign <sig> = ... & verifier_ok & policy_ok
        # or: <sig> <= ... & verifier_ok
        gated_pattern = re.compile(
            rf"{re.escape(sig)}\s*<=?\s*.+(verifier_ok|policy_ok)",
            re.DOTALL | re.IGNORECASE,
        )
        if not gated_pattern.search(rtl_text):
            # Also check if there's any safety gate mention nearby
            gate_present = "verifier_ok" in rtl_text and "policy_ok" in rtl_text
            if not gate_present:
                return False, (
                    f"Actuator signal '{sig}' is mapped without "
                    f"verifier_ok/policy_ok gate evidence"
                )

    return True, "Actuator signals properly gated"


def _check_duplicate_pins(
    constraints: Dict[str, str],
) -> Tuple[bool, str]:
    """Check for duplicate pin assignments."""
    pin_locations = {}
    for signal, pin in constraints.items():
        if pin in pin_locations:
            return False, (
                f"Duplicate pin assignment: '{pin}' is assigned to both "
                f"'{pin_locations[pin]}' and '{signal}'"
            )
        pin_locations[pin] = signal
    return True, "No duplicate pin assignments"


def _check_unassigned_safety_outputs(
    ports: Dict[str, str],
    constraints: Dict[str, str],
) -> Tuple[bool, str]:
    """Check that all safety-critical outputs have pin assignments."""
    unassigned = []
    for port_name, direction in ports.items():
        if direction == "output" and _SAFETY_OUTPUT_PATTERNS.search(port_name):
            if port_name not in constraints:
                unassigned.append(port_name)

    if unassigned:
        return False, (
            f"Safety-critical outputs without pin assignments: "
            f"{', '.join(unassigned)}"
        )
    return True, "All safety-critical outputs have pin assignments"


def _check_unsafe_defaults(rtl_text: str, ports: Dict[str, str]) -> Tuple[bool, str]:
    """
    Check that safety-critical outputs have explicit safe defaults
    (e.g., 1'b0 for active-high actuators, or 1'b1 for active-low).
    """
    for port_name, direction in ports.items():
        if direction == "output" and _SAFETY_OUTPUT_PATTERNS.search(port_name):
            # Check for initial/default assignment to safe value
            init_pattern = re.compile(
                rf"{re.escape(port_name)}\s*=\s*[01]'b[01]",
                re.IGNORECASE,
            )
            # Also check for default block in always
            default_pattern = re.compile(
                rf"default\s*:\s*{re.escape(port_name)}\s*<=",
                re.IGNORECASE,
            )
            # Also check for initial block
            initial_pattern = re.compile(
                rf"initial\s+{re.escape(port_name)}",
                re.IGNORECASE,
            )
            if not (init_pattern.search(rtl_text) or
                    default_pattern.search(rtl_text) or
                    initial_pattern.search(rtl_text)):
                return False, (
                    f"Safety-critical output '{port_name}' has no explicit "
                    f"safe default value"
                )

    return True, "All safety-critical outputs have explicit safe defaults"


def validate_pin_constraints(
    rtl_text: str,
    board_profile: BoardProfile,
    constraints: Optional[Dict[str, str]] = None,
) -> PinConstraintResult:
    """
    Validate pin constraints for an FPGA design.

    Args:
        rtl_text: Verilog source text.
        board_profile: Board profile to validate against.
        constraints: Optional dict mapping signal names to pin locations.
                     If None, validation is based on RTL port analysis only.

    Returns:
        PinConstraintResult with status and detailed checks.
    """
    checks: List[Dict[str, str]] = []
    all_pass = True

    ports = _extract_ports(rtl_text)
    if constraints is None:
        constraints = {}

    # Check 1: Clock
    clock_ok, clock_msg = _find_clock_signal(ports, board_profile)
    checks.append({"check": "clock", "status": "PASS" if clock_ok else "FAIL",
                    "message": clock_msg})
    if not clock_ok:
        all_pass = False

    # Check 2: Reset
    reset_ok, reset_msg = _find_reset_signal(ports, board_profile)
    checks.append({"check": "reset", "status": "PASS" if reset_ok else "FAIL",
                    "message": reset_msg})
    if not reset_ok:
        all_pass = False

    # Check 3: Kill switch (warning, not hard fail for non-safety designs)
    kill_ok, kill_msg = _find_kill_switch(ports)
    checks.append({"check": "kill_switch", "status": "PASS" if kill_ok else "FAIL",
                    "message": kill_msg})
    if not kill_ok:
        all_pass = False

    # Check 4: Direct actuator mapping (only if constraints provided)
    if constraints:
        act_ok, act_msg = _check_direct_actuator_mapping(rtl_text, constraints, board_profile)
        checks.append({"check": "actuator_gating", "status": "PASS" if act_ok else "FAIL",
                        "message": act_msg})
        if not act_ok:
            all_pass = False

        # Check 5: Duplicate pins
        dup_ok, dup_msg = _check_duplicate_pins(constraints)
        checks.append({"check": "duplicate_pins", "status": "PASS" if dup_ok else "FAIL",
                        "message": dup_msg})
        if not dup_ok:
            all_pass = False

        # Check 6: Unassigned safety outputs
        unassign_ok, unassign_msg = _check_unassigned_safety_outputs(ports, constraints)
        checks.append({"check": "unassigned_safety_outputs",
                        "status": "PASS" if unassign_ok else "FAIL",
                        "message": unassign_msg})
        if not unassign_ok:
            all_pass = False

    # Check 7: Unsafe output defaults
    default_ok, default_msg = _check_unsafe_defaults(rtl_text, ports)
    checks.append({"check": "safe_defaults", "status": "PASS" if default_ok else "FAIL",
                    "message": default_msg})
    if not default_ok:
        all_pass = False

    # Check 8: IO count constraint
    total_io = len(ports)
    if total_io > board_profile.maximum_io_count:
        checks.append({
            "check": "io_count",
            "status": "FAIL",
            "message": f"Design has {total_io} IO ports, "
                       f"board maximum is {board_profile.maximum_io_count}",
        })
        all_pass = False
    else:
        checks.append({
            "check": "io_count",
            "status": "PASS",
            "message": f"Design has {total_io} IO ports, "
                       f"within board maximum {board_profile.maximum_io_count}",
        })

    status = st.PIN_CONSTRAINT_PASS if all_pass else st.PIN_CONSTRAINT_FAIL
    return PinConstraintResult(status=status, checks=checks)


def load_constraints_from_json(constraints_path: str) -> Dict[str, str]:
    """Load pin constraints from a JSON file.

    Expected format:
    {
        "signal_name": "pin_location",
        ...
    }
    """
    text = Path(constraints_path).read_text(encoding="utf-8")
    data = json.loads(text)

    # Support both flat format and nested "pins" format
    if "pins" in data and isinstance(data["pins"], dict):
        return data["pins"]

    # Flat format: top-level keys are signal names
    return {k: str(v) for k, v in data.items() if not k.startswith("_")}