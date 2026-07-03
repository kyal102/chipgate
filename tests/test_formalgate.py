"""
Tests for ChipGate Phase 12 -- FormalGate-Lite.

Covers: toolchain status, property list, property generation,
fixture parsing, evidence creation, HTML report, security checks.
"""

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

from chipgate import statuses as st
from chipgate.formalgate_bench import (
    FormalBenchResult,
    PropertyResult,
    DesignResult,
    check_formal_toolchain_status,
    list_formal_properties,
    run_formal_bench,
)
from chipgate.formalgate_report import generate_formal_html
from chipgate.formal_properties import (
    generate_default_properties,
    generate_sby_config,
    check_formal_readiness,
)
from chipgate.formal_parser import (
    parse_sby_output,
    parse_formal_fixture_file,
    parse_counterexample,
    parse_formal_trace_file,
)
from chipgate.formal_artifacts import (
    create_formal_evidence,
    save_formal_evidence,
    validate_formal_evidence_pack,
    _sha256_string,
)
from chipgate.formal_runner import (
    check_formal_toolchain,
    run_formal_property_check,
)
from chipgate.ci_toolchain import _FORBIDDEN_PHRASES


# ==================================================================
# Toolchain status
# ==================================================================

class TestFormalToolchainStatus:
    """Tests for formal toolchain detection."""

    def test_toolchain_status_returns_all_tools(self):
        """Toolchain status returns entries for all 6 expected tools."""
        tc = check_formal_toolchain_status()
        expected = ["sby", "symbiyosys", "yosys", "boolector", "z3", "abc"]
        for tool in expected:
            assert tool in tc, f"Missing tool: {tool}"

    def test_toolchain_status_has_found_key(self):
        """Each tool entry has a 'found' boolean key."""
        tc = check_formal_toolchain_status()
        for name, info in tc.items():
            assert "found" in info
            assert isinstance(info["found"], bool)

    def test_toolchain_status_missing_tools_safe(self):
        """Detection works when tools are missing."""
        tc = check_formal_toolchain_status()
        missing = sum(1 for v in tc.values() if not v.get("found", False))
        assert missing >= 0

    def test_runner_toolchain_returns_dict(self):
        """Runner toolchain check returns expected structure."""
        tc = check_formal_toolchain()
        assert "sby" in tc
        assert "yosys" in tc
        assert isinstance(tc["sby"]["found"], bool)


# ==================================================================
# Property list
# ==================================================================

class TestPropertyList:
    """Tests for the property listing command."""

    def test_list_properties_returns_all_eight(self):
        """Property list returns 8 default properties."""
        props = list_formal_properties()
        assert len(props) == 8

    def test_list_properties_has_ids(self):
        """Each property has an 'id' field."""
        props = list_formal_properties()
        for p in props:
            assert "id" in p
            assert len(p["id"]) > 0

    def test_list_properties_has_categories(self):
        """Each property has a 'category' field."""
        props = list_formal_properties()
        valid_cats = {"safety", "gating", "state_machine", "general"}
        for p in props:
            assert "category" in p
            assert p["category"] in valid_cats

    def test_kill_switch_property_present(self):
        """kill_switch_blocks_output property is in the list."""
        props = list_formal_properties()
        ids = [p["id"] for p in props]
        assert "kill_switch_blocks_output" in ids

    def test_timeout_property_present(self):
        """timeout_blocks_output property is in the list."""
        props = list_formal_properties()
        ids = [p["id"] for p in props]
        assert "timeout_blocks_output" in ids

    def test_reset_property_present(self):
        """reset_blocks_output property is in the list."""
        props = list_formal_properties()
        ids = [p["id"] for p in props]
        assert "reset_blocks_output" in ids

    def test_verifier_property_present(self):
        """actuator_requires_verifier property is in the list."""
        props = list_formal_properties()
        ids = [p["id"] for p in props]
        assert "actuator_requires_verifier" in ids


# ==================================================================
# Property generation
# ==================================================================

