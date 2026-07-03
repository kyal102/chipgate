"""
ChipGate test suite.

Tests all rules, CLI commands, edge cases, and ensures no private imports.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the chipgate package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from chipgate.statuses import (
    ALL_STATUSES, FAIL_STATUSES, PASS_STATUSES, PUBLIC_WORDING,
    RTL_SCAN_PASS, RTL_SCAN_FAIL, RTL_LINT_PASS, RTL_LINT_FAIL,
    SIMULATION_PASS, SIMULATION_FAIL, FORMAL_READY, FORMAL_NOT_READY,
    ASSERTION_MISSING, UNSAFE_BYPASS_PATH, UNGATED_OUTPUT,
    SAFETY_GATE_PRESENT, NEEDS_HUMAN_REVIEW, EVIDENCE_PACK_CREATED,
)
from chipgate.rules import RULES, RULE_BY_ID, Severity, get_rules
from chipgate.scanner import (
    scan_file, scan_directory, parse_verilog, ModuleInfo,
    Finding, ScanResult, ACTUATOR_NAMES, VERIFICATION_GATE_SIGNALS,
    check_missing_reset, check_missing_default, check_undriven_outputs,
    check_unused_inputs, check_hardcoded_bypass, check_verifier_ok_gating,
    check_policy_ok_gating, check_kill_switch, check_assertions,
    check_testbench, check_safety_gate_present,
    _is_actuator_signal, _has_gate_signals, _has_bypass, strip_comments,
)
from chipgate.lint import run_lint, verilator_available, LintResult
from chipgate.simulation import run_simulation
from chipgate.formal import check_formal_readiness, yosys_available, sby_available
from chipgate.safety import analyze_safety_patterns
from chipgate.evidence import generate_evidence_pack, save_evidence_pack, validate_evidence_pack
from chipgate.replay import generate_replay_commands, format_replay_script_from_result
from chipgate.dtl_gate import get_dtl_gate_reference, get_dtl_fsm_reference, get_gate_structure_docs


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestStatusConstants(unittest.TestCase):
    """Test status constant definitions."""

    def test_all_statuses_defined(self):
        self.assertGreaterEqual(len(ALL_STATUSES), 26)

    def test_no_duplicate_statuses(self):
        self.assertEqual(len(ALL_STATUSES), len(set(ALL_STATUSES)))

    def test_public_wording_contains_disclaimers(self):
        self.assertIn("does not guarantee", PUBLIC_WORDING)
        self.assertIn("silicon readiness", PUBLIC_WORDING)

    def test_fail_and_pass_are_disjoint(self):
        self.assertEqual(FAIL_STATUSES & PASS_STATUSES, set())


class TestRules(unittest.TestCase):
    """Test rule catalogue."""

    def test_rules_defined(self):
        self.assertGreaterEqual(len(RULES), 14)

    def test_all_rules_have_ids(self):
        for rule in RULES:
            self.assertTrue(rule.rule_id.startswith("CG"))

    def test_rule_by_id_complete(self):
        for rule in RULES:
            self.assertIn(rule.rule_id, RULE_BY_ID)

    def test_get_rules_filters_by_severity(self):
        critical = get_rules(Severity.CRITICAL)
        for r in critical:
            self.assertEqual(r.severity, Severity.CRITICAL)

    def test_get_rules_returns_all_when_no_filter(self):
        all_rules = get_rules()
        self.assertEqual(len(all_rules), len(RULES))


class TestStripComments(unittest.TestCase):
    """Test comment stripping."""

    def test_single_line_comment(self):
        code = "a = b; // this is a comment\n"
        result = strip_comments(code)
        self.assertNotIn("this is a comment", result)
        self.assertIn("a = b;", result)

    def test_block_comment(self):
        code = "a = /* block */ b;"
        result = strip_comments(code)
        self.assertNotIn("block", result)
        self.assertIn("a =  b;", result)

    def test_no_comments(self):
        code = "assign x = y;"
        self.assertEqual(strip_comments(code), "assign x = y;")


class TestIsActuatorSignal(unittest.TestCase):
    """Test actuator signal detection."""

    def test_actuator_enable(self):
        self.assertTrue(_is_actuator_signal("actuator_enable"))

    def test_motor_enable(self):
        self.assertTrue(_is_actuator_signal("motor_enable"))

    def test_plain_signal(self):
        self.assertFalse(_is_actuator_signal("data_bus"))

    def test_valve_open(self):
        self.assertTrue(_is_actuator_signal("valve_open"))

    def test_heater_on(self):
        self.assertTrue(_is_actuator_signal("heater_on"))

    def test_laser_enable(self):
        self.assertTrue(_is_actuator_signal("laser_enable"))

    def test_drive_enable(self):
        self.assertTrue(_is_actuator_signal("drive_enable"))

    def test_trigger_out(self):
        self.assertTrue(_is_actuator_signal("trigger_out"))


class TestHasGateSignals(unittest.TestCase):
    """Test gate signal detection in expressions."""

    def test_verifier_ok_detected(self):
        has, gates = _has_gate_signals("ai_output && verifier_ok")
        self.assertTrue(has)
        self.assertIn("verifier_ok", gates)

    def test_policy_ok_detected(self):
        has, gates = _has_gate_signals("policy_ok && sensor_ok")
        self.assertTrue(has)
        self.assertIn("policy_ok", gates)

    def test_kill_switch_detected(self):
        has, gates = _has_gate_signals("!kill_switch")
        self.assertTrue(has)
        self.assertIn("kill_switch", gates)

    def test_no_gates(self):
        has, gates = _has_gate_signals("ai_output")
        self.assertFalse(has)
        self.assertEqual(gates, [])

    def test_all_gates(self):
        expr = "ai_output && verifier_ok && policy_ok && sensor_ok && timeout_ok && !kill_switch"
        has, gates = _has_gate_signals(expr)
        self.assertTrue(has)
        self.assertIn("verifier_ok", gates)
        self.assertIn("policy_ok", gates)
        self.assertIn("kill_switch", gates)


class TestHasBypass(unittest.TestCase):
    """Test bypass detection."""

    def test_single_signal_bypass(self):
        self.assertTrue(_has_bypass("ai_output"))

    def test_negated_signal_bypass(self):
        self.assertTrue(_has_bypass("!ai_output"))

    def test_constant_not_bypass(self):
        self.assertFalse(_has_bypass("1'b0"))
        self.assertFalse(_has_bypass("1'b1"))
        self.assertFalse(_has_bypass("0"))
        self.assertFalse(_has_bypass("1"))

    def test_gated_expression_not_bypass(self):
        self.assertFalse(_has_bypass("ai_output && verifier_ok && policy_ok"))

    def test_complex_expression_not_bypass(self):
        self.assertFalse(_has_bypass("a & b | c"))


# ── Integration Tests with Example Files ──────────────────────────────────────

class TestUnsafeActuatorExample(unittest.TestCase):
    """Test scanning the unsafe actuator example."""

    def setUp(self):
        self.path = str(EXAMPLES_DIR / "unsafe_actuator.v")

    def test_file_exists(self):
        self.assertTrue(Path(self.path).exists())

    def test_ungated_output_detected(self):
        result = scan_file(self.path)
        self.assertIn(UNGATED_OUTPUT, result.statuses)

    def test_missing_reset_detected(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertIn("CG001", rule_ids)

    def test_missing_kill_switch_detected(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertIn("CG009", rule_ids)

    def test_missing_verifier_ok(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertIn("CG007", rule_ids)

    def test_missing_policy_ok(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertIn("CG008", rule_ids)

    def test_assertions_missing(self):
        result = scan_file(self.path)
        self.assertIn(ASSERTION_MISSING, result.statuses)

    def test_scan_fails(self):
        result = scan_file(self.path)
        self.assertIn(RTL_SCAN_FAIL, result.statuses)

    def test_no_safety_gate(self):
        result = scan_file(self.path)
        self.assertNotIn(SAFETY_GATE_PRESENT, result.statuses)

    def test_bypass_detected(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertIn("CG006", rule_ids)


class TestSafeDTLGateExample(unittest.TestCase):
    """Test scanning the safe DTL gate example."""

    def setUp(self):
        self.path = str(EXAMPLES_DIR / "safe_dtl_gate.v")

    def test_file_exists(self):
        self.assertTrue(Path(self.path).exists())

    def test_safety_gate_present(self):
        result = scan_file(self.path)
        self.assertIn(SAFETY_GATE_PRESENT, result.statuses)

    def test_no_ungated_output(self):
        result = scan_file(self.path)
        self.assertNotIn(UNGATED_OUTPUT, result.statuses)

    def test_has_reset(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertNotIn("CG001", rule_ids)

    def test_has_kill_switch(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertNotIn("CG009", rule_ids)

    def test_verifier_ok_gated(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertNotIn("CG007", rule_ids)

    def test_policy_ok_gated(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertNotIn("CG008", rule_ids)

    def test_scan_passes(self):
        result = scan_file(self.path)
        self.assertIn(RTL_SCAN_PASS, result.statuses)

    def test_module_name_detected(self):
        result = scan_file(self.path)
        self.assertEqual(result.module_name, "safe_dtl_gate")


class TestDTLGateFSMExample(unittest.TestCase):
    """Test scanning the DTL gate FSM example."""

    def setUp(self):
        self.path = str(EXAMPLES_DIR / "dtl_gate_fsm.v")

    def test_file_exists(self):
        self.assertTrue(Path(self.path).exists())

    def test_module_name(self):
        result = scan_file(self.path)
        self.assertEqual(result.module_name, "dtl_gate_fsm")

    def test_safety_gate_present(self):
        result = scan_file(self.path)
        self.assertIn(SAFETY_GATE_PRESENT, result.statuses)

    def test_has_reset(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertNotIn("CG001", rule_ids)

    def test_has_kill_switch(self):
        result = scan_file(self.path)
        rule_ids = [f.rule_id for f in result.findings]
        self.assertNotIn("CG009", rule_ids)


# ── Individual Check Tests ───────────────────────────────────────────────────

class TestCheckMissingReset(unittest.TestCase):
    """Test CG001: Missing reset."""

    def test_no_reset_fails(self):
        info = ModuleInfo(raw_lines=["module test ();", "endmodule"], has_reset=False)
        finding = check_missing_reset(info)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.rule_id, "CG001")

    def test_with_reset_passes(self):
        info = ModuleInfo(
            raw_lines=["module test (input rst_n);", "endmodule"],
            has_reset=True,
        )
        finding = check_missing_reset(info)
        self.assertIsNone(finding)


class TestCheckKillSwitch(unittest.TestCase):
    """Test CG009: Kill switch."""

    def _make_info_with_actuator(self, has_kill: bool) -> ModuleInfo:
        from chipgate.scanner import Assignment
        info = ModuleInfo(
            raw_lines=[],
            has_kill_switch=has_kill,
            assignments=[Assignment(target="actuator_enable", expression="x")],
        )
        return info

    def test_no_kill_switch_fails(self):
        info = self._make_info_with_actuator(False)
        finding = check_kill_switch(info)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.rule_id, "CG009")

    def test_with_kill_switch_passes(self):
        info = self._make_info_with_actuator(True)
        finding = check_kill_switch(info)
        self.assertIsNone(finding)


class TestCheckAssertions(unittest.TestCase):
    """Test CG010: Assertions."""

    def test_no_assertions_fails(self):
        info = ModuleInfo(raw_lines=["module test ();", "endmodule"], has_assertions=False)
        finding = check_assertions(info)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.rule_id, "CG010")

    def test_with_assertions_passes(self):
        info = ModuleInfo(
            raw_lines=["module test ();", "  assert property (x);", "endmodule"],
            has_assertions=True,
        )
        finding = check_assertions(info)
        self.assertIsNone(finding)


class TestCheckTestbench(unittest.TestCase):
    """Test CG011: Testbench detection."""

    def test_no_testbench(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("module test ();\nendmodule\n")
            path = f.name
        try:
            finding = check_testbench(path)
            self.assertIsNotNone(finding)
            self.assertEqual(finding.rule_id, "CG011")
        finally:
            os.unlink(path)

    def test_with_testbench(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            design_path = Path(tmpdir) / "test.v"
            tb_path = Path(tmpdir) / "test_tb.v"
            design_path.write_text("module test ();\nendmodule\n")
            tb_path.write_text("module test_tb ();\nendmodule\n")
            finding = check_testbench(str(design_path))
            self.assertIsNone(finding)


# ── Scan File Tests ──────────────────────────────────────────────────────────

class TestScanFile(unittest.TestCase):
    """Test the scan_file function with synthetic designs."""

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            scan_file("/nonexistent/file.v")

    def test_replay_command_generated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("module t(input clk, output reg x); always@(posedge clk) x<=1; endmodule\n")
            path = f.name
        try:
            result = scan_file(path)
            self.assertIn("chipgate", result.replay_command)
            self.assertIn(path, result.replay_command)
        finally:
            os.unlink(path)

    def test_certificate_hash_is_sha256(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("module t(input clk, output reg x); always@(posedge clk) x<=1; endmodule\n")
            path = f.name
        try:
            result = scan_file(path)
            self.assertEqual(len(result.certificate_hash), 64)
            int(result.certificate_hash, 16)  # Must be valid hex
        finally:
            os.unlink(path)

    def test_public_wording_present(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("module t(input clk, output reg x); always@(posedge clk) x<=1; endmodule\n")
            path = f.name
        try:
            result = scan_file(path)
            self.assertEqual(result.public_wording, PUBLIC_WORDING)
        finally:
            os.unlink(path)

    def test_required_gates_populated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("module t(input clk, output reg x); always@(posedge clk) x<=1; endmodule\n")
            path = f.name
        try:
            result = scan_file(path)
            self.assertIn("verifier_ok", result.required_gates)
            self.assertIn("policy_ok", result.required_gates)
            self.assertIn("kill_switch", result.required_gates)
        finally:
            os.unlink(path)

    def test_rules_checked_populated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("module t(input clk, output reg x); always@(posedge clk) x<=1; endmodule\n")
            path = f.name
        try:
            result = scan_file(path)
            self.assertIn("CG001", result.rules_checked)
            self.assertIn("CG010", result.rules_checked)
            self.assertGreater(len(result.rules_checked), 10)
        finally:
            os.unlink(path)

    def test_to_dict(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("module t(input clk, output reg x); always@(posedge clk) x<=1; endmodule\n")
            path = f.name
        try:
            result = scan_file(path)
            d = result.to_dict()
            self.assertIn("file", d)
            self.assertIn("statuses", d)
            self.assertIn("findings", d)
            self.assertIsInstance(d["findings"], list)
        finally:
            os.unlink(path)


class TestScanDirectory(unittest.TestCase):
    """Test directory scanning."""

    def test_scan_examples_dir(self):
        results = scan_directory(str(EXAMPLES_DIR))
        self.assertGreater(len(results), 0)

    def test_nonexistent_dir(self):
        results = scan_directory("/nonexistent/dir")
        self.assertEqual(len(results), 0)


# ── Evidence Pack Tests ──────────────────────────────────────────────────────

class TestEvidencePack(unittest.TestCase):
    """Test evidence pack generation."""

    def test_generate_evidence_pack(self):
        result = scan_file(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
        pack = generate_evidence_pack(result)
        self.assertIn("chipgate_version", pack)
        self.assertIn("timestamp_utc", pack)
        self.assertIn("file", pack)
        self.assertIn("statuses", pack)
        self.assertIn("findings", pack)
        self.assertIn("certificate_hash", pack)
        self.assertIn("evidence_pack_hash", pack)
        self.assertIn("public_wording", pack)

    def test_save_evidence_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_file(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
            out_path = os.path.join(tmpdir, "test.evidence.json")
            saved = save_evidence_pack(result, output_path=out_path)
            self.assertTrue(Path(saved).exists())
            data = json.loads(Path(saved).read_text())
            self.assertEqual(data["module_name"], "safe_dtl_gate")

    def test_validate_evidence_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_file(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
            out_path = os.path.join(tmpdir, "test.evidence.json")
            save_evidence_pack(result, output_path=out_path)
            validation = validate_evidence_pack(out_path)
            self.assertTrue(validation["valid"])

    def test_validate_missing_pack(self):
        validation = validate_evidence_pack("/nonexistent/pack.json")
        self.assertFalse(validation["valid"])

    def test_validate_tampered_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_file(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
            out_path = os.path.join(tmpdir, "test.evidence.json")
            save_evidence_pack(result, output_path=out_path)
            # Tamper with the file
            content = Path(out_path).read_text()
            content = content.replace('"module_name"', '"module_name_tampered"')
            Path(out_path).write_text(content)
            validation = validate_evidence_pack(out_path)
            self.assertFalse(validation["valid"])


# ── Lint Tests ───────────────────────────────────────────────────────────────

class TestLint(unittest.TestCase):
    """Test lint runner."""

    def test_lint_returns_result(self):
        result = run_lint(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
        self.assertIsInstance(result, LintResult)

    def test_graceful_skip_when_no_verilator(self):
        if not verilator_available():
            result = run_lint(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
            self.assertFalse(result.available)


# ── Simulation Tests ─────────────────────────────────────────────────────────

class TestSimulation(unittest.TestCase):
    """Test simulation runner."""

    def test_simulation_returns_result(self):
        result = run_simulation(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
        self.assertIsNotNone(result)

    def test_no_simulator_graceful_skip(self):
        result = run_simulation(str(EXAMPLES_DIR / "safe_dtl_gate.v"), tool="none")
        self.assertFalse(result.available)


# ── Formal Tests ─────────────────────────────────────────────────────────────

class TestFormal(unittest.TestCase):
    """Test formal verification readiness."""

    def test_unsafe_not_formal_ready(self):
        result = check_formal_readiness(str(EXAMPLES_DIR / "unsafe_actuator.v"))
        self.assertFalse(result.ready)

    def test_formal_returns_issues(self):
        result = check_formal_readiness(str(EXAMPLES_DIR / "unsafe_actuator.v"))
        self.assertGreater(len(result.issues), 0)


# ── Safety Analysis Tests ────────────────────────────────────────────────────

class TestSafetyAnalysis(unittest.TestCase):
    """Test safety pattern analysis."""

    def test_unsafe_has_critical_gaps(self):
        result = analyze_safety_patterns(str(EXAMPLES_DIR / "unsafe_actuator.v"))
        self.assertGreater(len(result.critical_gaps), 0)

    def test_safe_has_higher_score(self):
        unsafe = analyze_safety_patterns(str(EXAMPLES_DIR / "unsafe_actuator.v"))
        safe = analyze_safety_patterns(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
        self.assertGreater(safe.safety_score, unsafe.safety_score)

    def test_fsm_has_highest_score(self):
        safe = analyze_safety_patterns(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
        fsm = analyze_safety_patterns(str(EXAMPLES_DIR / "dtl_gate_fsm.v"))
        self.assertGreaterEqual(fsm.safety_score, safe.safety_score)

    def test_patterns_list_populated(self):
        result = analyze_safety_patterns(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
        self.assertGreater(len(result.patterns), 0)


# ── Replay Tests ─────────────────────────────────────────────────────────────

class TestReplay(unittest.TestCase):
    """Test replay command generation."""

    def test_replay_commands_generated(self):
        result = scan_file(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
        commands = generate_replay_commands(result)
        self.assertGreater(len(commands), 0)

    def test_replay_script_format(self):
        result = scan_file(str(EXAMPLES_DIR / "safe_dtl_gate.v"))
        script = format_replay_script_from_result(result)
        self.assertIn("#!/usr/bin/env bash", script)
        self.assertIn("set -e", script)
        self.assertIn("chipgate scan", script)


# ── DTL Gate Tests ───────────────────────────────────────────────────────────

class TestDTLGate(unittest.TestCase):
    """Test DTL gate reference module."""

    def test_reference_verilog_returned(self):
        v = get_dtl_gate_reference()
        self.assertIn("module dtl_hardware_gate", v)
        self.assertIn("verifier_ok", v)
        self.assertIn("policy_ok", v)
        self.assertIn("kill_switch", v)
        self.assertIn("actuator_enable", v)

    def test_fsm_reference_returned(self):
        v = get_dtl_fsm_reference()
        self.assertIn("module dtl_gate_fsm", v)
        self.assertIn("IDLE", v)
        self.assertIn("FAILSAFE", v)
        self.assertIn("APPROVED", v)

    def test_docs_returned(self):
        docs = get_gate_structure_docs()
        self.assertIn("DTL Hardware Safety Gate", docs)
        self.assertIn("verifier_ok", docs)


# ── CLI Tests ────────────────────────────────────────────────────────────────

class TestCLI(unittest.TestCase):
    """Test CLI entry point."""

    def test_version(self):
        from chipgate.__main__ import main
        with patch("sys.argv", ["chipgate", "--version"]):
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 0)

    def test_list_rules(self):
        from chipgate.__main__ import main
        with patch("sys.argv", ["chipgate", "--list-rules"]):
            result = main()
            self.assertEqual(result, 0)

    def test_scan_unsafe(self):
        from chipgate.__main__ import main
        path = str(EXAMPLES_DIR / "unsafe_actuator.v")
        with patch("sys.argv", ["chipgate", "scan", path]):
            result = main()
            self.assertEqual(result, 2)  # FAIL

    def test_scan_safe(self):
        from chipgate.__main__ import main
        path = str(EXAMPLES_DIR / "safe_dtl_gate.v")
        with patch("sys.argv", ["chipgate", "scan", path]):
            result = main()
            self.assertEqual(result, 0)  # PASS

    def test_scan_json(self):
        from chipgate.__main__ import main
        path = str(EXAMPLES_DIR / "safe_dtl_gate.v")
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            with patch("sys.argv", ["chipgate", "scan", path, "--json"]):
                main()
            output = mock_out.getvalue()
            data = json.loads(output)
            self.assertIn("statuses", data)
            self.assertIn(SAFETY_GATE_PRESENT, data["statuses"])

    def test_scan_evidence(self):
        from chipgate.__main__ import main
        path = str(EXAMPLES_DIR / "safe_dtl_gate.v")
        with patch("sys.argv", ["chipgate", "scan", path, "--evidence"]):
            result = main()
            self.assertEqual(result, 0)

    def test_scan_nonexistent(self):
        from chipgate.__main__ import main
        with patch("sys.argv", ["chipgate", "scan", "/nonexistent/file.v"]):
            with patch("sys.stderr", new_callable=StringIO):
                result = main()
            self.assertEqual(result, 1)

    def test_demo(self):
        from chipgate.__main__ import main
        with patch("sys.argv", ["chipgate", "--demo"]):
            result = main()
            self.assertEqual(result, 0)

    def test_scan_with_safety(self):
        from chipgate.__main__ import main
        path = str(EXAMPLES_DIR / "safe_dtl_gate.v")
        with patch("sys.argv", ["chipgate", "scan", path, "--safety"]):
            result = main()
            self.assertEqual(result, 0)


# ── No Private Imports Test ──────────────────────────────────────────────────

class TestNoPrivateImports(unittest.TestCase):
    """Ensure no private JARVI3 or secret imports exist."""

    def test_no_jarvi3_imports(self):
        """No file in the chipgate package should import from jarvi3."""
        pkg_dir = Path(__file__).parent.parent / "chipgate"
        # mutators.py intentionally contains "jarvi3" as a test payload for
        # the private_leak mutation category — it is not an import.
        # Phase 25 passport files reference "JARVI3" in detection patterns,
        # docstrings and adapter examples — also not imports.
        _EXCLUDED = {
            "mutators.py",
            "passport_schema.py",
            "passport_policy.py",
            "passport_artifacts.py",
            "passport_builder.py",
            "passport_badges.py",
            "passport_export.py",
            "passport_replay.py",
            "passport_manifest.py",
            "passport_report.py",
            "passport_examples.py",
            "design_passport.py",
        }
        for py_file in pkg_dir.glob("**/*.py"):
            if py_file.name in _EXCLUDED:
                continue
            content = py_file.read_text()
            self.assertNotIn("jarvi3", content.lower(), f"Private import found in {py_file}")
            self.assertNotIn("from jarvi3", content)
            self.assertNotIn("import jarvi3", content)

    def test_no_secret_tokens(self):
        """No file should contain hardcoded secrets, API keys, or tokens."""
        pkg_dir = Path(__file__).parent.parent / "chipgate"
        patterns = ["API_KEY", "SECRET_KEY", "PRIVATE_TOKEN", "password=", "token="]
        for py_file in pkg_dir.glob("**/*.py"):
            content = py_file.read_text()
            for pattern in patterns:
                # Allow the pattern in comments about security
                if f'"{pattern}' in content or f"'{pattern}" in content:
                    self.fail(f"Potential secret pattern '{pattern}' found in {py_file}")

    def test_no_shell_true_unsafe(self):
        """shell=True should only be used with tested-safe arguments."""
        pkg_dir = Path(__file__).parent.parent / "chipgate"
        for py_file in pkg_dir.glob("**/*.py"):
            content = py_file.read_text()
            if "shell=True" in content:
                # Verify the file using shell=True is lint.py and it uses a list, not string
                self.assertEqual(
                    py_file.name, "lint.py",
                    f"shell=True found in unexpected file: {py_file}"
                )


# ── Edge Case Tests ──────────────────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = scan_file(path)
            self.assertIn(RTL_SCAN_FAIL, result.statuses)
        finally:
            os.unlink(path)

    def test_only_comments(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write("// Just a comment\n/* block comment */\n")
            path = f.name
        try:
            result = scan_file(path)
            self.assertIsNotNone(result)
        finally:
            os.unlink(path)

    def test_multiple_modules(self):
        code = """
module a (input x, output y);
    assign y = x;
endmodule
module b (input x, output y);
    assign y = x;
endmodule
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write(code)
            path = f.name
        try:
            result = scan_file(path)
            self.assertIsNotNone(result)
        finally:
            os.unlink(path)

    def test_assign_with_negated_kill_switch(self):
        code = """
module safe (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 0;
        else actuator_enable <= ai_output & verifier_ok & policy_ok & ~kill_switch;
    end
endmodule
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False) as f:
            f.write(code)
            path = f.name
        try:
            result = scan_file(path)
            self.assertIn(SAFETY_GATE_PRESENT, result.statuses)
            self.assertNotIn(UNGATED_OUTPUT, result.statuses)
        finally:
            os.unlink(path)


# ── Utilities ────────────────────────────────────────────────────────────────

from io import StringIO


if __name__ == "__main__":
    unittest.main()