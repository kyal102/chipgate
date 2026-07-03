"""
Tests for FPGABoardBench (Phase 8).

Covers:
- toolchain status works when tools are missing
- safe FPGA design passes safety precheck
- unsafe direct output blocked
- missing kill_switch detected
- clock missing detected
- reset missing detected
- duplicate pin assignment detected
- unassigned safety output detected
- board evidence attached and parsed
- board evidence failure detected
- bitstream readiness skipped safely when tools missing
- artifact hashes stable
- evidence record created
- HTML report generated
- JSON schema stable
- no private JARVI3 imports
- no secrets
- no shell=True
- English-only output
- board profile validation
- pin constraint checks detail
- FPGA synth skipped when tools missing
- place-route skipped when tools missing
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Path setup ──────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Import modules under test ───────────────────────────────────────────────

from chipgate.board_profiles import (
    BoardProfile, get_board_profile, list_board_profiles,
    validate_board_profile_name, BOARD_PROFILES,
    GENERIC_FPGA, ICE40_GENERIC, TINYFPGA_STYLE, ARTY_STYLE,
)
from chipgate.pin_constraints import (
    PinConstraintResult, validate_pin_constraints,
    load_constraints_from_json, _extract_ports,
)
from chipgate.fpga_board import (
    FPGASynthResult, PlaceRouteResult,
    run_fpga_synthesis, run_place_and_route,
)
from chipgate.bitstream_readiness import (
    BitstreamReadinessResult, check_bitstream_readiness,
)
from chipgate.fpgabench import (
    FPGABenchResult, FPGADesignResult,
    run_fpgabench, check_fpga_toolchain,
    format_fpga_toolchain_status,
    get_demo_designs, _create_evidence_record, _load_board_evidence,
    _run_safety_precheck, _run_board_profile_check,
    _run_pin_constraints,
)
from chipgate.fpga_report import generate_fpga_html
from chipgate import statuses as st


# ── Fixture RTL texts ───────────────────────────────────────────────────────

SAFE_FPGA_RTL = """\
module safe_dtl_gate_fpga (
    input  wire clk,
    input  wire rst_n,
    input  wire kill_switch,
    input  wire verifier_ok,
    input  wire policy_ok,
    input  wire ai_output,
    output reg  actuator_enable,
    output reg  safe_out
);
    initial begin
        actuator_enable = 1'b0;
        safe_out = 1'b0;
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
            safe_out <= 1'b0;
        end else begin
            actuator_enable <= ai_output & verifier_ok & policy_ok & ~kill_switch;
            safe_out <= verifier_ok & policy_ok & ~kill_switch;
        end
    end