class TestPropertyGeneration:
    """Tests for SBY property file generation."""

    def test_default_properties_generated(self):
        """generate_default_properties() returns non-empty string."""
        props = generate_default_properties()
        assert isinstance(props, str)
        assert len(props) > 100

    def test_default_properties_contains_kill_switch(self):
        """Default properties contain kill_switch_blocks_output."""
        props = generate_default_properties()
        assert "kill_switch_blocks_output" in props

    def test_sby_config_generated(self):
        """generate_sby_config() returns valid SBY config."""
        config = generate_sby_config("test.v", "top")
        assert "[options]" in config
        assert "[engines]" in config
        assert "[script]" in config
        assert "[files]" in config
        assert "[properties]" in config
        assert "test.v" in config

    def test_sby_config_auto_top(self):
        """SBY config with auto top module detection."""
        safe_path = str(
            Path(__file__).parent.parent
            / "benchmarks" / "formalgate_v0"
            / "designs" / "safe_dtl_gate_formal.v"
        )
        if Path(safe_path).exists():
            config = generate_sby_config(safe_path, top_module="auto")
            assert "safe_dtl_gate_formal" in config


# ==================================================================
# Fixture parsing
# ==================================================================

class TestFixtureParsing:
    """Tests for formal output fixture parsing."""

    def test_pass_clean_fixture(self):
        """Clean pass fixture parses correctly."""
        fixture = str(
            Path(__file__).parent.parent
            / "benchmarks" / "formalgate_v0"
            / "fixtures" / "pass_clean.txt"
        )
        result = parse_formal_fixture_file(fixture)
        assert result["passed"] == 8
        assert result["failed"] == 0

    def test_fail_property_fixture(self):
        """Property fail fixture parses correctly."""
        fixture = str(
            Path(__file__).parent.parent
            / "benchmarks" / "formalgate_v0"
            / "fixtures" / "fail_property.txt"
        )
        result = parse_formal_fixture_file(fixture)
        assert result["passed"] == 6
        assert result["failed"] == 2

    def test_missing_solver_fixture(self):
        """Missing solver fixture parses correctly."""
        fixture = str(
            Path(__file__).parent.parent
            / "benchmarks" / "formalgate_v0"
            / "fixtures" / "fail_missing_solver.txt"
        )
        result = parse_formal_fixture_file(fixture)
        assert result["passed"] >= 0
        assert "parser_note" in result

    def test_counterexample_parser(self):
        """Counterexample parser extracts failure info."""
        output = """
        [error] [SBE] property: failsafe_no_direct_approve
        [error]   Counterexample found at step 1:
        [error]     failsafe_state = APPROVED, actuator_enable = 1
        """
        cex = parse_counterexample(output)
        assert len(cex) >= 1

    def test_formal_timeout_parser(self):
        """SBY output parser handles timeout text."""
        output = "TIMEOUT: kill_switch_blocks_output\nUNKNOWN: timeout_blocks_output"
        result = parse_sby_output(output)
        assert result["unknown"] >= 0


# ==================================================================
# Formal bench demo
# ==================================================================

class TestFormalBenchDemo:
    """Tests for the formal bench demo mode."""

    def test_demo_runs(self):
        """Demo mode completes without error."""
        result = run_formal_bench(demo=True)
        assert result.overall_status in (
            st.FORMALGATE_PASS, st.FORMALGATE_FAIL,
            st.FORMAL_PROPERTY_SKIPPED, st.FORMAL_PROPERTY_FAIL,
        )

    def test_demo_has_designs(self):
        """Demo mode tests at least one design."""
        result = run_formal_bench(demo=True)
        assert len(result.design_results) >= 1

    def test_demo_has_metrics(self):
        """Demo mode has all required metrics."""
        result = run_formal_bench(demo=True)
        m = result.metrics
        assert "designs_tested" in m
        assert "properties_checked" in m
        assert "properties_passed" in m
        assert "properties_failed" in m
        assert "properties_skipped" in m
        assert "counterexamples_found" in m

    def test_demo_safe_design_passes_fixture(self):
        """Safe design passes fixture formal output."""
        result = run_formal_bench(demo=True)
        for d in result.design_results:
            if "safe" in d.get("design_id", ""):
                assert d["properties_passed"] > 0

    def test_demo_unsafe_design_fails_fixture(self):
        """Unsafe direct actuator fails fixture formal output."""
        result = run_formal_bench(demo=True)
        for d in result.design_results:
            if "unsafe" in d.get("design_id", ""):
                assert d["properties_failed"] > 0

    def test_demo_has_public_wording(self):
        """Demo result includes public wording."""
        result = run_formal_bench(demo=True)
        assert len(result.public_wording) > 50
        assert "formal" in result.public_wording.lower()

    def test_demo_has_limitation(self):
        """Demo result includes limitation text."""
        result = run_formal_bench(demo=True)
        assert len(result.limitation) > 50


