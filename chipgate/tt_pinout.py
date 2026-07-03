"""
ChipGate TinyTapeoutPrep — Pinout mapping and validation.

Defines the TinyTapeout pinout map for the public DTL safety gate design
and provides validation functions.

Pin mapping (TinyTapeout constraints: 8 inputs, 8 outputs):
  ui_in[0]  = ai_output
  ui_in[1]  = verifier_ok
  ui_in[2]  = policy_ok
  ui_in[3]  = sensor_ok
  ui_in[4]  = timeout
  ui_in[5]  = kill_switch
  ui_in[6]  = reset
  ui_in[7]  = reserved

  uo_out[0] = actuator_enable
  uo_out[1] = blocked
  uo_out[2] = failsafe
  uo_out[3] = approved
  uo_out[4] = evidence_pulse
  uo_out[5] = reserved
  uo_out[6] = reserved
  uo_out[7] = reserved
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import statuses as st

# ── Canonical pinout definition ──────────────────────────────────────────────

INPUT_PINOUT: Dict[str, Tuple[int, str]] = {
    "ai_output":   (0, "ui_in[0]"),
    "verifier_ok": (1, "ui_in[1]"),
    "policy_ok":   (2, "ui_in[2]"),
    "sensor_ok":   (3, "ui_in[3]"),
    "timeout":     (4, "ui_in[4]"),
    "kill_switch": (5, "ui_in[5]"),
    "reset":       (6, "ui_in[6]"),
}

OUTPUT_PINOUT: Dict[str, Tuple[int, str]] = {
    "actuator_enable": (0, "uo_out[0]"),
    "blocked":         (1, "uo_out[1]"),
    "failsafe":        (2, "uo_out[2]"),
    "approved":        (3, "uo_out[3]"),
    "evidence_pulse":  (4, "uo_out[4]"),
}

# Reserved pins
RESERVED_INPUTS = [7]
RESERVED_OUTPUTS = [5, 6, 7]

TT_INPUT_WIDTH = 8
TT_OUTPUT_WIDTH = 8


@dataclass
class PinoutValidationResult:
    """Result of pinout validation."""
    valid: bool = True
    status: str = st.TT_PINOUT_VALID
    issues: List[str] = field(default_factory=list)
    input_pins: Dict[str, str] = field(default_factory=dict)
    output_pins: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def get_canonical_pinout() -> Dict[str, str]:
    """Return the canonical pinout as a flat signal->pin mapping."""
    result = {}
    for sig, (_, pin) in INPUT_PINOUT.items():
        result[sig] = pin
    for sig, (_, pin) in OUTPUT_PINOUT.items():
        result[sig] = pin
    return result


def get_input_pinout() -> Dict[str, str]:
    """Return input pinout as signal->pin mapping."""
    return {sig: pin for sig, (_, pin) in INPUT_PINOUT.items()}


def get_output_pinout() -> Dict[str, str]:
    """Return output pinout as signal->pin mapping."""
    return {sig: pin for sig, (_, pin) in OUTPUT_PINOUT.items()}


def validate_pinout(pinout: Dict[str, str]) -> PinoutValidationResult:
    """Validate a pinout map against TinyTapeout constraints.

    Checks:
      - All required input signals are mapped
      - All required output signals are mapped
      - No duplicate pin assignments
      - Pins stay within ui_in[0:7] / uo_out[0:7]
      - No pin index out of range
    """
    result = PinoutValidationResult()
    result.input_pins = {k: v for k, v in pinout.items() if "ui_in" in v}
    result.output_pins = {k: v for k, v in pinout.items() if "uo_out" in v}

    # Check all required inputs
    for sig in INPUT_PINOUT:
        if sig not in pinout:
            result.issues.append(f"Missing required input signal: {sig}")
            result.valid = False

    # Check all required outputs
    for sig in OUTPUT_PINOUT:
        if sig not in pinout:
            result.issues.append(f"Missing required output signal: {sig}")
            result.valid = False

    # Check for duplicate pin assignments
    seen_pins = {}
    for sig, pin in pinout.items():
        if pin in seen_pins:
            result.issues.append(
                f"Duplicate pin assignment: {sig} and {seen_pins[pin]} "
                f"both map to {pin}"
            )
            result.valid = False
        seen_pins[pin] = sig

    # Check pin ranges
    for sig, pin in pinout.items():
        idx = _extract_pin_index(pin)
        if idx is None:
            result.issues.append(f"Invalid pin format for {sig}: {pin}")
            result.valid = False
            continue
        if "ui_in" in pin and idx >= TT_INPUT_WIDTH:
            result.issues.append(
                f"Input pin index {idx} out of range [0, {TT_INPUT_WIDTH - 1}] "
                f"for signal {sig}"
            )
            result.valid = False
        if "uo_out" in pin and idx >= TT_OUTPUT_WIDTH:
            result.issues.append(
                f"Output pin index {idx} out of range [0, {TT_OUTPUT_WIDTH - 1}] "
                f"for signal {sig}"
            )
            result.valid = False

    # Warnings for reserved pins
    for sig, pin in pinout.items():
        idx = _extract_pin_index(pin)
        if idx is not None:
            if "ui_in" in pin and idx in RESERVED_INPUTS:
                result.warnings.append(
                    f"Signal {sig} mapped to reserved input pin {pin}"
                )
            if "uo_out" in pin and idx in RESERVED_OUTPUTS:
                result.warnings.append(
                    f"Signal {sig} mapped to reserved output pin {pin}"
                )

    if not result.valid:
        result.status = st.TT_PINOUT_INVALID

    return result


def pinout_to_json(pinout: Dict[str, str]) -> str:
    """Serialise a pinout map to JSON."""
    return json.dumps(pinout, indent=2, sort_keys=True)


def load_pinout_from_json(json_str: str) -> Dict[str, str]:
    """Deserialise a pinout map from JSON."""
    data = json.loads(json_str)
    if not isinstance(data, dict):
        raise ValueError("Pinout JSON must be an object mapping signals to pins")
    return {str(k): str(v) for k, v in data.items()}


def _extract_pin_index(pin: str) -> Optional[int]:
    """Extract the numeric index from a pin string like 'ui_in[3]'."""
    if "[" in pin and "]" in pin:
        try:
            return int(pin.split("[")[1].split("]")[0])
        except (ValueError, IndexError):
            return None
    return None