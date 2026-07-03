"""
Tests for ChipGate TinyTapeoutPrep (Phase 9).

Tests cover:
  - tt_pinout: pinout generation, validation, JSON round-trip
  - tt_wrapper: core, wrapper, FSM generation
  - tt_docs: info.yaml, info.md, testbench, checklist generation
  - tt_submission_check: all 15 checks, private leak detection, SV detection
  - tt_report: HTML report generation
  - tinytapeout_prep: full orchestrator, demo mode, evidence pack
  - CLI integration: tinytapeout subcommand

No private imports, no secrets, no shell=True. English-only.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from chipgate import statuses as st
from chipgate.tt_pinout import (
    INPUT_PINOUT,
    OUTPUT_PINOUT,
    RESERVED_INPUTS,
    RESERVED_OUTPUTS,
    TT_INPUT_WIDTH,
    TT_OUTPUT_WIDTH,
    get_canonical_pinout,
    get_input_pinout,
    get_output_pinout,
    validate_pinout,
    pinout_to_json,
    load_pinout_from_json,
    _extract_pin_index,
)
from chipgate.tt_wrapper import (
    generate_core_verilog,
    generate_wrapper_verilog,
    generate_fsm_verilog,
)
from chipgate.tt_docs import (
    generate_info_yaml,
    generate_info_md,
    generate_submission_checklist,
    generate_testbench_verilog,
)
from chipgate.tt_submission_check import (
    run_submission_checks,
    _detect_private_names,
    _detect_unsupported_sv,
    _structural_scan,
    SubmissionCheckResult,
)
from chipgate.tt_report import generate_tinytapeout_html, _short_html
from chipgate.tinytapeout_prep import (
    run_tinytapeout_prep,
    SAFETY_PROPERTIES,
    TinyTapeoutPrepResult,
    DesignResult,
    _check_safety_in_verilog,
    _design_overall,
    _create_evidence_pack,
)


# ══════════════════════════════════════════════════════════════════════════════
# tt_pinout tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPinout:
    """Tests for tt_pinout module."""

    def test_canonical_pinout_has_all_inputs(self):
        pinout = get_canonical_pinout()
        for sig in INPUT_PINOUT:
            assert sig in pinout, f"Missing input signal: {sig}"

    def test_canonical_pinout_has_all_outputs(self):
        pinout = get_canonical_pinout()
        for sig in OUTPUT_PINOUT:
            assert sig in pinout, f"Missing output signal: {sig}"

    def test_input_pinout_only_inputs(self):
        inp = get_input_pinout()
        for sig in inp:
            assert sig in INPUT_PINOUT
        assert len(inp) == len(INPUT_PINOUT)

    def test_output_pinout_only_outputs(self):
        out = get_output_pinout()
        for sig in out:
            assert sig in OUTPUT_PINOUT
        assert len(out) == len(OUTPUT_PINOUT)

    def test_valid_pinout_passes(self):
        pinout = get_canonical_pinout()
        result = validate_pinout(pinout)
        assert result.valid is True
        assert result.status == st.TT_PINOUT_VALID

    def test_missing_signal_fails(self):
        pinout = get_canonical_pinout()
        del pinout["kill_switch"]
        result = validate_pinout(pinout)
        assert result.valid is False
        assert result.status == st.TT_PINOUT_INVALID
        assert any("kill_switch" in i for i in result.issues)

    def test_duplicate_pin_fails(self):
        pinout = get_canonical_pinout()
        pinout["extra_signal"] = pinout["ai_output"]  # duplicate pin
        result = validate_pinout(pinout)
        assert result.valid is False

    def test_out_of_range_pin_fails(self):
        pinout = get_canonical_pinout()
        pinout["ai_output"] = "ui_in[8]"  # out of range
        result = validate_pinout(pinout)
        assert result.valid is False
        assert any("out of range" in i for i in result.issues)

    def test_json_round_trip(self):
        pinout = get_canonical_pinout()
        json_str = pinout_to_json(pinout)
        loaded = load_pinout_from_json(json_str)
        assert loaded == pinout

    def test_extract_pin_index(self):
        assert _extract_pin_index("ui_in[3]") == 3
        assert _extract_pin_index("uo_out[0]") == 0
        assert _extract_pin_index("ui_in[7]") == 7
        assert _extract_pin_index("invalid") is None
        assert _extract_pin_index("ui_in[abc]") is None

    def test_reserved_pins_exist(self):
        assert 7 in RESERVED_INPUTS
        assert 5 in RESERVED_OUTPUTS
        assert 6 in RESERVED_OUTPUTS
        assert 7 in RESERVED_OUTPUTS

    def test_tt_widths(self):
        assert TT_INPUT_WIDTH == 8
        assert TT_OUTPUT_WIDTH == 8


# ══════════════════════════════════════════════════════════════════════════════
# tt_wrapper tests
# ══════════════════════════════════════════════════════════════════════════════

class TestWrapper:
    """Tests for tt_wrapper module."""

    def test_core_verilog_has_module(self):
        v = generate_core_verilog()
        assert "module tiny_dtl_gate" in v
        assert "endmodule" in v

    def test_core_verilog_has_all_inputs(self):
        v = generate_core_verilog()
        for sig in INPUT_PINOUT:
            assert f"input  wire {sig}" in v, f"Missing input: {sig}"

    def test_core_verilog_has_all_outputs(self):
        v = generate_core_verilog()
        for sig in OUTPUT_PINOUT:
            assert f"output wire {sig}" in v, f"Missing output: {sig}"

    def test_core_verilog_has_safety_logic(self):
        v = generate_core_verilog()
        assert "actuator_enable" in v
        assert "kill_switch" in v
        assert "verifier_ok" in v
        assert "policy_ok" in v
        assert "sensor_ok" in v
        assert "timeout" in v
        assert "reset" in v

    def test_core_verilog_no_private_names(self):
        v = generate_core_verilog()
        assert "jarvi3" not in v.lower()
        assert "proprietary" not in v.lower()
        assert "confidential" not in v.lower()

    def test_wrapper_verilog_has_top_module(self):
        v = generate_wrapper_verilog()
        assert "module tt_um_chipgate_dtl_gate" in v
        assert "endmodule" in v

    def test_wrapper_has_tt_ports(self):
        v = generate_wrapper_verilog()
        assert "ui_in" in v
        assert "uo_out" in v
        assert "uio_in" in v
        assert "uio_out" in v
        assert "uio_oe" in v
        assert "ena" in v
        assert "clk" in v
        assert "rst_n" in v

    def test_wrapper_instantiates_core(self):
        v = generate_wrapper_verilog()
        assert "tiny_dtl_gate core" in v

    def test_wrapper_maps_pins(self):
        v = generate_wrapper_verilog()
        assert "assign ai_output = ui_in[0]" in v
        assert "assign uo_out[0] = actuator_enable" in v

    def test_fsm_verilog_has_states(self):
        v = generate_fsm_verilog()
        assert "S_IDLE" in v
        assert "S_PROPOSED" in v
        assert "S_VERIFYING" in v
        assert "S_APPROVED" in v
        assert "S_BLOCKED" in v
        assert "S_FAILSAFE" in v

    def test_fsm_verilog_has_kill_switch(self):
        v = generate_fsm_verilog()
        assert "kill_switch" in v

    def test_fsm_has_case_statement(self):
        v = generate_fsm_verilog()
        assert "case (state)" in v

    def test_custom_module_names(self):
        v = generate_core_verilog(module_name="my_gate")
        assert "module my_gate" in v

        w = generate_wrapper_verilog(
            core_module="my_gate",
            top_module="tt_um_custom",
        )
        assert "module tt_um_custom" in w
        assert "my_gate core" in w


# ══════════════════════════════════════════════════════════════════════════════
# tt_docs tests
# ══════════════════════════════════════════════════════════════════════════════

class TestDocs:
    """Tests for tt_docs module."""

    def test_info_yaml_has_project_name(self):
        yaml = generate_info_yaml()
        assert "project_name: tt_um_chipgate_dtl_gate" in yaml

    def test_info_yaml_has_author(self):
        yaml = generate_info_yaml()
        assert "author:" in yaml

    def test_info_yaml_has_pin_comments(self):
        yaml = generate_info_yaml()
        assert "ui_in[0]" in yaml
        assert "kill_switch" in yaml

    def test_info_yaml_has_limitations(self):
        yaml = generate_info_yaml()
        assert "does not guarantee" in yaml.lower()

    def test_info_md_has_overview(self):
        md = generate_info_md()
        assert "# tt_um_chipgate_dtl_gate" in md
        assert "## Overview" in md

    def test_info_md_has_pin_tables(self):
        md = generate_info_md()
        assert "## Pin Mapping" in md
        assert "| ui_in[0]" in md
        assert "| uo_out[0]" in md

    def test_info_md_has_safety_properties(self):
        md = generate_info_md()
        assert "## Safety Properties" in md
        assert "kill_switch" in md

    def test_info_md_has_limitations(self):
        md = generate_info_md()
        assert "## Limitations" in md

    def test_testbench_has_module(self):
        tb = generate_testbench_verilog()
        assert "module tb_tiny_dtl_gate" in tb
        assert "endmodule" in tb

    def test_testbench_instantiates_core(self):
        tb = generate_testbench_verilog()
        assert "tiny_dtl_gate dut" in tb

    def test_testbench_has_test_cases(self):
        tb = generate_testbench_verilog()
        assert "Test 1:" in tb
        assert "Test 2:" in tb
        assert "Test 8:" in tb

    def test_testbench_checks_kill_switch(self):
        tb = generate_testbench_verilog()
        assert "kill_switch" in tb

    def test_submission_checklist_has_all_15(self):
        checks = [
            {"id": str(i), "name": f"Check {i}", "status": "PASS"}
            for i in range(1, 16)
        ]
        md = generate_submission_checklist(checks=checks)
        for i in range(1, 16):
            assert f"| {i} |" in md

    def test_default_checklist_has_15_entries(self):
        md = generate_submission_checklist()
        assert "| 1 |" in md
        assert "| 15 |" in md


# ══════════════════════════════════════════════════════════════════════════════
# tt_submission_check tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSubmissionCheck:
    """Tests for tt_submission_check module."""

    def _good_inputs(self):
        """Return good inputs for submission checks."""
        wrapper = generate_wrapper_verilog()
        yaml = generate_info_yaml()
        md = generate_info_md()
        tb = generate_testbench_verilog()
        return wrapper, yaml, md, tb

    def test_all_15_checks_run(self):
        wrapper, yaml, md, tb = self._good_inputs()
        result = run_submission_checks(wrapper, yaml, md, tb)
        assert len(result.checks) == 15

    def test_check_ids_sequential(self):
        wrapper, yaml, md, tb = self._good_inputs()
        result = run_submission_checks(wrapper, yaml, md, tb)
        ids = [c["id"] for c in result.checks]
        assert ids == [str(i) for i in range(1, 16)]

    def test_good_design_passes_all_non_skip(self):
        wrapper, yaml, md, tb = self._good_inputs()
        result = run_submission_checks(wrapper, yaml, md, tb)
        for chk in result.checks:
            if chk["status"] != "SKIP":
                assert chk["status"] == "PASS", f"Check {chk['id']} failed: {chk.get('detail', '')}"

    def test_private_name_detected(self):
        wrapper = generate_wrapper_verilog()
        wrapper += "\n// This is based on JARVI3 proprietary logic\n"
        yaml = generate_info_yaml()
        md = generate_info_md()
        tb = generate_testbench_verilog()
        result = run_submission_checks(wrapper, yaml, md, tb)
        chk3 = next(c for c in result.checks if c["id"] == "3")
        assert chk3["status"] == "FAIL"

    def test_unsupported_sv_detected(self):
        wrapper = generate_wrapper_verilog()
        wrapper = wrapper.replace(
            "module tt_um_chipgate_dtl_gate",
            "module tt_um_chipgate_dtl_gate\n"
            "  class my_class;\n"
            "  endclass\n"
            "module tt_um_chipgate_dtl_gate"
        )
        yaml = generate_info_yaml()
        md = generate_info_md()
        tb = generate_testbench_verilog()
        result = run_submission_checks(wrapper, yaml, md, tb)
        chk4 = next(c for c in result.checks if c["id"] == "4")
        assert chk4["status"] == "FAIL"

    def test_bench_checks_skip_safely(self):
        wrapper, yaml, md, tb = self._good_inputs()
        result = run_submission_checks(wrapper, yaml, md, tb)
        for chk_id in ["13", "14", "15"]:
            chk = next(c for c in result.checks if c["id"] == chk_id)
            assert chk["status"] == "SKIP"

    def test_manual_review_items_for_benches(self):
        wrapper, yaml, md, tb = self._good_inputs()
        result = run_submission_checks(wrapper, yaml, md, tb)
        assert any("LongevityBench" in item for item in result.manual_review_items)
        assert any("SiliconReadinessBench" in item for item in result.manual_review_items)
        assert any("FPGABoardBench" in item for item in result.manual_review_items)

    def test_empty_content_fails_existence_checks(self):
        result = run_submission_checks("", "", "", "")
        chk1 = next(c for c in result.checks if c["id"] == "1")
        assert chk1["status"] == "FAIL"

    def test_wrong_module_name_fails(self):
        wrapper = "module wrong_name (input clk); endmodule"
        yaml = generate_info_yaml()
        md = generate_info_md()
        tb = generate_testbench_verilog()
        result = run_submission_checks(wrapper, yaml, md, tb)
        chk2 = next(c for c in result.checks if c["id"] == "2")
        assert chk2["status"] == "FAIL"

    def test_result_tally(self):
        wrapper, yaml, md, tb = self._good_inputs()
        result = run_submission_checks(wrapper, yaml, md, tb)
        assert result.passed_count + result.failed_count + result.skipped_count == 15
        assert result.skipped_count == 3  # checks 13-15

    def test_detect_private_names_helper(self):
        assert len(_detect_private_names("normal verilog code")) == 0
        assert len(_detect_private_names("// jarvi3 internal module")) > 0
        assert len(_detect_private_names("// PROPRIETARY code")) > 0
        assert len(_detect_private_names("// confidential do not share")) > 0

    def test_detect_unsupported_sv_helper(self):
        assert len(_detect_unsupported_sv("assign a = b;")) == 0
        assert len(_detect_unsupported_sv("class my_class;")) > 0
        assert len(_detect_unsupported_sv("interface my_if;")) > 0

    def test_structural_scan_ungated(self):
        v = "module bad(input clk, output reg actuator_enable);\n"
        v += "always @(posedge clk) actuator_enable <= 1'b1;\nendmodule"
        issues = _structural_scan(v)
        assert len(issues) > 0
        assert any("kill_switch" in i for i in issues)

    def test_structural_scan_gated_passes(self):
        v = "module ok(input clk, input kill_switch, input verifier_ok, "
        v += "input timeout, input reset, output actuator_enable);\n"
        v += "assign actuator_enable = clk && !kill_switch && verifier_ok "
        v += "&& !timeout && !reset;\nendmodule"
        issues = _structural_scan(v)
        assert len(issues) == 0


# ══════════════════════════════════════════════════════════════════════════════
# tt_report tests
# ══════════════════════════════════════════════════════════════════════════════

class TestReport:
    """Tests for tt_report module."""

    def test_html_contains_title(self):
        data = {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "benchmark_version": "0.5.0",
            "overall_status": "TINYTAPEOUT_PREP_PASS",
            "design_results": [],
            "pinout": {"ui_in[0]": "ai_output"},
            "submission_checks": [],
            "manual_review_items": [],
            "designs_generated": 2,
            "wrappers_generated": 1,
            "pinout_checks_passed": 1,
            "submission_checks_passed": 12,
            "safety_properties_count": 5,
            "private_leak_count": 0,
            "testbench_count": 1,
            "evidence_packs_created": 1,
            "public_wording": "Test public wording",
            "limitation": "Test limitation",
        }
        html = generate_tinytapeout_html(data)
        assert "ChipGate TinyTapeoutPrep Report" in html
        assert "</html>" in html

    def test_html_contains_limitations(self):
        data = {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "benchmark_version": "0.5.0",
            "overall_status": "TINYTAPEOUT_PREP_PASS",
            "design_results": [],
            "pinout": {},
            "submission_checks": [],
            "manual_review_items": [],
            "designs_generated": 0,
            "wrappers_generated": 0,
            "pinout_checks_passed": 0,
            "submission_checks_passed": 0,
            "safety_properties_count": 0,
            "private_leak_count": 0,
            "testbench_count": 0,
            "evidence_packs_created": 0,
            "public_wording": "Test",
            "limitation": "This is a limitation disclaimer",
        }
        html = generate_tinytapeout_html(data)
        assert "This is a limitation disclaimer" in html

    def test_html_has_no_external_deps(self):
        data = {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "benchmark_version": "0.5.0",
            "overall_status": "TINYTAPEOUT_PREP_PASS",
            "design_results": [],
            "pinout": {},
            "submission_checks": [],
            "manual_review_items": [],
            "designs_generated": 0,
            "wrappers_generated": 0,
            "pinout_checks_passed": 0,
            "submission_checks_passed": 0,
            "safety_properties_count": 0,
            "private_leak_count": 0,
            "testbench_count": 0,
            "evidence_packs_created": 0,
            "public_wording": "",
            "limitation": "",
        }
        html = generate_tinytapeout_html(data)
        # No external CSS or JS references
        assert "<link" not in html
        assert "<script" not in html
        assert "cdn" not in html.lower()

    def test_short_html_pass(self):
        assert "PASS" in _short_html("SIMULATION_PASS")
        assert "PASS" in _short_html("TINYTAPEOUT_PREP_PASS")
        assert "PASS" in _short_html("TT_SUBMISSION_CHECK_PASS")

    def test_short_html_fail(self):
        assert "FAIL" in _short_html("RTL_SCAN_FAIL")
        assert "FAIL" in _short_html("TINYTAPEOUT_PREP_FAIL")
        assert "FAIL" in _short_html("TT_PINOUT_INVALID")

    def test_short_html_skip(self):
        assert "SKIP" in _short_html("FPGA_SYNTH_SKIPPED_TOOL_MISSING")


# ══════════════════════════════════════════════════════════════════════════════
# tinytapeout_prep orchestrator tests
# ══════════════════════════════════════════════════════════════════════════════

class TestOrchestrator:
    """Tests for the main TinyTapeoutPrep orchestrator."""

    def test_demo_run_returns_result(self):
        result = run_tinytapeout_prep(demo=True)
        assert isinstance(result, TinyTapeoutPrepResult)

    def test_demo_generates_designs(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.designs_generated >= 2

    def test_demo_creates_wrapper(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.wrappers_generated >= 1

    def test_demo_pinout_valid(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.pinout_checks_passed >= 1

    def test_demo_has_evidence_pack(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.evidence_packs_created >= 1

    def test_demo_no_private_leaks(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.private_leak_count == 0

    def test_demo_has_testbench(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.testbench_count >= 1

    def test_demo_has_safety_properties(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.safety_properties_count >= 5

    def test_demo_has_timestamp(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.timestamp_utc != ""
        assert "T" in result.timestamp_utc  # ISO format

    def test_demo_has_public_wording(self):
        result = run_tinytapeout_prep(demo=True)
        assert "does not guarantee" in result.public_wording.lower()

    def test_demo_has_limitation(self):
        result = run_tinytapeout_prep(demo=True)
        assert "does not mean" in result.limitation.lower()

    def test_demo_submission_checks_15(self):
        result = run_tinytapeout_prep(demo=True)
        assert len(result.submission_checks) == 15

    def test_demo_overall_pass(self):
        result = run_tinytapeout_prep(demo=True)
        assert result.overall_status == st.TINYTAPEOUT_PREP_PASS

    def test_demo_two_design_results(self):
        result = run_tinytapeout_prep(demo=True)
        assert len(result.design_results) >= 2

    def test_output_dir_creates_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_tinytapeout_prep(demo=True, output_dir=tmpdir)
            assert result.artifacts_dir == tmpdir
            assert Path(tmpdir, "info.yaml").exists()
            assert Path(tmpdir, "pinout.json").exists()
            assert Path(tmpdir, "submission_checklist.md").exists()
            assert Path(tmpdir, "evidence_pack.json").exists()
            assert Path(tmpdir, "designs", "tiny_dtl_gate.v").exists()
            assert Path(tmpdir, "designs", "tt_um_chipgate_dtl_gate.v").exists()
            assert Path(tmpdir, "testbenches", "tb_tiny_dtl_gate.v").exists()
            assert Path(tmpdir, "docs", "info.md").exists()

    def test_evidence_pack_has_sha256(self):
        result = run_tinytapeout_prep(demo=True)
        with open(Path(result.artifacts_dir, "evidence_pack.json")) as f:
            pack = json.load(f)
        assert "artifacts" in pack
        for name, info in pack["artifacts"].items():
            assert "sha256" in info
            assert len(info["sha256"]) == 64

    def test_to_dict_has_all_keys(self):
        result = run_tinytapeout_prep(demo=True)
        d = result.to_dict()
        expected_keys = {
            "benchmark_version", "timestamp_utc", "overall_status",
            "designs_generated", "wrappers_generated", "pinout_checks_passed",
            "submission_checks_passed", "submission_checks_failed",
            "submission_checks_skipped", "safety_properties_count",
            "private_leak_count", "testbench_count", "evidence_packs_created",
            "manual_review_items_count", "design_results", "pinout",
            "submission_checks", "manual_review_items", "public_wording",
            "limitation", "artifacts_dir",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_check_safety_in_verilog_passes(self):
        v = generate_core_verilog()
        assert _check_safety_in_verilog(v) == st.SAFETY_GATE_PRESENT

    def test_check_safety_in_verilog_fails(self):
        v = "module bad(input x, output y); assign y = x; endmodule"
        assert _check_safety_in_verilog(v) == st.TT_SAFETY_PROPERTY_MISSING

    def test_design_overall_pass(self):
        d = DesignResult(
            wrapper_status=st.TT_WRAPPER_CREATED,
            pinout_status=st.TT_PINOUT_VALID,
            submission_check_status=st.TT_SUBMISSION_CHECK_PASS,
            safety_result=st.SAFETY_GATE_PRESENT,
        )
        assert _design_overall(d) == st.TINYTAPEOUT_PREP_PASS

    def test_design_overall_fail(self):
        d = DesignResult(
            wrapper_status=st.TT_WRAPPER_CREATED,
            pinout_status=st.TT_PINOUT_INVALID,
            submission_check_status=st.TT_SUBMISSION_CHECK_PASS,
            safety_result=st.SAFETY_GATE_PRESENT,
        )
        assert _design_overall(d) == st.TINYTAPEOUT_PREP_FAIL

    def test_benchmark_dir_integration(self):
        """Test that the benchmark directory artifacts are valid."""
        bench_dir = Path(__file__).parent.parent / "benchmarks" / "tinytapeoutprep_v0"
        if not bench_dir.exists():
            pytest.skip("Benchmark directory not yet created")
        assert (bench_dir / "info.yaml").exists()
        assert (bench_dir / "pinout.json").exists()
        assert (bench_dir / "designs" / "tiny_dtl_gate.v").exists()


# ══════════════════════════════════════════════════════════════════════════════
# Status constants tests
# ══════════════════════════════════════════════════════════════════════════════

class TestStatusConstants:
    """Tests for Phase 9 status constants."""

    def test_tt_prep_pass_in_pass_statuses(self):
        assert st.TINYTAPEOUT_PREP_PASS in st.PASS_STATUSES

    def test_tt_prep_fail_in_fail_statuses(self):
        assert st.TINYTAPEOUT_PREP_FAIL in st.FAIL_STATUSES

    def test_tt_wrapper_created_in_pass(self):
        assert st.TT_WRAPPER_CREATED in st.PASS_STATUSES

    def test_tt_wrapper_missing_in_fail(self):
        assert st.TT_WRAPPER_MISSING in st.FAIL_STATUSES

    def test_tt_pinout_valid_in_pass(self):
        assert st.TT_PINOUT_VALID in st.PASS_STATUSES

    def test_tt_pinout_invalid_in_fail(self):
        assert st.TT_PINOUT_INVALID in st.FAIL_STATUSES

    def test_tt_private_leak_in_fail(self):
        assert st.TT_PRIVATE_LEAK_DETECTED in st.FAIL_STATUSES

    def test_tt_safety_missing_in_fail(self):
        assert st.TT_SAFETY_PROPERTY_MISSING in st.FAIL_STATUSES

    def test_all_statuses_includes_tt(self):
        tt_statuses = [
            st.TINYTAPEOUT_PREP_PASS, st.TINYTAPEOUT_PREP_FAIL,
            st.TT_WRAPPER_CREATED, st.TT_WRAPPER_MISSING,
            st.TT_PINOUT_VALID, st.TT_PINOUT_INVALID,
            st.TT_INFO_YAML_CREATED, st.TT_DOCS_CREATED,
            st.TT_TESTBENCH_CREATED, st.TT_SUBMISSION_CHECK_PASS,
            st.TT_SUBMISSION_CHECK_FAIL, st.TT_PRIVATE_LEAK_DETECTED,
            st.TT_SAFETY_PROPERTY_MISSING, st.TT_READY_FOR_MANUAL_REVIEW,
            st.NEEDS_OFFICIAL_TINYTAPEOUT_CHECK,
            st.TT_EVIDENCE_PACK_CREATED,
        ]
        for s in tt_statuses:
            assert s in st.ALL_STATUSES, f"Missing status: {s}"

    def test_public_wording_exists(self):
        assert st.TINYTAPEOUT_PUBLIC_WORDING != ""
        assert "does not guarantee" in st.TINYTAPEOUT_PUBLIC_WORDING.lower()

    def test_limitation_wording_exists(self):
        assert st.TINYTAPEOUT_LIMITATION != ""
        assert "does not mean" in st.TINYTAPEOUT_LIMITATION.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Safety properties
# ══════════════════════════════════════════════════════════════════════════════

class TestSafetyProperties:
    """Tests for safety property definitions."""

    def test_at_least_5_properties(self):
        assert len(SAFETY_PROPERTIES) >= 5

    def test_kill_switch_property(self):
        assert any("kill_switch" in p for p in SAFETY_PROPERTIES)

    def test_timeout_property(self):
        assert any("timeout" in p for p in SAFETY_PROPERTIES)

    def test_reset_property(self):
        assert any("reset" in p for p in SAFETY_PROPERTIES)

    def test_verifier_property(self):
        assert any("verifier_ok" in p for p in SAFETY_PROPERTIES)

    def test_failsafe_property(self):
        assert any("FAILSAFE" in p for p in SAFETY_PROPERTIES)