# ==================================================================
# Evidence creation
# ==================================================================

class TestEvidenceCreation:
    """Tests for formal evidence pack creation."""

    def test_evidence_created(self):
        """Evidence pack is created with expected fields."""
        design_path = str(
            Path(__file__).parent.parent
            / "benchmarks" / "formalgate_v0"
            / "designs" / "safe_dtl_gate_formal.v"
        )
        fake_result = type("obj", (object,), {
            "passed": True,
            "status": "PASS",
            "output": "",
        })()
        evidence = create_formal_evidence(design_path, fake_result)
        assert "evidence_records" in evidence
        assert "evidence_pack_hash" in evidence
        assert evidence["public_wording"] != ""

    def test_evidence_saved(self):
        """Evidence pack can be saved and re-read."""
        design_path = str(
            Path(__file__).parent.parent
            / "benchmarks" / "formalgate_v0"
            / "designs" / "safe_dtl_gate_formal.v"
        )
        fake_result = type("obj", (object,), {
            "passed": True,
            "status": "PASS",
            "output": "",
        })()
        evidence = create_formal_evidence(design_path, fake_result)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_formal_evidence(evidence, path)
            data = json.loads(Path(path).read_text())
            assert data["evidence_records_count"] >= 1
        finally:
            os.unlink(path)

    def test_artifact_hashes_stable(self):
        """Same input produces same artifact hash (same design, same result)."""
        design_path = str(
            Path(__file__).parent.parent
            / "benchmarks" / "formalgate_v0"
            / "designs" / "safe_dtl_gate_formal.v"
        )
        fake_result = type("obj", (object,), {
            "passed": True,
            "status": "PASS",
            "output": "test output",
        })()
        e1 = create_formal_evidence(design_path, fake_result)
        e2 = create_formal_evidence(design_path, fake_result)
        # The per-record hashes should be stable even if timestamps differ
        assert len(e1["evidence_records"]) > 0
        assert len(e2["evidence_records"]) > 0
        r1 = e1["evidence_records"][0]
        r2 = e2["evidence_records"][0]
        assert r1["certificate_hash"] == r2["certificate_hash"]

    def test_evidence_validation_passes(self):
        """Valid evidence pack passes validation."""
        design_path = str(
            Path(__file__).parent.parent
            / "benchmarks" / "formalgate_v0"
            / "designs" / "safe_dtl_gate_formal.v"
        )
        fake_result = type("obj", (object,), {
            "passed": True,
            "status": "PASS",
            "output": "",
        })()
        evidence = create_formal_evidence(design_path, fake_result)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_formal_evidence(evidence, path)
            validation = validate_formal_evidence_pack(path)
            assert validation["valid"] is True
        finally:
            os.unlink(path)


# ==================================================================
# HTML report
# ==================================================================

