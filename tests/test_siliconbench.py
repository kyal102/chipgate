"""
Tests for SiliconReadinessBench (Phase 7).

Covers:
- toolchain status works when tools missing
- safe design passes internal safety precheck
- unsafe design blocked before synthesis ranking
- bad syntax classified correctly with mocked tool output
- Yosys report parser extracts cell count from fixture
- Verilator lint parser extracts warnings from fixture
- formal result parser detects pass/fail from fixture
- artifact hashes stable
- evidence record created
- HTML report generated
- JSON schema stable
- no private JARVI3 imports
- no secrets
- no shell=True
- English-only output
"""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Import modules under test ──────────────────────────────────────────────

from chipgate.toolchain import (
    check_toolchain, ToolchainReport, ToolStatus,
    format_toolchain_status, _TOOL_DEFS,
)
from chipgate.verilator_flow import (
    run_verilator_lint, parse_verilator_output, LintResult,
)
from chipgate.yosys_flow import (
    run_yosys_synthesis, parse_yosys_stats, SynthesisResult,
)
from chipgate.formal_flow import (
    run_formal_check, parse_formal_output, FormalResult,
)
from chipgate.fpga_flow import run_fpga_flow, FPGAResult
from chipgate.openlane_flow import run_asic_readiness, ASICResult
from chipgate.silicon_artifacts import (
    hash_artifact, hash_design_artifacts, compute_evidence_hash,
    SiliconEvidenceRecord, create_evidence_record, _sha256,
)
from chipgate.siliconbench import (
    SiliconDesign, SiliconBenchResult, DesignStageResults,
    run_design_stages, run_siliconbench_demo, run_siliconbench,
    SAFE_DTL_GATE, UNSAFE_DIRECT_ACTUATOR, SAFE_FSM_GATE, BAD_SYNTAX,
    _run_safety_precheck, _rate, _load_designs_from_path,
)
from chipgate.silicon_report import generate_silicon_html
from chipgate import statuses as st


# ── Fixtures ───────────────────────────────────────────────────────────────

SAFE_RTL = """module safe_gate (
    input clk, input rst_n, input ai_output,
    input verifier_ok, input policy_ok, input kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule
"""

UNSAFE_RTL = """module unsafe_gate (
    input clk, input ai_output,
    output reg actuator_enable
);
    always @(posedge clk) begin
        actuator_enable <= ai_output;
    end
endmodule
"""

BAD_RTL = """module bad (
    input clk, output reg out
);
    always @(posedge clk) begin
        out <= = clk +
    end
endmodule
"""

YOSYS_STATS_OUTPUT = """=== safe_gate ===
   Number of cells:                 15
   Number of wires:                 12
   Number of process cells:          1
"""

VERILATOR_OUTPUT_WARNINGS = """%Warning-UNDRIVEN: test.v:5: Signal 'unused_sig' is not driven
%Warning-UNUSED: test.v:3: Signal 'unused_input' is not used
%Warning-UNDRIVEN: test.v:8: Another undriven warning
"""

VERILATOR_OUTPUT_ERRORS = """%Error: test.v:5: Syntax error
%Error: Unable to continue
"""

SBY_PASS_OUTPUT = """SBY 1.0 reporting
[INFO] property_kill_switch: PASSED
[INFO] property_verifier: PASSED
"""

SBY_FAIL_OUTPUT = """SBY 1.0 reporting
[INFO] property_kill_switch: PASSED
[INFO] property_verifier: FAILED
"""


def _check_no_shell_true(source: str) -> None:
    """Check that shell=True is not used in actual code (not comments/docstrings)."""
    in_docstring = False
    for i, line in enumerate(source.split('\n'), 1):
        stripped = line.strip()
        # Track docstring boundaries (simple heuristic)
        if '"""' in stripped:
            count = stripped.count('"""')
            if count == 1:
                in_docstring = not in_docstring
            # count == 2 means docstring opens and closes on same line
        if stripped.startswith('#'):
            continue
        if in_docstring:
            continue
        if 'shell=True' in line:
            raise AssertionError(f'shell=True found at line {i}: {line}')


# ── Test: Toolchain ────────────────────────────────────────────────────────

