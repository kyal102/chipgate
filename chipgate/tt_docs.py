"""
ChipGate TinyTapeoutPrep — Document and artifact generation.

Generates:
  - info.yaml: TinyTapeout project metadata
  - docs/info.md: Project information page
  - submission_checklist.md: Submission readiness checklist
  - Testbench Verilog for the core gate
"""

import os
from typing import Dict, List, Optional

from .tt_pinout import (
    INPUT_PINOUT,
    OUTPUT_PINOUT,
    get_canonical_pinout,
)


def generate_info_yaml(
    project_name: str = "tt_um_chipgate_dtl_gate",
    author: str = "ChipGate Contributors",
    description: str = (
        "A minimal DTL safety gate demonstrating verification-gated "
        "actuator control. Public demonstration design for TinyTapeout."
    ),
    repo: str = "https://github.com/user/chipgate",
    version: str = "0.5.0",
    top_module: str = "tt_um_chipgate_dtl_gate",
) -> str:
    """Generate info.yaml content for TinyTapeout submission.

    Returns the YAML content as a string. No external YAML library needed.
    """
    lines = []
    lines.append(f"project_name: {project_name}")
    lines.append(f"author: {author}")
    lines.append(f"description: {description}")
    lines.append(f"repo: {repo}")
    lines.append(f"version: {version}")
    lines.append(f"top_module: {top_module}")
    lines.append("")
    lines.append("# ChipGate TinyTapeoutPrep — auto-generated metadata")
    lines.append("# This does not guarantee Tiny Tapeout acceptance or fabrication.")
    lines.append("# Official submission requires CI on tinytapeout.com.")
    lines.append("")
    lines.append("# Communication protocol: none (combinational)")
    lines.append("# Inputs: ui_in[0:7] mapped to DTL gate signals")
    lines.append("# Outputs: uo_out[0:7] mapped to gate status signals")
    lines.append("")
    lines.append("# Pin mapping:")
    for sig in INPUT_PINOUT:
        _, pin = INPUT_PINOUT[sig]
        lines.append(f"#   {pin} = {sig}")
    for sig in OUTPUT_PINOUT:
        _, pin = OUTPUT_PINOUT[sig]
        lines.append(f"#   {pin} = {sig}")
    lines.append("")
    lines.append("# Limitations:")
    lines.append("# - Combinational design, no sequential state")
    lines.append("# - Does not guarantee silicon correctness or physical safety")
    lines.append("# - Requires official Tiny Tapeout CI for actual submission")
    lines.append("# - Not certified for safety-critical, medical, or defence use")

    return "\n".join(lines)