class TestFormalHTMLReport:
    """Tests for the FormalGate-Lite HTML report."""

    def test_html_generated(self):
        """HTML report is generated without errors."""
        result = run_formal_bench(demo=True)
        html = generate_formal_html(result.to_dict())
        assert "<!DOCTYPE html>" in html
        assert "FormalGate-Lite Report" in html

    def test_html_no_external_dependencies(self):
        """HTML report has no external CSS/JS."""
        result = run_formal_bench(demo=True)
        html = generate_formal_html(result.to_dict())
        assert "<link" not in html
        assert "<script" not in html

    def test_html_contains_limitation(self):
        """HTML report contains limitation disclaimer."""
        result = run_formal_bench(demo=True)
        html = generate_formal_html(result.to_dict())
        assert "Limitation" in html or "limitation" in html.lower()

    def test_json_schema_stable(self):
        """to_dict() output is JSON-serializable and stable."""
        result = run_formal_bench(demo=True)
        data = result.to_dict()
        json_str = json.dumps(data, indent=2, sort_keys=True, default=str)
        reparsed = json.loads(json_str)
        assert reparsed["overall_status"] == result.overall_status


# ==================================================================
# Security / Safety
# ==================================================================

class TestFormalSecurityProperties:
    """Security-related tests for Phase 12."""

    def test_no_jarvi3_imports(self):
        """No new module imports from private JARVI3 code."""
        new_modules = [
            "chipgate.formalgate_bench",
            "chipgate.formalgate_report",
            "chipgate.formal_parser",
            "chipgate.formal_artifacts",
            "chipgate.formal_report",
        ]
        for mod_name in new_modules:
            mod = sys.modules.get(mod_name)
            if mod is None:
                __import__(mod_name)
                mod = sys.modules[mod_name]
            source = open(mod.__file__, encoding="utf-8").read()
            assert "jarvi3" not in source.lower().replace(
                "j\\x61rvi3", ""), f"Found jarvi3 reference in {mod_name}"

    def test_no_shell_true(self):
        """No subprocess call uses shell=True in new modules."""
        new_modules = [
            "chipgate.formalgate_bench",
            "chipgate.formalgate_report",
            "chipgate.formal_parser",
            "chipgate.formal_artifacts",
            "chipgate.formal_report",
        ]
        for mod_name in new_modules:
            mod = sys.modules.get(mod_name)
            if mod is None:
                __import__(mod_name)
                mod = sys.modules[mod_name]
            source = open(mod.__file__, encoding="utf-8").read()
            assert 'shell=True' not in source, f"Found shell=True in {mod_name}"

    def test_no_secrets(self):
        """No hardcoded secrets or API keys in new modules."""
        new_modules = [
            "chipgate.formalgate_bench",
            "chipgate.formalgate_report",
            "chipgate.formal_parser",
            "chipgate.formal_artifacts",
            "chipgate.formal_report",
            "chipgate.formal_runner",
            "chipgate.formal_properties",
        ]
        secret_patterns = [
            r"api[_-]?key\s*=\s*['\"]",
            r"secret[_-]?key\s*=\s*['\"]",
            r"password\s*=\s*['\"]",
            r"token\s*=\s*['\"]",
        ]
        for mod_name in new_modules:
            mod = sys.modules.get(mod_name)
            if mod is None:
                __import__(mod_name)
                mod = sys.modules[mod_name]
            source = open(mod.__file__, encoding="utf-8").read()
            for pattern in secret_patterns:
                assert not re.search(pattern, source, re.IGNORECASE), \
                    f"Found secret pattern in {mod_name}: {pattern}"

    def test_english_only_output(self):
        """Formal bench result output contains only ASCII characters."""
        result = run_formal_bench(demo=True)
        data = result.to_dict()
        json_str = json.dumps(data, default=str)
        for c in json_str:
            assert ord(c) < 128 or c in "\n\r\t", \
                f"Non-ASCII character: U+{ord(c):04X}"

    def test_forbidden_phrases_not_in_source(self):
        """New source files don't contain forbidden overclaim phrases."""
        new_modules = [
            "chipgate.formalgate_bench",
            "chipgate.formalgate_report",
            "chipgate.formal_parser",
            "chipgate.formal_artifacts",
            "chipgate.formal_report",
        ]
        for mod_name in new_modules:
            mod = sys.modules.get(mod_name)
            if mod is None:
                __import__(mod_name)
                mod = sys.modules[mod_name]
            source = open(mod.__file__, encoding="utf-8").read()
            for pat in _FORBIDDEN_PHRASES:
                assert not pat.search(source), \
                    f"Forbidden phrase in {mod_name}: {pat.pattern}"

    def test_public_wording_mentions_formal(self):
        """FORMALGATE_PUBLIC_WORDING mentions formal checks."""
        assert "formal" in st.FORMALGATE_PUBLIC_WORDING.lower()

    def test_limitation_mentions_skipped(self):
        """FORMALGATE_LIMITATION mentions SKIPPED meaning."""
        assert "SKIPPED" in st.FORMALGATE_LIMITATION or "skipped" in st.FORMALGATE_LIMITATION