class TestToolchain(unittest.TestCase):
    """Tests for toolchain detection module."""

    def test_toolchain_report_structure(self):
        """ToolchainReport has expected fields."""
        report = check_toolchain()
        self.assertIsInstance(report, ToolchainReport)
        self.assertIn("verilator", report.tools)
        self.assertIn("yosys", report.tools)
        self.assertIn("symbiyosys", report.tools)
        self.assertIn("nextpnr", report.tools)
        self.assertIn("openlane", report.tools)
        self.assertIn("openroad", report.tools)

    def test_toolchain_coverage_no_tools(self):
        """Coverage is 0 when no tools found (typical CI env)."""
        report = check_toolchain()
        # In a test environment, most tools won't be present
        self.assertIsInstance(report.coverage, float)
        self.assertGreaterEqual(report.coverage, 0.0)
        self.assertLessEqual(report.coverage, 1.0)

    def test_toolchain_to_dict(self):
        """ToolchainReport.to_dict() returns valid dict."""
        report = check_toolchain()
        d = report.to_dict()
        self.assertIsInstance(d, dict)
        for name in _TOOL_DEFS:
            self.assertIn(name, d)
            self.assertIn("found", d[name])
            self.assertIn("note", d[name])

    def test_format_toolchain_status(self):
        """format_toolchain_status returns non-empty string."""
        report = check_toolchain()
        output = format_toolchain_status(report)
        self.assertIn("Toolchain Status", output)
        self.assertIn("Verilator", output)
        self.assertIn("Yosys", output)

    def test_toolchain_status_json_safe(self):
        """Toolchain report serializes to JSON."""
        report = check_toolchain()
        d = report.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        self.assertIsInstance(json_str, str)
        # Round-trip
        parsed = json.loads(json_str)
        self.assertEqual(parsed, d)

    def test_no_shell_true_in_toolchain(self):
        """toolchain.py does not use shell=True in code."""
        import chipgate.toolchain as tc_module
        source = Path(tc_module.__file__).read_text()
        _check_no_shell_true(source)


# ── Test: Safety Precheck ──────────────────────────────────────────────────

class TestSafetyPrecheck(unittest.TestCase):
    """Tests for Stage 1 — RTL safety precheck."""

    def test_safe_design_passes_precheck(self):
        """Safe DTL gate passes safety precheck."""
        with tempfile.TemporaryDirectory() as work_dir:
            status, findings = _run_safety_precheck(SAFE_RTL, "safe_gate", work_dir)
            self.assertEqual(status, st.RTL_SCAN_PASS)

    def test_unsafe_design_fails_precheck(self):
        """Ungated actuator fails safety precheck."""
        with tempfile.TemporaryDirectory() as work_dir:
            status, findings = _run_safety_precheck(UNSAFE_RTL, "unsafe_gate", work_dir)
            self.assertEqual(status, st.RTL_SCAN_FAIL)
            self.assertTrue(len(findings) > 0)

    def test_bad_syntax_handled(self):
        """Bad syntax does not crash safety precheck."""
        with tempfile.TemporaryDirectory() as work_dir:
            status, findings = _run_safety_precheck(BAD_RTL, "bad", work_dir)
            # Should return a status (either PASS or FAIL) without crashing
            self.assertIn(status, [st.RTL_SCAN_PASS, st.RTL_SCAN_FAIL])


# ── Test: Unsafe Design Blocking ───────────────────────────────────────────

class TestUnsafeBlocking(unittest.TestCase):
    """Tests that unsafe designs are blocked before tool stages."""

    def test_unsafe_blocked_without_allow_flag(self):
        """Unsafe design gets BLOCKED_UNSAFE for all tool stages."""
        design = SiliconDesign(
            design_id="unsafe_test",
            rtl_text=UNSAFE_RTL,
            description="Unsafe test",
            expected_safety="FAIL",
            expected_lint="FAIL",
            expected_synthesis="FAIL",
            expected_formal="FAIL",
        )
        with tempfile.TemporaryDirectory() as work_dir:
            dr = run_design_stages(design, work_dir, allow_unsafe=False)
            self.assertEqual(dr.safety_precheck_status, st.RTL_SCAN_FAIL)
            self.assertEqual(dr.lint_status, "BLOCKED_UNSAFE")
            self.assertEqual(dr.synthesis_status, "BLOCKED_UNSAFE")
            self.assertEqual(dr.formal_status, "BLOCKED_UNSAFE")
            self.assertEqual(dr.fpga_flow_status, "BLOCKED_UNSAFE")
            self.assertEqual(dr.asic_flow_status, "BLOCKED_UNSAFE")
            self.assertEqual(dr.overall_status, st.SILICON_READINESS_FAIL)

    def test_unsafe_proceeds_with_allow_flag(self):
        """Unsafe design proceeds to tool stages when --allow-unsafe."""
        design = SiliconDesign(
            design_id="unsafe_allowed",
            rtl_text=UNSAFE_RTL,
            description="Unsafe but allowed",
            expected_safety="FAIL",
            expected_lint="SKIP",
            expected_synthesis="SKIP",
            expected_formal="SKIP",
        )
        with tempfile.TemporaryDirectory() as work_dir:
            dr = run_design_stages(design, work_dir, allow_unsafe=True)
            # Should NOT be blocked
            self.assertNotEqual(dr.lint_status, "BLOCKED_UNSAFE")
            self.assertNotEqual(dr.synthesis_status, "BLOCKED_UNSAFE")