def generate_info_md(
    project_name: str = "tt_um_chipgate_dtl_gate",
    version: str = "0.5.0",
    pinout: Optional[Dict[str, str]] = None,
    safety_properties: Optional[List[str]] = None,
) -> str:
    """Generate docs/info.md content for TinyTapeout.

    Args:
        project_name: Project/module name.
        version: ChipGate version.
        pinout: Pin mapping. If None, uses canonical pinout.
        safety_properties: List of safety property descriptions.

    Returns:
        Markdown content as string.
    """
    if pinout is None:
        pinout = get_canonical_pinout()

    if safety_properties is None:
        safety_properties = [
            "kill_switch forces actuator_enable low",
            "timeout forces actuator_enable low",
            "reset forces actuator_enable low",
            "actuator_enable implies verifier_ok, policy_ok, and sensor_ok",
            "FAILSAFE state cannot jump directly to APPROVED",
        ]

    lines = []
    lines.append(f"# {project_name}")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(
        "A minimal DTL (Decision-Trust Layer) safety gate implemented as a "
        "combinational circuit for TinyTapeout. This is a public demonstration "
        "design that shows verification-gated actuator control logic. It does "
        "not guarantee silicon correctness, fabrication readiness, or physical safety."
    )
    lines.append("")
    lines.append("## How It Works")
    lines.append("")
    lines.append(
        "The gate takes 7 input signals (plus 1 reserved) and produces 5 output "
        "signals (plus 3 reserved). The primary output `actuator_enable` is only "
        "asserted when all verification conditions are met and no safety overrides "
        "are active. This is the core DTL safety pattern: an AI or autonomous "
        "system output must pass through multiple verification checks before it "
        "can drive a physical actuator."
    )
    lines.append("")
    lines.append("## Pin Mapping")
    lines.append("")
    lines.append("### Inputs (ui_in[0:7])")
    lines.append("")
    lines.append("| Pin | Signal | Description |")
    lines.append("|-----|--------|-------------|")
    pin_descriptions = {
        "ai_output": "AI/autonomous system output request",
        "verifier_ok": "Verification check passed",
        "policy_ok": "Policy compliance check passed",
        "sensor_ok": "Sensor health check passed",
        "timeout": "Operation timeout indicator",
        "kill_switch": "Emergency stop / kill switch",
        "reset": "System reset signal",
    }
    for sig in INPUT_PINOUT:
        _, pin = INPUT_PINOUT[sig]
        desc = pin_descriptions.get(sig, "Reserved")
        lines.append(f"| {pin} | {sig} | {desc} |")
    lines.append("| ui_in[7] | reserved | Unused |")
    lines.append("")
    lines.append("### Outputs (uo_out[0:7])")
    lines.append("")
    lines.append("| Pin | Signal | Description |")
    lines.append("|-----|--------|-------------|")
    out_descriptions = {
        "actuator_enable": "Gated actuator enable output",
        "blocked": "Request is blocked (safety violation)",
        "failsafe": "System is in failsafe state",
        "approved": "Request is approved and enabled",
        "evidence_pulse": "Evidence pulse (mirrors actuator_enable)",
    }
    for sig in OUTPUT_PINOUT:
        _, pin = OUTPUT_PINOUT[sig]
        desc = out_descriptions.get(sig, "Reserved")
        lines.append(f"| {pin} | {sig} | {desc} |")
    lines.append("| uo_out[5:7] | reserved | Unused |")
    lines.append("")
    lines.append("## Safety Properties")
    lines.append("")
    for i, prop in enumerate(safety_properties, 1):
        lines.append(f"{i}. {prop}")
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "- This is a combinational design with no sequential state or clocked logic."
    )
    lines.append(
        "- It does not guarantee silicon correctness, timing signoff, or power consumption."
    )
    lines.append(
        "- Passing TinyTapeoutPrep does not mean the design has been accepted by "
        "Tiny Tapeout, fabricated, or tested on real hardware."
    )
    lines.append(
        "- Not certified for safety-critical, medical, defence, or robotics use."
    )
    lines.append(
        "- Actual Tiny Tapeout submission requires official GitHub Actions CI, "
        "GDS build, and manual review on tinytapeout.com."
    )
    lines.append("")
    lines.append(f"Generated by ChipGate v{version}")

    return "\n".join(lines)


