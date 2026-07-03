"""
ChipGate FPGA board profile definitions.

Each board profile defines:
  - clock_pin_placeholder: Expected clock pin name
  - reset_pin_placeholder: Expected reset pin name
  - safe_output_pins: List of allowed safe output pin names
  - forbidden_direct_actuator_pins: Pins that must never be directly driven
  - maximum_io_count: Maximum number of IO pins on the board
  - supported_constraints_format: Constraints file format (e.g. "pcf", "xdc", "simple_json")
  - fpga_family: FPGA family for synthesis (e.g. "ice40", "ecp5", "xilinx")
  - fpga_device: Target device string for place-and-route
  - package: Package name for place-and-route

All profiles are definitions only. No hardware connection is made.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BoardProfile:
    """Definition of an FPGA board profile."""
    name: str
    description: str
    clock_pin_placeholder: str
    reset_pin_placeholder: str
    safe_output_pins: List[str] = field(default_factory=list)
    forbidden_direct_actuator_pins: List[str] = field(default_factory=list)
    maximum_io_count: int = 16
    supported_constraints_format: str = "simple_json"
    fpga_family: str = "ice40"
    fpga_device: str = "lp384"
    package: str = "qn32"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "clock_pin_placeholder": self.clock_pin_placeholder,
            "reset_pin_placeholder": self.reset_pin_placeholder,
            "safe_output_pins": list(self.safe_output_pins),
            "forbidden_direct_actuator_pins": list(self.forbidden_direct_actuator_pins),
            "maximum_io_count": self.maximum_io_count,
            "supported_constraints_format": self.supported_constraints_format,
            "fpga_family": self.fpga_family,
            "fpga_device": self.fpga_device,
            "package": self.package,
        }


# ── Built-in Board Profiles ──────────────────────────────────────────────────

GENERIC_FPGA = BoardProfile(
    name="generic_fpga",
    description="Generic FPGA with no specific board constraints. "
                "Suitable for initial bring-up testing.",
    clock_pin_placeholder="clk",
    reset_pin_placeholder="rst_n",
    safe_output_pins=["led_out", "safe_out", "gate_out"],
    forbidden_direct_actuator_pins=["motor_out", "relay_out", "valve_out"],
    maximum_io_count=16,
    supported_constraints_format="simple_json",
    fpga_family="ice40",
    fpga_device="lp384",
    package="qn32",
)

ICE40_GENERIC = BoardProfile(
    name="ice40_generic",
    description="Generic Lattice iCE40 FPGA profile. "
                "Uses ice40 family synthesis with minimal constraints.",
    clock_pin_placeholder="clk",
    reset_pin_placeholder="rst_n",
    safe_output_pins=["led[0]", "led[1]", "led[2]", "led[3]",
                      "safe_output", "gate_output"],
    forbidden_direct_actuator_pins=["motor_pwm", "relay_ctrl", "heater_out"],
    maximum_io_count=32,
    supported_constraints_format="pcf",
    fpga_family="ice40",
    fpga_device="hx1k",
    package="tq144",
)

TINYFPGA_STYLE = BoardProfile(
    name="tinyfpga_style",
    description="TinyFPGA BX-style board profile. "
                "Small form factor with limited IO.",
    clock_pin_placeholder="clk",
    reset_pin_placeholder="rst_n",
    safe_output_pins=["led[0]", "led[1]", "led[2]", "led[3]",
                      "led[4]", "led[5]", "led[6]", "led[7]"],
    forbidden_direct_actuator_pins=["motor_out", "relay_out", "valve_out",
                                    "heater_out", "solenoid_out"],
    maximum_io_count=16,
    supported_constraints_format="pcf",
    fpga_family="ice40",
    fpga_device="lp8k",
    package="cm81",
)

ARTY_STYLE = BoardProfile(
    name="arty_style",
    description="Digilent Arty A7-style board profile. "
                "Larger Xilinx 7-series FPGA with more IO.",
    clock_pin_placeholder="clk",
    reset_pin_placeholder="rst_n",
    safe_output_pins=["led[0:3]", "rgb_led[0:2]", "safe_out",
                      "gate_out", "status_led"],
    forbidden_direct_actuator_pins=["motor_pwm", "relay_ctrl", "valve_ctrl",
                                    "heater_pwm", "solenoid_ctrl", "laser_out"],
    maximum_io_count=64,
    supported_constraints_format="xdc",
    fpga_family="xilinx",
    fpga_device="artix7",
    package="xc7a35tcpg236-1",
)

# ── Profile Registry ─────────────────────────────────────────────────────────

BOARD_PROFILES: Dict[str, BoardProfile] = {
    "generic_fpga": GENERIC_FPGA,
    "ice40_generic": ICE40_GENERIC,
    "tinyfpga_style": TINYFPGA_STYLE,
    "arty_style": ARTY_STYLE,
}


def get_board_profile(name: str) -> Optional[BoardProfile]:
    """Look up a board profile by name. Returns None if not found."""
    return BOARD_PROFILES.get(name)


def list_board_profiles() -> List[str]:
    """Return a list of all registered board profile names."""
    return sorted(BOARD_PROFILES.keys())


def validate_board_profile_name(name: str) -> bool:
    """Check whether a board profile name is known."""
    return name in BOARD_PROFILES