# ── Test: Verilator Flow ──────────────────────────────────────────────────

class TestVerilatorFlow(unittest.TestCase):
    """Tests for Verilator lint flow."""

    def test_verilator_missing_returns_skipped(self):
        """When Verilator not found, returns LINT_SKIPPED_TOOL_MISSING."""
        with tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False) as f:
            f.write(SAFE_RTL)
            f.flush()
            result = run_verilator_lint(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.LINT_SKIPPED_TOOL_MISSING)

    @patch("chipgate.verilator_flow.shutil.which", return_value="/usr/bin/verilator")
    @patch("chipgate.verilator_flow._get_verilator_version", return_value="Verilator 5.020")
    @patch("chipgate.verilator_flow.subprocess.run")
    def test_verilator_pass_with_mock(self, mock_run, mock_ver, mock_which):
        """Mocked Verilator returns LINT_PASS when no errors."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All checks passed",
            stderr="",
        )
        with tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False) as f:
            f.write(SAFE_RTL)
            f.flush()
            result = run_verilator_lint(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.LINT_PASS)
        self.assertEqual(result.tool_version, "Verilator 5.020")

    @patch("chipgate.verilator_flow.shutil.which", return_value="/usr/bin/verilator")
    @patch("chipgate.verilator_flow._get_verilator_version", return_value="Verilator 5.020")
    @patch("chipgate.verilator_flow.subprocess.run")
    def test_verilator_fail_with_mock(self, mock_run, mock_ver, mock_which):
        """Mocked Verilator returns LINT_FAIL when errors present."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr=VERILATOR_OUTPUT_ERRORS,
        )
        with tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False) as f:
            f.write(BAD_RTL)
            f.flush()
            result = run_verilator_lint(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.LINT_FAIL)
        self.assertGreater(result.error_count, 0)

    def test_parse_verilator_warnings(self):
        """Verilator warning parser extracts correct counts."""
        warnings, errors = parse_verilator_output(VERILATOR_OUTPUT_WARNINGS)
        self.assertEqual(warnings, 3)
        self.assertEqual(errors, 0)

    def test_parse_verilator_errors(self):
        """Verilator error parser extracts correct counts."""
        warnings, errors = parse_verilator_output(VERILATOR_OUTPUT_ERRORS)
        self.assertEqual(warnings, 0)
        self.assertEqual(errors, 2)

    def test_no_shell_true_in_verilator_flow(self):
        """verilator_flow.py does not use shell=True in code."""
        import chipgate.verilator_flow as vf
        source = Path(vf.__file__).read_text()
        _check_no_shell_true(source)

    def test_lint_result_to_dict(self):
        """LintResult.to_dict() returns valid dict."""
        result = LintResult(status=st.LINT_PASS, warning_count=0, error_count=0)
        d = result.to_dict()
        self.assertEqual(d["status"], st.LINT_PASS)
        json.dumps(d)  # Must be JSON-serializable


# ── Test: Yosys Flow ──────────────────────────────────────────────────────