def generate_submission_checklist(
    checks: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Generate submission_checklist.md content.

    Args:
        checks: List of check dicts with 'id', 'name', 'status' keys.

    Returns:
        Markdown content as string.
    """
    if checks is None:
        checks = _default_checks()

    lines = []
    lines.append("# TinyTapeout Submission Checklist")
    lines.append("")
    lines.append(
        "This checklist tracks readiness for TinyTapeout submission. "
        "Each item must pass before the design is considered ready for "
        "manual review on tinytapeout.com. Passing this checklist does "
        "not guarantee Tiny Tapeout acceptance or fabrication."
    )
    lines.append("")
    lines.append("| # | Check | Status |")
    lines.append("|---|-------|--------|")

    for chk in checks:
        chk_id = chk.get("id", "?")
        name = chk.get("name", "Unknown")
        status = chk.get("status", "PENDING")
        status_mark = "PASS" if status == "PASS" else (
            "FAIL" if status == "FAIL" else status
        )
        lines.append(f"| {chk_id} | {name} | {status_mark} |")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- This is an automated structural checklist, not a substitute for "
        "official Tiny Tapeout CI or manual review."
    )
    lines.append(
        "- Evidence packs provide SHA-256 hashes for reproducibility but do "
        "not constitute fabrication signoff."
    )
    lines.append(
        "- LongevityBench, SiliconReadinessBench, and FPGABoardBench results "
        "gracefully degrade to SKIPPED when external tools are unavailable."
    )

    return "\n".join(lines)


def generate_testbench_verilog(
    core_module: str = "tiny_dtl_gate",
    testbench_module: str = "tb_tiny_dtl_gate",
) -> str:
    """Generate a simple Verilog testbench for the core DTL gate.

    Tests:
      1. All conditions met -> actuator_enable HIGH
      2. kill_switch active -> actuator_enable LOW
      3. timeout active -> actuator_enable LOW
      4. reset active -> actuator_enable LOW
      5. verifier_ok LOW -> actuator_enable LOW
      6. policy_ok LOW -> actuator_enable LOW
      7. sensor_ok LOW -> actuator_enable LOW
      8. ai_output LOW -> actuator_enable LOW
    """
    input_sigs = list(INPUT_PINOUT.keys())
    output_sigs = list(OUTPUT_PINOUT.keys())

    lines = []
    lines.append(f"// Testbench for {core_module}")
    lines.append("// Generated by ChipGate TinyTapeoutPrep")
    lines.append(f"module {testbench_module};")
    lines.append("")

    # Reg declarations
    lines.append("    // Inputs")
    for sig in input_sigs:
        lines.append(f"    reg {sig};")
    lines.append("")
    lines.append("    // Outputs")
    for sig in output_sigs:
        lines.append(f"    wire {sig};")
    lines.append("")

    # Instantiate core
    lines.append(f"    // DUT")
    lines.append(f"    {core_module} dut (")
    port_connections = []
    for sig in input_sigs:
        port_connections.append(f"        .{sig}({sig})")
    for sig in output_sigs:
        port_connections.append(f"        .{sig}({sig})")
    lines.append(",\n".join(port_connections))
    lines.append("    );")
    lines.append("")

    # Test cases
    lines.append("    // Test sequence")
    lines.append("    integer errors;")
    lines.append("")
    lines.append("    initial begin")
    lines.append("        errors = 0;")
    lines.append("")

    # Test 1: All conditions met
    lines.append("        // Test 1: All conditions met")
    _set_inputs(lines, input_sigs, ai_output=1, verifier_ok=1, policy_ok=1,
                sensor_ok=1, timeout=0, kill_switch=0, reset=0)
    lines.append("        #10;")
    _check_output(lines, "actuator_enable", 1, "all conditions met")
    _check_output(lines, "blocked", 0, "all conditions met")

    # Test 2: kill_switch
    lines.append("")
    lines.append("        // Test 2: kill_switch forces disable")
    _set_inputs(lines, input_sigs, ai_output=1, verifier_ok=1, policy_ok=1,
                sensor_ok=1, timeout=0, kill_switch=1, reset=0)
    lines.append("        #10;")
    _check_output(lines, "actuator_enable", 0, "kill_switch active")

    # Test 3: timeout
    lines.append("")
    lines.append("        // Test 3: timeout forces disable")
    _set_inputs(lines, input_sigs, ai_output=1, verifier_ok=1, policy_ok=1,
                sensor_ok=1, timeout=1, kill_switch=0, reset=0)
    lines.append("        #10;")
    _check_output(lines, "actuator_enable", 0, "timeout active")

    # Test 4: reset
    lines.append("")
    lines.append("        // Test 4: reset forces disable")
    _set_inputs(lines, input_sigs, ai_output=1, verifier_ok=1, policy_ok=1,
                sensor_ok=1, timeout=0, kill_switch=0, reset=1)
    lines.append("        #10;")
    _check_output(lines, "actuator_enable", 0, "reset active")

    # Test 5: verifier_ok LOW
    lines.append("")
    lines.append("        // Test 5: verifier_ok LOW blocks output")
    _set_inputs(lines, input_sigs, ai_output=1, verifier_ok=0, policy_ok=1,
                sensor_ok=1, timeout=0, kill_switch=0, reset=0)
    lines.append("        #10;")
    _check_output(lines, "actuator_enable", 0, "verifier_ok LOW")

    # Test 6: policy_ok LOW
    lines.append("")
    lines.append("        // Test 6: policy_ok LOW blocks output")
    _set_inputs(lines, input_sigs, ai_output=1, verifier_ok=1, policy_ok=0,
                sensor_ok=1, timeout=0, kill_switch=0, reset=0)
    lines.append("        #10;")
    _check_output(lines, "actuator_enable", 0, "policy_ok LOW")

    # Test 7: sensor_ok LOW
    lines.append("")
    lines.append("        // Test 7: sensor_ok LOW blocks output")
    _set_inputs(lines, input_sigs, ai_output=1, verifier_ok=1, policy_ok=1,
                sensor_ok=0, timeout=0, kill_switch=0, reset=0)
    lines.append("        #10;")
    _check_output(lines, "actuator_enable", 0, "sensor_ok LOW")

    # Test 8: ai_output LOW
    lines.append("")
    lines.append("        // Test 8: ai_output LOW -> no enable")
    _set_inputs(lines, input_sigs, ai_output=0, verifier_ok=1, policy_ok=1,
                sensor_ok=1, timeout=0, kill_switch=0, reset=0)
    lines.append("        #10;")
    _check_output(lines, "actuator_enable", 0, "ai_output LOW")

    # Summary
    lines.append("")
    lines.append("        // Summary")
    lines.append("        if (errors == 0)")
    lines.append('            $display("PASS: All tests passed");')
    lines.append("        else")
    lines.append('            $display("FAIL: %0d test(s) failed", errors);')
    lines.append("        $finish;")
    lines.append("    end")
    lines.append("")
    lines.append("endmodule")

    return "\n".join(lines)


def _set_inputs(lines, input_sigs, **values):
    """Append input assignments to lines."""
    for sig in input_sigs:
        val = values.get(sig, 0)
        lines.append(f"        {sig} = 1'b{val};")


def _check_output(lines, signal, expected, label):
    """Append an output check to lines."""
    lines.append(
        f'        if ({signal} !== 1\'b{expected}) begin '
        f'errors = errors + 1; '
        f'$display("FAIL [{label}]: {signal}=%b expected {expected}", {signal}); end'
    )


def _default_checks() -> List[Dict[str, str]]:
    """Return the 15 default submission checks."""
    return [
        {"id": "1", "name": "Top module file exists", "status": "PENDING"},
        {"id": "2", "name": "Top module name matches info.yaml", "status": "PENDING"},
        {"id": "3", "name": "No private imports or names", "status": "PENDING"},
        {"id": "4", "name": "No unsupported SystemVerilog constructs", "status": "PENDING"},
        {"id": "5", "name": "No inferred latches", "status": "PENDING"},
        {"id": "6", "name": "Clock signal documented", "status": "PENDING"},
        {"id": "7", "name": "Reset signal documented", "status": "PENDING"},
        {"id": "8", "name": "Pinout documented in info.yaml", "status": "PENDING"},
        {"id": "9", "name": "docs/info.md exists", "status": "PENDING"},
        {"id": "10", "name": "Testbench exists", "status": "PENDING"},
        {"id": "11", "name": "Safety properties listed", "status": "PENDING"},
        {"id": "12", "name": "ChipGate scan passes", "status": "PENDING"},
        {"id": "13", "name": "LongevityBench: pass or skip safely", "status": "PENDING"},
        {"id": "14", "name": "SiliconReadinessBench: pass or skip safely", "status": "PENDING"},
        {"id": "15", "name": "FPGABoardBench: pass or skip safely", "status": "PENDING"},
    ]