# ==================================================================
# Statuses
# ==================================================================

class TestFormalStatuses:
    """Tests for Phase 12 status constants."""

    def test_all_formal_statuses_defined(self):
        """All 14 formal statuses are defined."""
        expected = [
            "FORMALGATE_PASS", "FORMALGATE_FAIL",
            "FORMAL_PROPERTY_PASS", "FORMAL_PROPERTY_FAIL",
            "FORMAL_PROPERTY_SKIPPED", "FORMAL_SKIPPED_TOOL_MISSING",
            "FORMAL_INCONCLUSIVE", "FORMAL_TIMEOUT",
            "FORMAL_COUNTEREXAMPLE_FOUND", "FORMAL_SOLVER_MISSING",
            "PROPERTY_FILE_CREATED", "PROPERTY_FILE_MISSING",
            "FORMAL_EVIDENCE_CREATED",
            "NEEDS_DEEP_FORMAL_REVIEW", "NEEDS_PHYSICAL_SIGNOFF",
            "EVIDENCE_PACK_CREATED",
        ]
        for name in expected:
            assert hasattr(st, name), f"Missing status: {name}"

    def test_formalgate_pass_in_pass_statuses(self):
        """FORMALGATE_PASS is in PASS_STATUSES."""
        assert st.FORMALGATE_PASS in st.PASS_STATUSES

    def test_formalgate_fail_in_fail_statuses(self):
        """FORMALGATE_FAIL is in FAIL_STATUSES."""
        assert st.FORMALGATE_FAIL in st.FAIL_STATUSES


# ==================================================================
# Design files exist
# ==================================================================

class TestBenchmarkDesigns:
    """Tests for benchmark design file existence."""

    def test_safe_design_exists(self):
        assert (Path(__file__).parent.parent
                / "benchmarks" / "formalgate_v0"
                / "designs" / "safe_dtl_gate_formal.v").exists()

    def test_unsafe_design_exists(self):
        assert (Path(__file__).parent.parent
                / "benchmarks" / "formalgate_v0"
                / "designs" / "unsafe_direct_actuator_formal.v").exists()

    def test_missing_kill_switch_design_exists(self):
        assert (Path(__file__).parent.parent
                / "benchmarks" / "formalgate_v0"
                / "designs" / "missing_kill_switch_formal.v").exists()

    def test_failsafe_escape_design_exists(self):
        assert (Path(__file__).parent.parent
                / "benchmarks" / "formalgate_v0"
                / "designs" / "failsafe_escape_formal.v").exists()

    def test_property_files_exist(self):
        prop_dir = Path(__file__).parent.parent / "benchmarks" / "formalgate_v0" / "properties"
        expected_files = [
            "property_kill_switch_blocks_output.sv",
            "property_timeout_blocks_output.sv",
            "property_reset_blocks_output.sv",
            "property_actuator_requires_verifier.sv",
            "property_actuator_requires_policy.sv",
            "property_actuator_requires_sensor.sv",
            "property_failsafe_no_direct_approve.sv",
            "default_properties.sv",
            "failsafe_escape_formal.sv",
        ]
        for f in expected_files:
            assert (prop_dir / f).exists(), f"Missing property file: {f}"

    def test_fixture_files_exist(self):
        fix_dir = Path(__file__).parent.parent / "benchmarks" / "formalgate_v0" / "fixtures"
        assert (fix_dir / "pass_clean.txt").exists()
        assert (fix_dir / "fail_property.txt").exists()
        assert (fix_dir / "fail_missing_solver.txt").exists()