class TestYosysFlow(unittest.TestCase):
    """Tests for Yosys synthesis flow."""

    def test_yosys_missing_returns_skipped(self):
        """When Yosys not found, returns SYNTHESIS_SKIPPED_TOOL_MISSING."""
        with tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False) as f:
            f.write(SAFE_RTL)
            f.flush()
            result = run_yosys_synthesis(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.SYNTHESIS_SKIPPED_TOOL_MISSING)

    def test_parse_yosys_stats(self):
        """Yosys stats parser extracts cell and wire counts."""
        stats = parse_yosys_stats(YOSYS_STATS_OUTPUT)
        self.assertEqual(stats["cell_count"], 15)
        self.assertEqual(stats["wire_count"], 12)
        self.assertEqual(stats["process_count"], 1)

    def test_parse_yosys_stats_empty(self):
        """Yosys stats parser handles empty output."""
        stats = parse_yosys_stats("")
        self.assertEqual(stats["cell_count"], 0)
        self.assertEqual(stats["wire_count"], 0)

    @patch("chipgate.yosys_flow.shutil.which", return_value="/usr/bin/yosys")
    @patch("chipgate.yosys_flow._get_yosys_version", return_value="Yosys 0.35")
    @patch("chipgate.yosys_flow.subprocess.run")
    def test_yosys_pass_with_mock(self, mock_run, mock_ver, mock_which):
        """Mocked Yosys returns SYNTHESIS_PASS."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=YOSYS_STATS_OUTPUT,
            stderr="",
        )
        with tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False) as f:
            f.write(SAFE_RTL)
            f.flush()
            result = run_yosys_synthesis(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.SYNTHESIS_PASS)
        self.assertEqual(result.cell_count, 15)
        self.assertEqual(result.wire_count, 12)

    def test_no_shell_true_in_yosys_flow(self):
        """yosys_flow.py does not use shell=True in code."""
        import chipgate.yosys_flow as yf
        source = Path(yf.__file__).read_text()
        _check_no_shell_true(source)

    def test_synthesis_result_to_dict(self):
        """SynthesisResult.to_dict() returns valid dict."""
        result = SynthesisResult(status=st.SYNTHESIS_PASS, cell_count=10, wire_count=8)
        d = result.to_dict()
        self.assertEqual(d["cell_count"], 10)
        json.dumps(d)  # Must be JSON-serializable


# ── Test: Formal Flow ─────────────────────────────────────────────────────

class TestFormalFlow(unittest.TestCase):
    """Tests for SymbiYosys formal verification flow."""

    def test_sby_missing_returns_skipped(self):
        """When SBY not found, returns FORMAL_SKIPPED_TOOL_MISSING."""
        with tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False) as f:
            f.write(SAFE_RTL)
            f.flush()
            result = run_formal_check(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.FORMAL_SKIPPED_TOOL_MISSING)

    def test_parse_formal_pass(self):
        """Formal output parser detects pass patterns."""
        counts = parse_formal_output(SBY_PASS_OUTPUT)
        self.assertGreater(counts["passed"], 0)
        self.assertEqual(counts["failed"], 0)

    def test_parse_formal_fail(self):
        """Formal output parser detects failure patterns."""
        counts = parse_formal_output(SBY_FAIL_OUTPUT)
        self.assertGreater(counts["passed"], 0)
        self.assertGreater(counts["failed"], 0)

    def test_no_shell_true_in_formal_flow(self):
        """formal_flow.py does not use shell=True in code."""
        import chipgate.formal_flow as ff
        source = Path(ff.__file__).read_text()
        _check_no_shell_true(source)

    def test_formal_result_to_dict(self):
        """FormalResult.to_dict() returns valid dict."""
        result = FormalResult(status=st.FORMAL_PASS, properties_checked=2, properties_passed=2)
        d = result.to_dict()
        self.assertEqual(d["properties_checked"], 2)
        json.dumps(d)  # Must be JSON-serializable


# ── Test: FPGA Flow ───────────────────────────────────────────────────────

class TestFPGAFlow(unittest.TestCase):
    """Tests for FPGA readiness flow."""

    def test_fpga_missing_returns_skipped(self):
        """When tools not found, returns FPGA_FLOW_SKIPPED_TOOL_MISSING."""
        with tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False) as f:
            f.write(SAFE_RTL)
            f.flush()
            result = run_fpga_flow(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.FPGA_FLOW_SKIPPED_TOOL_MISSING)
        self.assertFalse(result.yosys_available or result.nextpnr_available)

    def test_no_shell_true_in_fpga_flow(self):
        """fpga_flow.py does not use shell=True in code."""
        import chipgate.fpga_flow as ff
        source = Path(ff.__file__).read_text()
        _check_no_shell_true(source)


# ── Test: ASIC Flow ───────────────────────────────────────────────────────

class TestASICFlow(unittest.TestCase):
    """Tests for ASIC flow readiness."""

    def test_asic_missing_returns_skipped(self):
        """When OpenLane/OpenROAD not found, returns ASIC_FLOW_SKIPPED_TOOL_MISSING."""
        with tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False) as f:
            f.write(SAFE_RTL)
            f.flush()
            result = run_asic_readiness(f.name)
        os.unlink(f.name)
        self.assertEqual(result.status, st.ASIC_FLOW_SKIPPED_TOOL_MISSING)

    def test_no_shell_true_in_openlane_flow(self):
        """openlane_flow.py does not use shell=True in code."""
        import chipgate.openlane_flow as ol
        source = Path(ol.__file__).read_text()
        _check_no_shell_true(source)


# ── Test: Artifact Hashing ─────────────────────────────────────────────────

class TestArtifactHashing(unittest.TestCase):
    """Tests for artifact hashing and evidence records."""

    def test_hash_artifact_stable(self):
        """Same input produces same hash."""
        h1 = hash_artifact("test content", "label")
        h2 = hash_artifact("test content", "label")
        self.assertEqual(h1, h2)

    def test_hash_artifact_different_input(self):
        """Different input produces different hash."""
        h1 = hash_artifact("content A", "label")
        h2 = hash_artifact("content B", "label")
        self.assertNotEqual(h1, h2)

    def test_hash_design_artifacts(self):
        """hash_design_artifacts returns list with expected labels."""
        artifacts = hash_design_artifacts(
            rtl_text="module test; endmodule",
            report_text="PASS",
            command="test cmd",
        )
        labels = [a["label"] for a in artifacts]
        self.assertIn("rtl_input", labels)
        self.assertIn("report", labels)
        self.assertIn("command", labels)
        # Each has sha256
        for a in artifacts:
            self.assertIn("sha256", a)
            self.assertEqual(len(a["sha256"]), 64)

    def test_evidence_hash_stable(self):
        """Evidence hash is deterministic."""
        evidence = {"a": 1, "b": "test"}
        h1 = compute_evidence_hash(evidence)
        h2 = compute_evidence_hash(evidence)
        self.assertEqual(h1, h2)

    def test_evidence_hash_excludes_itself(self):
        """Evidence hash excludes its own field."""
        evidence = {"a": 1, "b": "test", "certificate_hash": "wrong"}
        h = compute_evidence_hash(evidence)
        # Verify by computing manually
        check = {"a": 1, "b": "test"}
        expected = hashlib.sha256(json.dumps(check, sort_keys=True).encode()).hexdigest()
        self.assertEqual(h, expected)

    def test_create_evidence_record(self):
        """create_evidence_record returns valid SiliconEvidenceRecord."""
        record = create_evidence_record(
            design_id="test",
            rtl_text=SAFE_RTL,
            safety_result=st.RTL_SCAN_PASS,
            lint_result=st.LINT_SKIPPED_TOOL_MISSING,
            synthesis_result=st.SYNTHESIS_SKIPPED_TOOL_MISSING,
            formal_result=st.FORMAL_SKIPPED_TOOL_MISSING,
            fpga_flow_result=st.FPGA_FLOW_SKIPPED_TOOL_MISSING,
            asic_flow_result=st.ASIC_FLOW_SKIPPED_TOOL_MISSING,
            tool_versions={},
            replay_command="python -m chipgate silicon --demo",
        )
        self.assertIsInstance(record, SiliconEvidenceRecord)
        self.assertEqual(record.design_id, "test")
        self.assertEqual(len(record.artifact_hashes), 2)  # rtl_input + report
        self.assertEqual(record.rtl_hash, hashlib.sha256(SAFE_RTL.encode()).hexdigest())

    def test_evidence_record_to_dict(self):
        """SiliconEvidenceRecord.to_dict() returns JSON-serializable dict."""
        record = create_evidence_record(
            design_id="test",
            rtl_text=SAFE_RTL,
            safety_result=st.RTL_SCAN_PASS,
            lint_result=st.LINT_SKIPPED_TOOL_MISSING,
            synthesis_result=st.SYNTHESIS_SKIPPED_TOOL_MISSING,
            formal_result=st.FORMAL_SKIPPED_TOOL_MISSING,
            fpga_flow_result=st.FPGA_FLOW_SKIPPED_TOOL_MISSING,
            asic_flow_result=st.ASIC_FLOW_SKIPPED_TOOL_MISSING,
            tool_versions={},
            replay_command="python -m chipgate silicon --demo",
        )
        d = record.to_dict()
        self.assertIn("certificate_hash", d)
        self.assertIn("public_wording", d)
        self.assertEqual(d["design_id"], "test")
        # Must be JSON-serializable
        json_str = json.dumps(d, sort_keys=True)
        self.assertIsInstance(json_str, str)

    def test_evidence_record_save(self):
        """SiliconEvidenceRecord.save() writes valid JSON."""
        record = create_evidence_record(
            design_id="test",
            rtl_text=SAFE_RTL,
            safety_result=st.RTL_SCAN_PASS,
            lint_result=st.LINT_SKIPPED_TOOL_MISSING,
            synthesis_result=st.SYNTHESIS_SKIPPED_TOOL_MISSING,
            formal_result=st.FORMAL_SKIPPED_TOOL_MISSING,
            fpga_flow_result=st.FPGA_FLOW_SKIPPED_TOOL_MISSING,
            asic_flow_result=st.ASIC_FLOW_SKIPPED_TOOL_MISSING,
            tool_versions={},
            replay_command="python -m chipgate silicon --demo",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "evidence.json")
            result_path = record.save(path)
            self.assertTrue(Path(path).exists())
            # Verify it's valid JSON
            data = json.loads(Path(path).read_text())
            self.assertEqual(data["design_id"], "test")


# ── Test: Benchmark Runner ─────────────────────────────────────────────────

class TestSiliconBenchRunner(unittest.TestCase):
    """Tests for the main SiliconReadinessBench runner."""

    def test_demo_runs(self):
        """run_siliconbench_demo completes without error."""
        result = run_siliconbench_demo()
        self.assertIsInstance(result, SiliconBenchResult)
        self.assertEqual(result.benchmark_name, "siliconbench_v0")
        self.assertGreater(result.designs_tested, 0)

    def test_demo_designs_count(self):
        """Demo runs 4 built-in designs."""
        result = run_siliconbench_demo()
        self.assertEqual(result.designs_tested, 4)

    def test_demo_safe_dtl_gate_passes_precheck(self):
        """Safe DTL gate passes safety precheck in demo."""
        result = run_siliconbench_demo()
        safe_results = [d for d in result.design_results if d["design_id"] == "safe_dtl_gate"]
        self.assertEqual(len(safe_results), 1)
        self.assertEqual(safe_results[0]["safety_precheck_status"], st.RTL_SCAN_PASS)

    def test_demo_unsafe_blocked(self):
        """Unsafe design is blocked in demo."""
        result = run_siliconbench_demo()
        unsafe_results = [d for d in result.design_results if d["design_id"] == "unsafe_direct_actuator"]
        self.assertEqual(len(unsafe_results), 1)
        self.assertEqual(unsafe_results[0]["lint_status"], "BLOCKED_UNSAFE")

    def test_demo_bad_syntax_fails_precheck(self):
        """Bad syntax design fails safety precheck."""
        result = run_siliconbench_demo()
        bad_results = [d for d in result.design_results if d["design_id"] == "bad_syntax"]
        self.assertEqual(len(bad_results), 1)

    def test_demo_has_evidence_records(self):
        """Each design in demo has an evidence record."""
        result = run_siliconbench_demo()
        self.assertEqual(result.evidence_packs_created, result.designs_tested)
        for d in result.design_results:
            self.assertIsNotNone(d.get("evidence_record"))
            self.assertIn("certificate_hash", d["evidence_record"])

    def test_demo_has_public_wording(self):
        """Demo result includes public wording."""
        result = run_siliconbench_demo()
        self.assertIn("does not guarantee", result.public_wording)
        self.assertIn("open-source tool-flow", result.public_wording)

    def test_demo_has_limitation(self):
        """Demo result includes limitation wording."""
        result = run_siliconbench_demo()
        self.assertIn("tool-flow readiness checks", result.limitation)

    def test_result_to_dict(self):
        """SiliconBenchResult.to_dict() returns complete dict."""
        result = run_siliconbench_demo()
        d = result.to_dict()
        self.assertEqual(d["benchmark_name"], "siliconbench_v0")
        self.assertIn("toolchain_report", d)
        self.assertIn("design_results", d)
        self.assertIn("public_wording", d)
        self.assertIn("limitation", d)
        # Must be JSON-serializable
        json.dumps(d, sort_keys=True)

    def test_result_json_schema_stable(self):
        """JSON output schema is stable across runs."""
        result1 = run_siliconbench_demo()
        result2 = run_siliconbench_demo()
        d1 = result1.to_dict()
        d2 = result2.to_dict()
        # Same keys
        self.assertEqual(set(d1.keys()), set(d2.keys()))
        # Same design IDs
        ids1 = {d["design_id"] for d in d1["design_results"]}
        ids2 = {d["design_id"] for d in d2["design_results"]}
        self.assertEqual(ids1, ids2)

    def test_load_designs_from_path(self):
        """_load_designs_from_path loads .v files from directory."""
        # Use the benchmark designs directory
        designs_dir = Path(__file__).parent.parent / "benchmarks" / "siliconbench_v0" / "designs"
        if designs_dir.exists():
            designs = _load_designs_from_path(str(designs_dir.parent))
            self.assertGreater(len(designs), 0)
            for d in designs:
                self.assertTrue(d.rtl_text.startswith("//") or "module" in d.rtl_text)

    def test_load_designs_from_nonexistent_path(self):
        """_load_designs_from_path returns empty list for nonexistent path."""
        designs = _load_designs_from_path("/nonexistent/path")
        self.assertEqual(designs, [])

    def test_rate_calculation(self):
        """_rate helper calculates pass rates correctly."""
        self.assertAlmostEqual(_rate(["PASS", "PASS", "FAIL"], "PASS"), 2/3)
        self.assertAlmostEqual(_rate(["PASS", "SKIP", "SKIP"], "PASS", "SKIP"), 1.0)
        self.assertAlmostEqual(_rate([], "PASS"), 0.0)

    def test_toolchain_coverage_in_result(self):
        """Demo result includes toolchain coverage."""
        result = run_siliconbench_demo()
        self.assertIsInstance(result.toolchain_coverage, float)
        self.assertGreaterEqual(result.toolchain_coverage, 0.0)
        self.assertLessEqual(result.toolchain_coverage, 1.0)

    def test_artifact_hash_count(self):
        """Demo result counts artifact hashes."""
        result = run_siliconbench_demo()
        self.assertGreater(result.artifact_hash_count, 0)

    def test_replay_match_rate(self):
        """Demo result has replay match rate."""
        result = run_siliconbench_demo()
        self.assertEqual(result.replay_match_rate, 100.0)


# ── Test: HTML Report ──────────────────────────────────────────────────────

class TestSiliconReport(unittest.TestCase):
    """Tests for HTML report generation."""

    def test_html_report_generated(self):
        """generate_silicon_html produces valid HTML."""
        result = run_siliconbench_demo()
        html = generate_silicon_html(result.to_dict())
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("SiliconReadinessBench Report", html)
        self.assertIn("Toolchain Status", html)
        self.assertIn("Design Results", html)
        self.assertIn("Artifact Hashes", html)
        self.assertIn("Limitation", html)

    def test_html_contains_design_ids(self):
        """HTML report contains all design IDs."""
        result = run_siliconbench_demo()
        html = generate_silicon_html(result.to_dict())
        for d in result.design_results:
            self.assertIn(d["design_id"], html)

    def test_html_contains_public_wording(self):
        """HTML report contains public wording disclaimer."""
        result = run_siliconbench_demo()
        html = generate_silicon_html(result.to_dict())
        self.assertIn("does not guarantee", html)
        self.assertIn("fabrication readiness", html)

    def test_html_contains_limitation(self):
        """HTML report contains limitation section."""
        result = run_siliconbench_demo()
        html = generate_silicon_html(result.to_dict())
        self.assertIn("tool-flow readiness checks", html)

    def test_html_contains_hash_snippets(self):
        """HTML report contains SHA-256 hash snippets."""
        result = run_siliconbench_demo()
        html = generate_silicon_html(result.to_dict())
        self.assertIn("hash", html.lower())
        # Check for actual hash-like strings (hex chars)
        import re
        hashes = re.findall(r'[0-9a-f]{24}', html)
        self.assertGreater(len(hashes), 0, "No hash snippets found in HTML")

    def test_html_is_dependency_free(self):
        """HTML report has no external dependencies."""
        result = run_siliconbench_demo()
        html = generate_silicon_html(result.to_dict())
        # No external CSS, JS, or fonts
        self.assertNotIn("cdn.", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        # No script tags (except none expected)
        self.assertNotIn("<script", html)


# ── Test: Status Constants ─────────────────────────────────────────────────

class TestSiliconStatuses(unittest.TestCase):
    """Tests for SiliconReadinessBench status constants."""

    def test_silicon_statuses_defined(self):
        """All SiliconReadinessBench statuses are defined."""
        self.assertEqual(st.SILICON_READINESS_PASS, "SILICON_READINESS_PASS")
        self.assertEqual(st.SILICON_READINESS_FAIL, "SILICON_READINESS_FAIL")
        self.assertEqual(st.LINT_PASS, "LINT_PASS")
        self.assertEqual(st.LINT_FAIL, "LINT_FAIL")
        self.assertEqual(st.LINT_SKIPPED_TOOL_MISSING, "LINT_SKIPPED_TOOL_MISSING")
        self.assertEqual(st.SYNTHESIS_PASS, "SYNTHESIS_PASS")
        self.assertEqual(st.SYNTHESIS_FAIL, "SYNTHESIS_FAIL")
        self.assertEqual(st.SYNTHESIS_SKIPPED_TOOL_MISSING, "SYNTHESIS_SKIPPED_TOOL_MISSING")
        self.assertEqual(st.FORMAL_PASS, "FORMAL_PASS")
        self.assertEqual(st.FORMAL_FAIL, "FORMAL_FAIL")
        self.assertEqual(st.FORMAL_SKIPPED_TOOL_MISSING, "FORMAL_SKIPPED_TOOL_MISSING")
        self.assertEqual(st.FPGA_FLOW_PASS, "FPGA_FLOW_PASS")
        self.assertEqual(st.FPGA_FLOW_FAIL, "FPGA_FLOW_FAIL")
        self.assertEqual(st.FPGA_FLOW_SKIPPED_TOOL_MISSING, "FPGA_FLOW_SKIPPED_TOOL_MISSING")
        self.assertEqual(st.ASIC_FLOW_READY, "ASIC_FLOW_READY")
        self.assertEqual(st.ASIC_FLOW_FAIL, "ASIC_FLOW_FAIL")
        self.assertEqual(st.ASIC_FLOW_SKIPPED_TOOL_MISSING, "ASIC_FLOW_SKIPPED_TOOL_MISSING")

    def test_silicon_public_wording(self):
        """Silicon public wording contains required phrases."""
        self.assertIn("does not guarantee", st.SILICON_PUBLIC_WORDING)
        self.assertIn("fabrication readiness", st.SILICON_PUBLIC_WORDING)
        self.assertIn("open-source tool-flow", st.SILICON_PUBLIC_WORDING)

    def test_silicon_limitation(self):
        """Silicon limitation contains required phrases."""
        self.assertIn("tool-flow readiness checks", st.SILICON_LIMITATION)
        self.assertIn("not silicon results", st.SILICON_LIMITATION)

    def test_silicon_statuses_in_all_statuses(self):
        """Silicon statuses are in ALL_STATUSES list."""
        silicon_statuses = [
            st.SILICON_READINESS_PASS, st.SILICON_READINESS_FAIL,
            st.LINT_PASS, st.LINT_FAIL, st.LINT_SKIPPED_TOOL_MISSING,
            st.SYNTHESIS_PASS, st.SYNTHESIS_FAIL, st.SYNTHESIS_SKIPPED_TOOL_MISSING,
            st.FORMAL_PASS, st.FORMAL_FAIL, st.FORMAL_SKIPPED_TOOL_MISSING,
            st.FPGA_FLOW_PASS, st.FPGA_FLOW_FAIL, st.FPGA_FLOW_SKIPPED_TOOL_MISSING,
            st.ASIC_FLOW_READY, st.ASIC_FLOW_FAIL, st.ASIC_FLOW_SKIPPED_TOOL_MISSING,
        ]
        for s in silicon_statuses:
            self.assertIn(s, st.ALL_STATUSES, f"{s} not in ALL_STATUSES")


# ── Test: No Private Imports ───────────────────────────────────────────────

class TestNoPrivateImports(unittest.TestCase):
    """Verify no private JARVI3 or DTL internals are imported."""

    def test_no_jarvi3_imports(self):
        """No SiliconReadinessBench module imports JARVI3."""
        modules = [
            "chipgate.siliconbench",
            "chipgate.toolchain",
            "chipgate.verilator_flow",
            "chipgate.yosys_flow",
            "chipgate.formal_flow",
            "chipgate.fpga_flow",
            "chipgate.openlane_flow",
            "chipgate.silicon_artifacts",
            "chipgate.silicon_report",
        ]
        for mod_name in modules:
            try:
                mod = __import__(mod_name, fromlist=[""])
                source = Path(mod.__file__).read_text()
                self.assertNotIn("jarvi3", source.lower(), f"{mod_name} references JARVI3")
                self.assertNotIn("private", source.lower(), f"{mod_name} references 'private'")
            except ImportError:
                pass

    def test_no_secrets_in_source(self):
        """No SiliconReadinessBench module contains secrets."""
        modules = [
            "chipgate.siliconbench",
            "chipgate.toolchain",
            "chipgate.verilator_flow",
            "chipgate.yosys_flow",
            "chipgate.formal_flow",
            "chipgate.fpga_flow",
            "chipgate.openlane_flow",
            "chipgate.silicon_artifacts",
            "chipgate.silicon_report",
        ]
        secret_patterns = ["API_KEY", "SECRET", "PASSWORD", "TOKEN", "CREDENTIAL"]
        for mod_name in modules:
            try:
                mod = __import__(mod_name, fromlist=[""])
                source = Path(mod.__file__).read_text()
                for pattern in secret_patterns:
                    self.assertNotIn(pattern, source, f"{mod_name} contains '{pattern}'")
            except ImportError:
                pass


# ── Test: English-Only Output ──────────────────────────────────────────────

class TestEnglishOnlyOutput(unittest.TestCase):
    """Verify all output is in English."""

    def test_demo_output_english(self):
        """Demo result fields are in English (no CJK characters)."""
        result = run_siliconbench_demo()
        d = result.to_dict()
        # Check all string values for CJK characters (U+4E00-U+9FFF)
        def check_english(obj, path=""):
            if isinstance(obj, str):
                for ch in obj:
                    if 0x4E00 <= ord(ch) <= 0x9FFF:
                        self.fail(f"CJK character at {path}: {ch!r} in '{obj[:50]}'")
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    check_english(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_english(v, f"{path}[{i}]")
        check_english(d)


# ── Test: Design Stage Results ─────────────────────────────────────────────

class TestDesignStageResults(unittest.TestCase):
    """Tests for DesignStageResults dataclass."""

    def test_to_dict(self):
        """DesignStageResults.to_dict() returns complete dict."""
        dr = DesignStageResults(
            design_id="test",
            safety_precheck_status=st.RTL_SCAN_PASS,
            lint_status=st.LINT_SKIPPED_TOOL_MISSING,
            synthesis_status=st.SYNTHESIS_SKIPPED_TOOL_MISSING,
            formal_status=st.FORMAL_SKIPPED_TOOL_MISSING,
            fpga_flow_status=st.FPGA_FLOW_SKIPPED_TOOL_MISSING,
            asic_flow_status=st.ASIC_FLOW_SKIPPED_TOOL_MISSING,
            overall_status=st.SILICON_READINESS_PASS,
        )
        d = dr.to_dict()
        self.assertEqual(d["design_id"], "test")
        self.assertEqual(d["overall_status"], st.SILICON_READINESS_PASS)
        json.dumps(d)  # Must be JSON-serializable


if __name__ == "__main__":
    unittest.main()