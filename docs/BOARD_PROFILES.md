# Board Profiles

FPGABoardBench includes built-in board profiles that define the constraints and characteristics of target FPGA boards. These are definitions only — no hardware connection is made.

## Available Profiles

### generic_fpga

The default profile for initial bring-up testing.

| Property | Value |
|----------|-------|
| Clock Pin | `clk` |
| Reset Pin | `rst_n` |
| Max IO | 16 |
| FPGA Family | ice40 |
| Device | lp384 |
| Package | qn32 |
| Constraints Format | simple_json |
| Safe Outputs | `led_out`, `safe_out`, `gate_out` |
| Forbidden Direct Actuator Pins | `motor_out`, `relay_out`, `valve_out` |

### ice40_generic

Generic Lattice iCE40 FPGA profile with more IO.

| Property | Value |
|----------|-------|
| Clock Pin | `clk` |
| Reset Pin | `rst_n` |
| Max IO | 32 |
| FPGA Family | ice40 |
| Device | hx1k |
| Package | tq144 |
| Constraints Format | pcf |
| Safe Outputs | `led[0]`–`led[3]`, `safe_output`, `gate_output` |
| Forbidden Direct Actuator Pins | `motor_pwm`, `relay_ctrl`, `heater_out` |

### tinyfpga_style

TinyFPGA BX-style small form factor board.

| Property | Value |
|----------|-------|
| Clock Pin | `clk` |
| Reset Pin | `rst_n` |
| Max IO | 16 |
| FPGA Family | ice40 |
| Device | lp8k |
| Package | cm81 |
| Constraints Format | pcf |
| Safe Outputs | `led[0]`–`led[7]` |
| Forbidden Direct Actuator Pins | `motor_out`, `relay_out`, `valve_out`, `heater_out`, `solenoid_out` |

### arty_style

Digilent Arty A7-style larger board with Xilinx 7-series FPGA.

| Property | Value |
|----------|-------|
| Clock Pin | `clk` |
| Reset Pin | `rst_n` |
| Max IO | 64 |
| FPGA Family | xilinx |
| Device | artix7 |
| Package | xc7a35tcpg236-1 |
| Constraints Format | xdc |
| Safe Outputs | `led[0:3]`, `rgb_led[0:2]`, `safe_out`, `gate_out`, `status_led` |
| Forbidden Direct Actuator Pins | `motor_pwm`, `relay_ctrl`, `valve_ctrl`, `heater_pwm`, `solenoid_ctrl`, `laser_out` |

## Profile Fields

Each board profile defines:

- **clock_pin_placeholder**: Expected clock signal name in the RTL
- **reset_pin_placeholder**: Expected reset signal name in the RTL
- **safe_output_pins**: List of output pin names considered safe for direct mapping
- **forbidden_direct_actuator_pins**: Pin names that should never be directly driven without safety gating
- **maximum_io_count**: Maximum number of IO ports the design may use
- **supported_constraints_format**: Constraints file format (pcf, xdc, simple_json)
- **fpga_family**: Target FPGA family for synthesis
- **fpga_device**: Target device for place-and-route
- **package**: Package name for place-and-route

## Using Profiles

```bash
# Use the default (generic_fpga)
python -m chipgate fpga --demo

# Use a specific profile
python -m chipgate fpga --demo --board-profile tinyfpga_style

# Use the Arty-style profile
python -m chipgate fpga --demo --board-profile arty_style
```

## Creating Custom Profiles

Custom profiles can be added programmatically by creating a `BoardProfile` instance and registering it:

```python
from chipgate.board_profiles import BoardProfile, BOARD_PROFILES

custom = BoardProfile(
    name="my_board",
    description="My custom FPGA board",
    clock_pin_placeholder="sys_clk",
    reset_pin_placeholder="sys_rst_n",
    safe_output_pins=["led_out"],
    forbidden_direct_actuator_pins=["motor_out"],
    maximum_io_count=20,
    supported_constraints_format="pcf",
    fpga_family="ice40",
    fpga_device="hx8k",
    package="ct256",
)

BOARD_PROFILES["my_board"] = custom
```