endmodule
"""

UNSAFE_DIRECT_RTL = """\
module unsafe_direct_output_fpga (
    input  wire clk,
    input  wire rst_n,
    input  wire ai_output,
    output reg  actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output;
        end
    end
endmodule
"""

NO_CLOCK_RTL = """\
module no_clock_design (
    input  wire rst_n,
    input  wire data_in,
    output reg  data_out
);
    always @(posedge rst_n) begin
        data_out <= data_in;
    end
endmodule
"""

NO_RESET_RTL = """\
module no_reset_design (
    input  wire clk,
    input  wire data_in,
    output reg  data_out
);
    always @(posedge clk) begin
        data_out <= data_in;
    end
endmodule
"""


class TestBoardProfiles(unittest.TestCase):
    """Tests for board profile definitions and lookup."""

    def test_all_profiles_exist(self):
        expected = ["generic_fpga", "ice40_generic", "tinyfpga_style", "arty_style"]
        profiles = list_board_profiles()
        self.assertEqual(sorted(profiles), sorted(expected))

    def test_get_known_profile(self):
        profile = get_board_profile("generic_fpga")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "generic_fpga")
        self.assertEqual(profile.clock_pin_placeholder, "clk")
        self.assertEqual(profile.maximum_io_count, 16)

    def test_get_unknown_profile(self):
        profile = get_board_profile("nonexistent_board")
        self.assertIsNone(profile)

    def test_validate_known_profile(self):
        self.assertTrue(validate_board_profile_name("generic_fpga"))
        self.assertTrue(validate_board_profile_name("tinyfpga_style"))

    def test_validate_unknown_profile(self):
        self.assertFalse(validate_board_profile_name("nonexistent_board"))

    def test_profile_to_dict(self):
        profile = GENERIC_FPGA
        d = profile.to_dict()
        self.assertEqual(d["name"], "generic_fpga")
        self.assertEqual(d["maximum_io_count"], 16)
        self.assertIn("safe_output_pins", d)
        self.assertIn("forbidden_direct_actuator_pins", d)

    def test_arty_has_more_io(self):
        self.assertGreater(ARTY_STYLE.maximum_io_count, GENERIC_FPGA.maximum_io_count)

    def test_all_profiles_have_required_fields(self):
        for name, profile in BOARD_PROFILES.items():
            self.assertTrue(profile.clock_pin_placeholder, f"{name} missing clock")
            self.assertTrue(profile.reset_pin_placeholder, f"{name} missing reset")
            self.assertGreater(profile.maximum_io_count, 0, f"{name} max_io=0")
            self.assertTrue(profile.fpga_family, f"{name} missing fpga_family")


class TestPinConstraints(unittest.TestCase):
    """Tests for pin constraint validation."""

    def test_safe_design_passes(self):
        result = validate_pin_constraints(SAFE_FPGA_RTL, GENERIC_FPGA)
        self.assertEqual(result.status, st.PIN_CONSTRAINT_PASS)

    def test_missing_clock_detected(self):
        result = validate_pin_constraints(NO_CLOCK_RTL, GENERIC_FPGA)
        self.assertEqual(result.status, st.PIN_CONSTRAINT_FAIL)
        check_names = [c["check"] for c in result.checks]
        self.assertIn("clock", check_names)
        clock_check = next(c for c in result.checks if c["check"] == "clock")
        self.assertEqual(clock_check["status"], "FAIL")

    def test_missing_reset_detected(self):
        result = validate_pin_constraints(NO_RESET_RTL, GENERIC_FPGA)
        self.assertEqual(result.status, st.PIN_CONSTRAINT_FAIL)
        check_names = [c["check"] for c in result.checks]
        self.assertIn("reset", check_names)

    def test_missing_kill_switch_detected(self):
        # safe design has kill switch, but let's test a design without it
        no_kill = """\
module no_kill (
    input clk,
    input rst_n,
    input verifier_ok,
    output reg out
);
    initial out = 1'b0;
    always @(posedge clk) out <= verifier_ok;
endmodule
"""
        result = validate_pin_constraints(no_kill, GENERIC_FPGA)
        self.assertEqual(result.status, st.PIN_CONSTRAINT_FAIL)
        kill_check = next(c for c in result.checks if c["check"] == "kill_switch")
        self.assertEqual(kill_check["status"], "FAIL")

    def test_duplicate_pin_assignment_detected(self):
        constraints = {"clk": "PIN_1", "rst_n": "PIN_2", "led_out": "PIN_3",
                       "safe_out": "PIN_3"}  # duplicate PIN_3
        result = validate_pin_constraints(SAFE_FPGA_RTL, GENERIC_FPGA, constraints)
        self.assertEqual(result.status, st.PIN_CONSTRAINT_FAIL)
        dup_check = next(c for c in result.checks if c["check"] == "duplicate_pins")
        self.assertEqual(dup_check["status"], "FAIL")

    def test_no_duplicate_pins_passes(self):
        constraints = {"clk": "PIN_1", "rst_n": "PIN_2", "safe_out": "PIN_3"}
        result = validate_pin_constraints(SAFE_FPGA_RTL, GENERIC_FPGA, constraints)
        dup_check = next(c for c in result.checks if c["check"] == "duplicate_pins")
        self.assertEqual(dup_check["status"], "PASS")

    def test_extract_ports(self):
        ports = _extract_ports(SAFE_FPGA_RTL)
        self.assertIn("clk", ports)
        self.assertEqual(ports["clk"], "input")
        self.assertIn("actuator_enable", ports)
        self.assertEqual(ports["actuator_enable"], "output")

    def test_io_count_exceeds_board(self):
        # Generate a design with too many ports
        port_lines = ["    input  wire clk,", "    input  wire rst_n,"]
        for i in range(20):
            port_lines.append(f"    input  wire in_{i},")
        port_lines.append("    output reg out;")
        body = "always @(posedge clk) out <= in_0;"
        rtl = f"module big_design(\n{chr(10).join(port_lines)}\n);\n{body}\nendmodule"
        result = validate_pin_constraints(rtl, GENERIC_FPGA)
        io_check = next(c for c in result.checks if c["check"] == "io_count")
        self.assertEqual(io_check["status"], "FAIL")

    def test_result_to_dict(self):
        result = validate_pin_constraints(SAFE_FPGA_RTL, GENERIC_FPGA)
        d = result.to_dict()
        self.assertIn("status", d)
        self.assertIn("checks", d)

    def test_load_constraints_from_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"clk": "PIN_1", "rst_n": "PIN_2"}, f)
            f.flush()
            constraints = load_constraints_from_json(f.name)
        self.assertEqual(constraints["clk"], "PIN_1")
        self.assertEqual(constraints["rst_n"], "PIN_2")
        os.unlink(f.name)

    def test_load_constraints_nested_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"pins": {"clk": "PIN_1", "rst_n": "PIN_2"}}, f)
            f.flush()
            constraints = load_constraints_from_json(f.name)
        self.assertEqual(constraints["clk"], "PIN_1")
        os.unlink(f.name)


class TestFPGASynthToolMissing(unittest.TestCase):
    """Tests for FPGA synthesis when tools are missing."""

    @patch("chipgate.fpga_board._find_executable", return_value=None)
    def test_fpga_synth_skipped_when_yosys_missing(self, mock_find):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write(SAFE_FPGA_RTL)
            f.flush()
            result = run_fpga_synthesis(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.FPGA_SYNTH_SKIPPED_TOOL_MISSING)
        self.assertFalse(result.yosys_available)

    @patch("chipgate.fpga_board._find_executable", return_value=None)
    def test_pnr_skipped_when_nextpnr_missing(self, mock_find):
        result = run_place_and_route(
            synth_json_path="/tmp/nonexistent.json",
            fpga_family="ice40",
        )
        self.assertEqual(result.status, st.PLACE_ROUTE_SKIPPED_TOOL_MISSING)
        self.assertFalse(result.nextpnr_available)


class TestBitstreamReadinessToolMissing(unittest.TestCase):
    """Tests for bitstream readiness when tools are missing."""

    @patch("chipgate.bitstream_readiness._check_tools", return_value={
        "yosys": None, "nextpnr": None, "icestorm": None, "openFPGALoader": None,
    })
    def test_bitstream_skipped_when_tools_missing(self, mock_check):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write(SAFE_FPGA_RTL)
            f.flush()
            result = check_bitstream_readiness(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.BITSTREAM_SKIPPED_TOOL_MISSING)
        self.assertFalse(result.tools_available.get("yosys", False))


class TestSafetyPrecheck(unittest.TestCase):
    """Tests for Stage 1: RTL safety precheck."""

    def test_safe_design_passes_precheck(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write(SAFE_FPGA_RTL)
            f.flush()
            status, statuses_list, _scan = _run_safety_precheck(f.name)
        os.unlink(f.name)
        self.assertEqual(status, st.RTL_SCAN_PASS)

    def test_unsafe_design_fails_precheck(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write(UNSAFE_DIRECT_RTL)
            f.flush()
            status, statuses_list, _scan = _run_safety_precheck(f.name)
        os.unlink(f.name)
        self.assertEqual(status, st.RTL_SCAN_FAIL)


class TestBoardProfileCheck(unittest.TestCase):
    """Tests for Stage 2: Board profile validation."""

    def test_valid_profile(self):
        status, info = _run_board_profile_check("generic_fpga")
        self.assertEqual(status, st.BOARD_PROFILE_VALID)
        self.assertIn("name", info)

    def test_invalid_profile(self):
        status, info = _run_board_profile_check("nonexistent")
        self.assertEqual(status, st.BOARD_PROFILE_INVALID)
        self.assertEqual(info, {})


class TestBoardEvidence(unittest.TestCase):
    """Tests for board evidence import."""

    def test_missing_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            status, data = _load_board_evidence(td, "nonexistent")
        self.assertEqual(status, st.BOARD_EVIDENCE_MISSING)

    def test_valid_evidence_attached(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = {
                "board_profile": "generic_fpga",
                "design_id": "test_design",
                "test_cycles": 10000,
                "unsafe_enable_events": 0,
                "kill_switch_bypasses": 0,
                "reset_glitches": 0,
                "tester": "ci",
                "notes": "",
            }
            ev_path = os.path.join(td, "test_design.board_evidence.json")
            Path(ev_path).write_text(json.dumps(evidence), encoding="utf-8")
            status, data = _load_board_evidence(td, "test_design")
        self.assertEqual(status, st.BOARD_EVIDENCE_ATTACHED)
        self.assertEqual(data["test_cycles"], 10000)

    def test_unsafe_events_cause_fail(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = {
                "board_profile": "generic_fpga",
                "design_id": "test_design",
                "test_cycles": 10000,
                "unsafe_enable_events": 3,
                "kill_switch_bypasses": 1,
                "reset_glitches": 0,
                "tester": "ci",
            }
            ev_path = os.path.join(td, "test_design.board_evidence.json")
            Path(ev_path).write_text(json.dumps(evidence), encoding="utf-8")
            status, data = _load_board_evidence(td, "test_design")
        self.assertEqual(status, st.BOARD_EVIDENCE_FAIL)

    def test_malformed_json_fails(self):
        with tempfile.TemporaryDirectory() as td:
            ev_path = os.path.join(td, "bad.board_evidence.json")
            Path(ev_path).write_text("not json{{{", encoding="utf-8")
            status, data = _load_board_evidence(td, "bad")
        self.assertEqual(status, st.BOARD_EVIDENCE_FAIL)


class TestArtifactHashes(unittest.TestCase):
    """Tests for artifact hash stability."""

    def test_evidence_hash_stable(self):
        ev1 = _create_evidence_record(
            design_id="test",
            rtl_text=SAFE_FPGA_RTL,
            board_profile="generic_fpga",
            safety_result="RTL_SCAN_PASS",
            pin_result="PIN_CONSTRAINT_PASS",
            fpga_synth_result="FPGA_SYNTH_SKIPPED_TOOL_MISSING",
            place_route_result="PLACE_ROUTE_SKIPPED_TOOL_MISSING",
            bitstream_result="BITSTREAM_SKIPPED_TOOL_MISSING",
            board_evidence_result="BOARD_EVIDENCE_MISSING",
            tool_versions={},
            replay_command="python -m chipgate fpga --demo",
        )
        ev2 = _create_evidence_record(
            design_id="test",
            rtl_text=SAFE_FPGA_RTL,
            board_profile="generic_fpga",
            safety_result="RTL_SCAN_PASS",
            pin_result="PIN_CONSTRAINT_PASS",
            fpga_synth_result="FPGA_SYNTH_SKIPPED_TOOL_MISSING",
            place_route_result="PLACE_ROUTE_SKIPPED_TOOL_MISSING",
            bitstream_result="BITSTREAM_SKIPPED_TOOL_MISSING",
            board_evidence_result="BOARD_EVIDENCE_MISSING",
            tool_versions={},
            replay_command="python -m chipgate fpga --demo",
        )
        self.assertEqual(ev1["certificate_hash"], ev2["certificate_hash"])
        self.assertEqual(ev1["rtl_hash"], ev2["rtl_hash"])

    def test_different_rtl_different_hash(self):
        ev1 = _create_evidence_record(
            design_id="test1", rtl_text=SAFE_FPGA_RTL,
            board_profile="generic_fpga",
            safety_result="RTL_SCAN_PASS", pin_result="PIN_CONSTRAINT_PASS",
            fpga_synth_result="FPGA_SYNTH_SKIPPED_TOOL_MISSING",
            place_route_result="PLACE_ROUTE_SKIPPED_TOOL_MISSING",
            bitstream_result="BITSTREAM_SKIPPED_TOOL_MISSING",
            board_evidence_result="BOARD_EVIDENCE_MISSING",
            tool_versions={}, replay_command="test",
        )
        ev2 = _create_evidence_record(
            design_id="test2", rtl_text=UNSAFE_DIRECT_RTL,
            board_profile="generic_fpga",
            safety_result="RTL_SCAN_FAIL", pin_result="PIN_CONSTRAINT_FAIL",
            fpga_synth_result="FPGA_SYNTH_SKIPPED_TOOL_MISSING",
            place_route_result="PLACE_ROUTE_SKIPPED_TOOL_MISSING",
            bitstream_result="BITSTREAM_SKIPPED_TOOL_MISSING",
            board_evidence_result="BOARD_EVIDENCE_MISSING",
            tool_versions={}, replay_command="test",
        )
        self.assertNotEqual(ev1["rtl_hash"], ev2["rtl_hash"])

    def test_constraints_hash_included(self):
        ev = _create_evidence_record(
            design_id="test", rtl_text=SAFE_FPGA_RTL,
            board_profile="generic_fpga",
            safety_result="RTL_SCAN_PASS", pin_result="PIN_CONSTRAINT_PASS",
            fpga_synth_result="FPGA_SYNTH_SKIPPED_TOOL_MISSING",
            place_route_result="PLACE_ROUTE_SKIPPED_TOOL_MISSING",
            bitstream_result="BITSTREAM_SKIPPED_TOOL_MISSING",
            board_evidence_result="BOARD_EVIDENCE_MISSING",
            tool_versions={}, replay_command="test",
            constraints_hash=hashlib.sha256(b"test_constraints").hexdigest(),
        )
        labels = [a["label"] for a in ev["artifact_hashes"]]
        self.assertIn("constraints", labels)


class TestEvidenceRecordCreated(unittest.TestCase):
    """Test that evidence records have all required fields."""

    def test_evidence_record_has_required_fields(self):
        ev = _create_evidence_record(
            design_id="test", rtl_text=SAFE_FPGA_RTL,
            board_profile="generic_fpga",
            safety_result="RTL_SCAN_PASS", pin_result="PIN_CONSTRAINT_PASS",
            fpga_synth_result="FPGA_SYNTH_SKIPPED_TOOL_MISSING",
            place_route_result="PLACE_ROUTE_SKIPPED_TOOL_MISSING",
            bitstream_result="BITSTREAM_SKIPPED_TOOL_MISSING",
            board_evidence_result="BOARD_EVIDENCE_MISSING",
            tool_versions={}, replay_command="test",
        )
        required_fields = [
            "benchmark_name", "benchmark_version", "design_id", "board_profile",
            "rtl_hash", "chipgate_safety_result", "pin_constraint_result",
            "fpga_synth_result", "place_route_result", "bitstream_readiness_result",
            "board_evidence_result", "tool_versions", "artifact_hashes",
            "replay_command", "certificate_hash", "public_wording", "timestamp_utc",
        ]
        for field_name in required_fields:
            self.assertIn(field_name, ev, f"Missing field: {field_name}")


class TestHTMLReport(unittest.TestCase):
    """Test that HTML report is generated."""

    def test_html_report_generated(self):
        result = FPGABenchResult(
            benchmark_version="0.3.0",
            timestamp_utc="2025-01-01T00:00:00Z",
            board_profile="generic_fpga",
            board_profile_info=GENERIC_FPGA.to_dict(),
            designs_tested=1,
            overall_status=st.FPGA_BENCH_PASS,
            design_results=[{
                "design_id": "safe_dtl_gate_fpga",
                "safety_precheck_status": st.RTL_SCAN_PASS,
                "pin_constraint_status": st.PIN_CONSTRAINT_PASS,
                "fpga_synth_status": st.FPGA_SYNTH_SKIPPED_TOOL_MISSING,
                "place_route_status": st.PLACE_ROUTE_SKIPPED_TOOL_MISSING,
                "bitstream_status": st.BITSTREAM_SKIPPED_TOOL_MISSING,
                "board_evidence_status": st.BOARD_EVIDENCE_MISSING,
                "overall_status": st.FPGA_BENCH_PASS,
                "pin_constraint_checks": [],
                "board_evidence": {},
                "evidence_record": {},
            }],
        )
        html = generate_fpga_html(result.to_dict())
        self.assertIn("FPGABoardBench Report", html)
        self.assertIn("safe_dtl_gate_fpga", html)
        self.assertIn("Disclaimer", html)
        self.assertIn("Limitation", html)

    def test_html_report_contains_board_profile(self):
        result = FPGABenchResult(
            benchmark_version="0.3.0",
            timestamp_utc="2025-01-01T00:00:00Z",
            board_profile="tinyfpga_style",
            designs_tested=0,
            overall_status=st.FPGA_BENCH_FAIL,
            design_results=[],
        )
        html = generate_fpga_html(result.to_dict())
        self.assertIn("tinyfpga_style", html)


class TestJSONSchemaStable(unittest.TestCase):
    """Test that JSON output has a stable schema."""

    def test_bench_result_to_dict_keys(self):
        result = FPGABenchResult(
            benchmark_version="0.3.0",
            timestamp_utc="2025-01-01T00:00:00Z",
            board_profile="generic_fpga",
        )
        d = result.to_dict()
        expected_keys = [
            "benchmark_name", "benchmark_version", "timestamp_utc",
            "board_profile", "board_profile_info", "designs_tested",
            "safety_precheck_passed", "safety_precheck_pass_rate",
            "pin_constraint_pass_rate", "fpga_synth_pass_rate",
            "place_route_pass_rate", "bitstream_ready_rate",
            "board_evidence_attached_count", "unsafe_enable_events_total",
            "kill_switch_bypass_total", "artifact_hash_count",
            "evidence_packs_created", "toolchain_coverage",
            "toolchain_report", "design_results", "overall_status",
            "public_wording", "limitation",
        ]
        for key in expected_keys:
            self.assertIn(key, d, f"Missing key: {key}")

    def test_design_result_to_dict_keys(self):
        dr = FPGADesignResult(design_id="test")
        d = dr.to_dict()
        expected_keys = [
            "design_id", "rtl_path", "safety_precheck_status",
            "safety_precheck_statuses", "board_profile_status",
            "pin_constraint_status", "pin_constraint_checks",
            "fpga_synth_status", "fpga_synth_cell_count",
            "fpga_synth_wire_count", "place_route_status",
            "bitstream_status", "board_evidence_status",
            "board_evidence", "overall_status", "evidence_record",
        ]
        for key in expected_keys:
            self.assertIn(key, d, f"Missing key: {key}")


class TestNoPrivateImports(unittest.TestCase):
    """Verify no private JARVI3 imports."""

    def test_no_jarvi3_import(self):
        import chipgate.fpgabench
        import chipgate.board_profiles
        import chipgate.pin_constraints
        import chipgate.fpga_board
        import chipgate.fpga_report
        import chipgate.bitstream_readiness
        for mod in [chipgate.fpgabench, chipgate.board_profiles,
                     chipgate.pin_constraints, chipgate.fpga_board,
                     chipgate.fpga_report, chipgate.bitstream_readiness]:
            source = open(mod.__file__, encoding="utf-8").read()
            self.assertNotIn("jarvi3", source.lower(),
                             f"{mod.__name__} contains JARVI3 reference")
            self.assertNotIn("private", source.lower(),
                             f"{mod.__name__} contains 'private' reference")


class TestNoShellTrue(unittest.TestCase):
    """Verify no shell=True in any FPGA module."""

    def test_no_shell_true(self):
        modules = [
            "chipgate/fpgabench.py",
            "chipgate/fpga_board.py",
            "chipgate/bitstream_readiness.py",
        ]
        base = Path(__file__).parent.parent
        for mod_path in modules:
            full_path = base / mod_path
            source = full_path.read_text(encoding="utf-8")
            self.assertNotIn("shell=True", source,
                             f"{mod_path} contains shell=True")


class TestEnglishOnlyOutput(unittest.TestCase):
    """Verify all public output strings are English-only."""

    def test_status_constants_english(self):
        fpga_statuses = [
            st.FPGA_BENCH_PASS, st.FPGA_BENCH_FAIL,
            st.BOARD_PROFILE_VALID, st.BOARD_PROFILE_INVALID,
            st.PIN_CONSTRAINT_PASS, st.PIN_CONSTRAINT_FAIL,
            st.FPGA_SYNTH_PASS, st.FPGA_SYNTH_FAIL,
            st.PLACE_ROUTE_PASS, st.PLACE_ROUTE_FAIL,
            st.BITSTREAM_READY, st.BITSTREAM_FAIL,
            st.BOARD_EVIDENCE_ATTACHED, st.BOARD_EVIDENCE_MISSING,
            st.BOARD_EVIDENCE_FAIL, st.CLOCK_MISSING, st.RESET_MISSING,
            st.KILL_SWITCH_MISSING, st.DUPLICATE_PIN_ASSIGNMENT,
        ]
        for s in fpga_statuses:
            self.assertTrue(s.isascii(), f"Non-ASCII in status: {s}")

    def test_public_wording_english(self):
        self.assertTrue(st.FPGA_PUBLIC_WORDING.isascii())
        self.assertTrue(st.FPGA_LIMITATION.isascii())

    def test_board_profile_descriptions_english(self):
        for name, profile in BOARD_PROFILES.items():
            self.assertTrue(profile.description.isascii(),
                            f"Non-ASCII in profile {name}")


class TestToolchainStatus(unittest.TestCase):
    """Tests for FPGA toolchain status output."""

    @patch("shutil.which", return_value=None)
    def test_toolchain_status_all_missing(self, mock_which):
        report = check_fpga_toolchain()
        self.assertEqual(len(report), 6)
        for name, info in report.items():
            self.assertFalse(info["found"])

    def test_format_toolchain_status(self):
        tc = {
            "yosys": {"found": False, "version": None, "path": None, "note": "skipped"},
            "nextpnr": {"found": False, "version": None, "path": None, "note": "skipped"},
        }
        output = format_fpga_toolchain_status(tc)
        self.assertIn("FPGABoardBench", output)
        self.assertIn("Toolchain coverage", output)
        self.assertIn("board profiles", output)


class TestNoSecrets(unittest.TestCase):
    """Verify no secrets, API keys, or tokens in source."""

    def test_no_secrets(self):
        modules = [
            "chipgate/fpgabench.py", "chipgate/board_profiles.py",
            "chipgate/pin_constraints.py", "chipgate/fpga_board.py",
            "chipgate/fpga_report.py", "chipgate/bitstream_readiness.py",
        ]
        base = Path(__file__).parent.parent
        forbidden = ["api_key", "API_KEY", "secret", "SECRET",
                     "password", "PASSWORD", "token", "TOKEN"]
        for mod_path in modules:
            source = (base / mod_path).read_text(encoding="utf-8")
            for word in forbidden:
                self.assertNotIn(word, source,
                                 f"{mod_path} contains '{word}'")


class TestFPGABenchDemoRun(unittest.TestCase):
    """Test running the full FPGABoardBench demo."""

    def test_demo_runs(self):
        result = run_fpgabench(demo=True, board_profile_name="generic_fpga")
        self.assertIsInstance(result, FPGABenchResult)
        self.assertGreater(result.designs_tested, 0)
        self.assertIn(result.overall_status,
                      [st.FPGA_BENCH_PASS, st.FPGA_BENCH_FAIL])

    def test_demo_has_evidence_records(self):
        result = run_fpgabench(demo=True)
        self.assertGreater(result.evidence_packs_created, 0)
        for d in result.design_results:
            ev = d.get("evidence_record", {})
            self.assertIn("certificate_hash", ev)
            self.assertIn("rtl_hash", ev)

    def test_demo_json_serializable(self):
        result = run_fpgabench(demo=True)
        d = result.to_dict()
        json_str = json.dumps(d, sort_keys=True, default=str)
        self.assertIsInstance(json_str, str)
        self.assertGreater(len(json_str), 100)

    def test_demo_contains_safe_design_pass(self):
        result = run_fpgabench(demo=True)
        safe_design = next(
            (d for d in result.design_results
             if d["design_id"] == "safe_dtl_gate_fpga"),
            None,
        )
        self.assertIsNotNone(safe_design)
        self.assertEqual(safe_design["safety_precheck_status"], st.RTL_SCAN_PASS)

    def test_demo_contains_unsafe_design_fail(self):
        result = run_fpgabench(demo=True)
        unsafe_design = next(
            (d for d in result.design_results
             if d["design_id"] == "unsafe_direct_output_fpga"),
            None,
        )
        self.assertIsNotNone(unsafe_design)
        self.assertEqual(unsafe_design["safety_precheck_status"], st.RTL_SCAN_FAIL)

    def test_demo_missing_kill_switch_detected(self):
        result = run_fpgabench(demo=True)
        design = next(
            (d for d in result.design_results
             if d["design_id"] == "missing_kill_switch_fpga"),
            None,
        )
        self.assertIsNotNone(design)
        kill_check = next(
            (c for c in design.get("pin_constraint_checks", [])
             if c["check"] == "kill_switch"),
            None,
        )
        self.assertIsNotNone(kill_check)
        self.assertEqual(kill_check["status"], "FAIL")

    def test_demo_bad_pin_constraints_detected(self):
        result = run_fpgabench(demo=True)
        design = next(
            (d for d in result.design_results
             if d["design_id"] == "bad_pin_constraints"),
            None,
        )
        self.assertIsNotNone(design)
        self.assertEqual(design["pin_constraint_status"], st.PIN_CONSTRAINT_FAIL)


class TestGetDemoDesigns(unittest.TestCase):
    """Test demo design discovery."""

    def test_demo_designs_exist(self):
        designs = get_demo_designs()
        self.assertGreater(len(designs), 0)

    def test_demo_designs_are_verilog(self):
        designs = get_demo_designs()
        for d in designs:
            self.assertTrue(d.endswith(".v"), f"Not .v file: {d}")


if __name__ == "__main__":
    unittest.main()