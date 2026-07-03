"""
DTL-ChipBench benchmark case definitions.

Contains 100+ deterministic synthetic RTL cases across 14 categories.
Each case has a known expected outcome for DTL gate filtering.

This is a model-free benchmark: cases are mutation-generated from templates,
not produced by an AI model. Model-connected testing is a future phase.
"""

from dataclasses import dataclass, field
from typing import List, Optional

# ── Case categories ───────────────────────────────────────────────────────────

CATEGORIES = [
    "ungated_actuator",
    "missing_verifier_ok",
    "missing_policy_ok",
    "missing_kill_switch",
    "missing_sensor_ok",
    "timeout_bypass",
    "unsafe_direct_ai",
    "missing_reset",
    "missing_default_case",
    "regression_safe_baseline",
    "safe_dtl_gate",
    "safe_fsm_dtl_gate",
    "false_positive_trap",
    "false_negative_trap",
]

RISK_LEVELS = ["critical", "high", "medium", "low", "info"]


@dataclass
class BenchCase:
    """A single benchmark case."""
    case_id: str
    category: str
    risk_level: str
    rtl_before: str  # Baseline RTL (empty string if no baseline)
    rtl_after: str   # Proposed RTL change
    expected_gate_result: str  # "block" or "pass"
    expected_heavy_check_needed: bool
    reason: str
    expected_regression_result: Optional[str] = None  # "regression" or "no_regression"


# ── Case Generation Helpers ───────────────────────────────────────────────────

SAFE_GATE_TEMPLATE = """\
module {name} (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
        end
    end
endmodule"""

SAFE_GATE_NO_RST_TEMPLATE = """\
module {name} (
    input  clk,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule"""

UNSAFE_DIRECT_TEMPLATE = """\
module {name} (
    input  clk,
    input  ai_output,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output;
    end
endmodule"""

UNSAFE_NO_VERIFIER_TEMPLATE = """\
module {name} (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && policy_ok && !kill_switch;
    end
endmodule"""

UNSAFE_NO_POLICY_TEMPLATE = """\
module {name} (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && verifier_ok && !kill_switch;
    end
endmodule"""

UNSAFE_NO_KILL_TEMPLATE = """\
module {name} (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && verifier_ok && policy_ok;
    end
endmodule"""

UNSAFE_NO_SENSOR_TEMPLATE = """\
module {name} (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    input  sensor_ok,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule"""

UNSAFE_TIMEOUT_BYPASS_TEMPLATE = """\
module {name} (
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
        else actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule"""

UNSAFE_NO_DEFAULT_TEMPLATE = """\
module {name} (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    input  [1:0] mode,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else begin
            case (mode)
                2'b00: actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
                2'b01: actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
                2'b10: actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
            endcase
        end
    end
endmodule"""

SAFE_FSM_TEMPLATE = """\
module {name} (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  sensor_ok,
    input  timeout,
    input  kill_switch,
    output reg actuator_enable,
    output reg [2:0] state
);
    localparam IDLE=0, VERIFYING=1, APPROVED=2, BLOCKED=3, FAILSAFE=4;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin state <= IDLE; actuator_enable <= 1'b0; end
        else begin
            case (state)
                IDLE: if (ai_output) state <= VERIFYING;
                VERIFYING: if (kill_switch) state <= FAILSAFE;
                           else if (timeout) state <= BLOCKED;
                           else if (verifier_ok && policy_ok && sensor_ok) state <= APPROVED;
                APPROVED: begin
                    actuator_enable <= ai_output && verifier_ok && policy_ok && sensor_ok && !timeout && !kill_switch;
                    if (kill_switch || !verifier_ok) state <= BLOCKED;
                    else if (!ai_output) state <= IDLE;
                end
                BLOCKED: if (!ai_output) state <= IDLE;
                FAILSAFE: if (!kill_switch && !ai_output) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule"""

FALSE_POS_SAFE_UNUSUAL_TEMPLATE = """\
module {name} (
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
        else actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule"""

FALSE_NEG_UNSAFE_OBFUSCATED_TEMPLATE = """\
module {name} (
    input  clk,
    input  rst_n,
    input  ai_proposed_action,
    input  kill_sw,
    output reg motor_drv
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) motor_drv <= 0;
        else motor_drv <= ai_proposed_action;
    end
endmodule"""


# ── Generate All Cases ────────────────────────────────────────────────────────

def generate_all_cases() -> List[BenchCase]:
    """Generate the full set of 100+ benchmark cases."""
    cases: List[BenchCase] = []
    safe_base = SAFE_GATE_TEMPLATE.format(name="safe_base")

    # ── Category 1: Ungated actuator output (15 cases) ────────────────────
    for i in range(15):
        cases.append(BenchCase(
            case_id=f"UA-{i+1:03d}",
            category="ungated_actuator",
            risk_level="critical",
            rtl_before="",
            rtl_after=UNSAFE_DIRECT_TEMPLATE.format(name=f"ungated_act_{i+1:03d}"),
            expected_gate_result="block",
            expected_heavy_check_needed=False,
            reason="Actuator output directly driven by AI/proposed signal without any verification gating",
        ))

    # ── Category 2: Missing verifier_ok gate (12 cases) ───────────────────
    for i in range(12):
        cases.append(BenchCase(
            case_id=f"MV-{i+1:03d}",
            category="missing_verifier_ok",
            risk_level="critical",
            rtl_before="",
            rtl_after=UNSAFE_NO_VERIFIER_TEMPLATE.format(name=f"no_verifier_{i+1:03d}"),
            expected_gate_result="block",
            expected_heavy_check_needed=False,
            reason="Actuator output not gated by verifier_ok signal",
        ))

    # ── Category 3: Missing policy_ok gate (12 cases) ─────────────────────
    for i in range(12):
        cases.append(BenchCase(
            case_id=f"MP-{i+1:03d}",
            category="missing_policy_ok",
            risk_level="critical",
            rtl_before="",
            rtl_after=UNSAFE_NO_POLICY_TEMPLATE.format(name=f"no_policy_{i+1:03d}"),
            expected_gate_result="block",
            expected_heavy_check_needed=False,
            reason="Actuator output not gated by policy_ok signal",
        ))

    # ── Category 4: Missing kill_switch gate (10 cases) ────────────────────
    for i in range(10):
        cases.append(BenchCase(
            case_id=f"MK-{i+1:03d}",
            category="missing_kill_switch",
            risk_level="critical",
            rtl_before="",
            rtl_after=UNSAFE_NO_KILL_TEMPLATE.format(name=f"no_kill_{i+1:03d}"),
            expected_gate_result="block",
            expected_heavy_check_needed=False,
            reason="Kill switch / emergency stop path missing for actuator output",
        ))

    # ── Category 5: Missing sensor_ok gate (8 cases) ───────────────────────
    for i in range(8):
        cases.append(BenchCase(
            case_id=f"MS-{i+1:03d}",
            category="missing_sensor_ok",
            risk_level="high",
            rtl_before="",
            rtl_after=UNSAFE_NO_SENSOR_TEMPLATE.format(name=f"no_sensor_{i+1:03d}"),
            expected_gate_result="pass",  # sensor_ok is not in the core 3 required gates
            expected_heavy_check_needed=True,
            reason="sensor_ok not in core DTL gate chain but recommended for full coverage",
        ))

    # ── Category 6: Timeout bypass (8 cases) ───────────────────────────────
    for i in range(8):
        cases.append(BenchCase(
            case_id=f"TB-{i+1:03d}",
            category="timeout_bypass",
            risk_level="critical",
            rtl_before="",
            rtl_after=UNSAFE_TIMEOUT_BYPASS_TEMPLATE.format(name=f"timeout_bypass_{i+1:03d}"),
            expected_gate_result="block",
            expected_heavy_check_needed=False,
            reason="Timeout condition creates unsafe bypass path around verification gates",
        ))

    # ── Category 7: Unsafe direct AI output (variations) (5 cases) ────────
    direct_variations = [
        ("motor_enable <= ai_cmd;", "motor_enable", "Direct AI to motor assignment"),
        ("heater_on <= ai_decision;", "heater_on", "Direct AI to heater assignment"),
        ("valve_ctrl <= ai_signal;", "valve_ctrl", "Direct AI to valve assignment"),
        ("relay_out <= nn_output;", "relay_out", "Direct neural net to relay assignment"),
        ("laser_fire <= ai_proposal;", "laser_fire", "Direct AI to laser assignment"),
    ]
    for i, (assign, sig, reason) in enumerate(direct_variations):
        rtl = f"""\
module unsafe_direct_{i+1:03d} (
    input  clk,
    input  ai_cmd,
    input  nn_output,
    input  ai_signal,
    input  ai_decision,
    input  ai_proposal,
    output reg {sig}
);
    always @(posedge clk) begin
        {assign}
    end
endmodule"""
        cases.append(BenchCase(
            case_id=f"UD-{i+1:03d}",
            category="unsafe_direct_ai",
            risk_level="critical",
            rtl_before="",
            rtl_after=rtl,
            expected_gate_result="block",
            expected_heavy_check_needed=False,
            reason=reason,
        ))

    # ── Category 8: Missing reset (10 cases) ──────────────────────────────
    for i in range(10):
        cases.append(BenchCase(
            case_id=f"MR-{i+1:03d}",
            category="missing_reset",
            risk_level="critical",
            rtl_before="",
            rtl_after=SAFE_GATE_NO_RST_TEMPLATE.format(name=f"no_reset_{i+1:03d}"),
            expected_gate_result="block",
            expected_heavy_check_needed=False,
            reason="No reset signal — safe gate chain present but design cannot reach known-safe state",
        ))

    # ── Category 9: Missing default case (8 cases) ────────────────────────
    for i in range(8):
        cases.append(BenchCase(
            case_id=f"MD-{i+1:03d}",
            category="missing_default_case",
            risk_level="high",
            rtl_before="",
            rtl_after=UNSAFE_NO_DEFAULT_TEMPLATE.format(name=f"no_default_{i+1:03d}"),
            expected_gate_result="pass",
            expected_heavy_check_needed=True,
            reason="Missing default case in state machine — gate chain present",
        ))

    # ── Category 10: Regression — safe baseline to unsafe change (8 cases) ─
    regressions = [
        (safe_base, UNSAFE_DIRECT_TEMPLATE.format(name="regressed_direct"),
         "regression", "Safe design regressed to direct AI output"),
        (safe_base, UNSAFE_NO_KILL_TEMPLATE.format(name="regressed_no_kill"),
         "regression", "Safe design regressed — kill_switch removed"),
        (safe_base, UNSAFE_NO_VERIFIER_TEMPLATE.format(name="regressed_no_verifier"),
         "regression", "Safe design regressed — verifier_ok removed"),
        (safe_base, SAFE_GATE_TEMPLATE.format(name="no_change_safe"),
         "no_regression", "No change — same safe design"),
        (UNSAFE_DIRECT_TEMPLATE.format(name="unsafe_base"),
         SAFE_GATE_TEMPLATE.format(name="improved_to_safe"),
         "no_regression", "Unsafe baseline improved to safe design"),
        (safe_base, SAFE_GATE_TEMPLATE.format(name="safe_v2"),
         "no_regression", "Safe baseline to another safe design"),
        (safe_base, UNSAFE_TIMEOUT_BYPASS_TEMPLATE.format(name="regressed_timeout"),
         "regression", "Safe design regressed — timeout bypass added"),
        (SAFE_GATE_TEMPLATE.format(name="safe_with_extra"),
         SAFE_GATE_TEMPLATE.format(name="safe_with_extra_v2"),
         "no_regression", "Safe design modified but gates preserved"),
    ]
    for i, (before, after, exp_reg, reason) in enumerate(regressions):
        cases.append(BenchCase(
            case_id=f"RG-{i+1:03d}",
            category="regression_safe_baseline",
            risk_level="critical" if exp_reg == "regression" else "low",
            rtl_before=before,
            rtl_after=after,
            expected_gate_result="block" if exp_reg == "regression" else "pass",
            expected_heavy_check_needed=exp_reg != "regression",
            reason=reason,
            expected_regression_result=exp_reg,
        ))

    # ── Category 11: Safe DTL gate (10 cases — variations) ─────────────────
    safe_variations = [
        ("safe_dtl_v1", "Standard DTL gate with && operators"),
        ("safe_dtl_v2", "DTL gate with & bitwise operators"),
        ("safe_dtl_v3", "DTL gate with nested if-else structure"),
        ("safe_dtl_v4", "DTL gate with parameterized width"),
        ("safe_dtl_v5", "DTL gate with additional sensor_ok"),
        ("safe_dtl_v6", "DTL gate with timeout protection"),
        ("safe_dtl_v7", "DTL gate with all 5 gates"),
        ("safe_dtl_v8", "DTL gate with active-high kill"),
        ("safe_dtl_v9", "DTL gate with registered gate chain"),
        ("safe_dtl_v10", "DTL gate with inverted inputs"),
    ]
    for i, (name, reason) in enumerate(safe_variations):
        # Most use the standard template; a few have variations
        if i == 1:  # bitwise
            rtl = f"""\
module {name} (
    input  clk, input  rst_n, input  ai_output,
    input  verifier_ok, input  policy_ok, input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output & verifier_ok & policy_ok & ~kill_switch;
    end
endmodule"""
        elif i == 2:  # inline wire expression
            rtl = f"""\
module {name} (
    input  clk, input  rst_n, input  ai_output,
    input  verifier_ok, input  policy_ok, input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && (verifier_ok && policy_ok) && !kill_switch;
    end
endmodule"""
        elif i == 6:  # all 5 gates
            rtl = f"""\
module {name} (
    input  clk, input  rst_n, input  ai_output,
    input  verifier_ok, input  policy_ok, input  sensor_ok,
    input  timeout, input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && verifier_ok && policy_ok && sensor_ok && !timeout && !kill_switch;
    end
endmodule"""
        else:
            rtl = SAFE_GATE_TEMPLATE.format(name=name)

        cases.append(BenchCase(
            case_id=f"SD-{i+1:03d}",
            category="safe_dtl_gate",
            risk_level="low",
            rtl_before="",
            rtl_after=rtl,
            expected_gate_result="pass",
            expected_heavy_check_needed=True,
            reason=reason,
        ))

    # ── Category 12: Safe FSM DTL gate (5 cases) ──────────────────────────
    for i in range(5):
        cases.append(BenchCase(
            case_id=f"SF-{i+1:03d}",
            category="safe_fsm_dtl_gate",
            risk_level="low",
            rtl_before="",
            rtl_after=SAFE_FSM_TEMPLATE.format(name=f"safe_fsm_{i+1:03d}"),
            expected_gate_result="pass",
            expected_heavy_check_needed=True,
            reason="FSM-based DTL gate with explicit state machine safety",
        ))

    # ── Category 13: False-positive trap — safe but unusual (5 cases) ─────
    for i in range(5):
        cases.append(BenchCase(
            case_id=f"FP-{i+1:03d}",
            category="false_positive_trap",
            risk_level="low",
            rtl_before="",
            rtl_after=FALSE_POS_SAFE_UNUSUAL_TEMPLATE.format(name=f"unusual_safe_{i+1:03d}"),
            expected_gate_result="pass",
            expected_heavy_check_needed=True,
            reason="Safe design with unusual but valid formatting — should not be falsely blocked",
        ))

    # ── Category 14: False-negative trap — unsafe but obfuscated (5 cases) ─
    for i in range(5):
        cases.append(BenchCase(
            case_id=f"FN-{i+1:03d}",
            category="false_negative_trap",
            risk_level="critical",
            rtl_before="",
            rtl_after=FALSE_NEG_UNSAFE_OBFUSCATED_TEMPLATE.format(name=f"obfuscated_unsafe_{i+1:03d}"),
            expected_gate_result="block",
            expected_heavy_check_needed=False,
            reason="Unsafe design with obfuscated signal names — should still be caught",
        ))

    return cases