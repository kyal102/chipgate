"""
Tests for ChipGate Phase 10 — OpenLanePhysicalBench.

Covers: toolchain status, preflight safety, config validation,
DRC/LVS/timing parsing, GDS hashing, artifact stability,
evidence records, HTML report, no private imports, no shell=True,
English-only output.
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
from chipgate.drc_lvs_parser import parse_drc_report, parse_lvs_report
from chipgate.timing_report_parser import parse_timing_report, parse_area_stats
from chipgate.gds_artifacts import (
    hash_all_artifacts, hash_content, hash_file, GDSHashResult,
)
from chipgate.openroad_reports import (
    parse_fixtures_directory, parse_single_drc, parse_single_lvs, parse_single_timing,
)
from chipgate.physical_score import (
    PhysicalMetrics, compute_toolchain_coverage, compute_metrics_from_results,
)
from chipgate.openlane_physical import (
    run_physical_bench, check_toolchain_status,
    _preflight_safety, _check_openlane_config,
)
from chipgate.physical_report import generate_physical_html


# ── Fixture paths ─────────────────────────────────────────────────────────────

FIXTURES_DIR = str(
    Path(__file__).parent.parent
    / "benchmarks" / "openlanephysical_v0" / "fixtures"
)


# ══════════════════════════════════════════════════════════════════════════════
# Toolchain Status
# ══════════════════════════════════════════════════════════════════════════════

class TestToolchainStatus:
    """Tests for OpenLane/OpenROAD toolchain detection."""

    def test_toolchain_status_returns_all_tools(self):
        """Toolchain status returns entries for all 7 expected tools."""
        tc = check_toolchain_status()
        expected = ["OpenLane", "OpenROAD", "Yosys", "Magic", "Netgen", "KLayout", "STA"]
        for tool in expected:
            assert tool in tc, f"Missing tool: {tool}"

    def test_toolchain_status_has_found_key(self):
        """Each tool entry has a 'found' boolean key."""
        tc = check_toolchain_status()
        for name, info in tc.items():
            assert "found" in info, f"Missing 'found' for {name}"
            assert isinstance(info["found"], bool)

    def test_toolchain_works_when_tools_missing(self):
        """Toolchain detection works even when no tools are installed."""
        tc = check_toolchain_status()
        # Should not raise; may have 0 found
        found_count = sum(1 for i in tc.values() if i["found"])
        assert found_count >= 0


# ══════════════════════════════════════════════════════════════════════════════
# Preflight Safety
# ══════════════════════════════════════════════════════════════════════════════

class TestPreflightSafety:
    """Tests for preflight safety checks."""

    SAFE_V = """
    module safe_gate(input clk, input kill_switch, input timeout, input reset,
        input verifier_ok, input policy_ok, input sensor_ok,
        output actuator_enable);
        assign actuator_enable = ai_output & verifier_ok & policy_ok & sensor_ok & ~timeout & ~kill_switch & ~reset;
    endmodule
    """

    UNSAFE_V = """
    module unsafe_gate(input clk, input ai_output, output actuator_enable);
        assign actuator_enable = ai_output;
    endmodule
    """

    PRIVATE_V = """
    module leaky(input clk, output actuator_enable);
        // This references jarvi3 internal
        assign actuator_enable = 1;
    endmodule
    """

    def test_safe_design_passes_preflight(self):
        """A design with safety signals passes preflight."""
        passed, status = _preflight_safety(self.SAFE_V)
        assert passed is True
        assert status == st.SAFETY_GATE_PRESENT

    def test_unsafe_design_blocked(self):
        """A design without safety gating is blocked."""
        passed, status = _preflight_safety(self.UNSAFE_V)
        assert passed is False

    def test_private_name_detected(self):
        """A design with 'jarvi3' triggers private leak detection."""
        passed, status = _preflight_safety(self.PRIVATE_V)
        assert passed is False
        assert status == st.TT_PRIVATE_LEAK_DETECTED


# ══════════════════════════════════════════════════════════════════════════════
# OpenLane Config
# ══════════════════════════════════════════════════════════════════════════════

class TestOpenLaneConfig:
    """Tests for OpenLane config validation."""

    VALID_CONFIG = json.dumps({
        "DESIGN_NAME": "test_gate",
        "VERILOG_FILES": ["src/test.v"],
        "CLOCK_PERIOD": 10.0,
    })

    BAD_CONFIG_NO_TOP = json.dumps({
        "DESIGN_NAME": "",
        "VERILOG_FILES": [],
    })

    BAD_CONFIG_PRIVATE = json.dumps({
        "DESIGN_NAME": "test",
        "PRIVATE_DTL_INTERNAL": True,
    })

    def test_valid_config_passes(self):
        """A valid config with top module passes."""
        ok, issues = _check_openlane_config("module test_gate(input clk); endmodule",
                                             self.VALID_CONFIG, "test_gate")
        assert ok is True
        assert issues == []

    def test_empty_verilog_fails(self):
        """Empty Verilog source fails config check."""
        ok, issues = _check_openlane_config("",
                                             self.VALID_CONFIG, "")
        assert ok is False
        assert any("empty" in i.lower() for i in issues)

    def test_private_name_in_config_fails(self):
        """Config with PRIVATE_DTL triggers failure."""
        ok, issues = _check_openlane_config("module x(input clk); endmodule",
                                             self.BAD_CONFIG_PRIVATE, "x")
        assert ok is False
        assert any("private" in i.lower() or "PRIVATE_DTL" in i for i in issues)


# ══════════════════════════════════════════════════════════════════════════════
# DRC Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestDRCParser:
    """Tests for DRC report parsing."""

    def test_drc_clean_parsed(self):
        """Clean DRC report gives 0 violations."""
        text = "Magic DRC Report\nTotal DRC errors: 0\nDesign is DRC CLEAN."
        result = parse_drc_report(text, "drc_clean.rpt")
        assert result.clean is True
        assert result.violation_count == 0

    def test_drc_violations_parsed(self):
        """DRC report with violations counted correctly."""
        text = "Magic DRC Report\nTotal DRC violations: 3\nviolation: metal1 spacing\nviolation: via1 enclosure\nerror: metal2 width"
        result = parse_drc_report(text, "drc_violations.rpt")
        assert result.clean is False
        assert result.violation_count == 3

    def test_drc_keyword_clean(self):
        """DRC report with 'DRC CLEAN' keyword detected."""
        text = "Flow complete. DRC CLEAN. No issues."
        result = parse_drc_report(text)
        assert result.clean is True

    def test_drc_fixture_file_stable(self):
        """Parsing the drc_clean.rpt fixture gives stable results."""
        path = Path(FIXTURES_DIR) / "drc_clean.rpt"
        if not path.exists():
            pytest.skip("Fixture not available")
        text = path.read_text(encoding="utf-8")
        result = parse_drc_report(text, str(path))
        assert result.clean is True
        assert result.violation_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# LVS Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestLVSParser:
    """Tests for LVS report parsing."""

    def test_lvs_clean_parsed(self):
        """Clean LVS report gives clean status."""
        text = "Netgen LVS Report\nNetlists match perfectly.\nLVS: PASS"
        result = parse_lvs_report(text, "lvs_clean.rpt")
        assert result.clean is True
        assert result.mismatch_count == 0

    def test_lvs_mismatch_parsed(self):
        """LVS report with mismatch detected."""
        text = "Netgen LVS Report\nNetlists do not match.\nmismatch: Device count mismatch\nerror: Pin mismatch"
        result = parse_lvs_report(text, "lvs_mismatch.rpt")
        assert result.clean is False
        assert result.mismatch_count >= 1

    def test_lvs_fixture_stable(self):
        """Parsing the lvs_clean.rpt fixture gives stable results."""
        path = Path(FIXTURES_DIR) / "lvs_clean.rpt"
        if not path.exists():
            pytest.skip("Fixture not available")
        text = path.read_text(encoding="utf-8")
        result = parse_lvs_report(text, str(path))
        assert result.clean is True


# ══════════════════════════════════════════════════════════════════════════════
# Timing Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestTimingParser:
    """Tests for timing report parsing."""

    def test_timing_pass_parsed(self):
        """Timing pass report detected correctly."""
        text = "slack (MET) 2.35 ns\nWNS: 2.35 ns"
        result = parse_timing_report(text, "timing_pass.rpt")
        assert result.pass_status is True

    def test_timing_fail_parsed(self):
        """Timing fail report detected correctly."""
        text = "slack (VIOLATED) -0.45 ns\nWNS: -0.45 ns"
        result = parse_timing_report(text, "timing_fail.rpt")
        assert result.pass_status is False
        assert result.worst_negative_slack == -0.45

    def test_timing_fixture_stable(self):
        """Parsing the timing_pass.rpt fixture gives stable results."""
        path = Path(FIXTURES_DIR) / "timing_pass.rpt"
        if not path.exists():
            pytest.skip("Fixture not available")
        text = path.read_text(encoding="utf-8")
        result = parse_timing_report(text, str(path))
        assert result.pass_status is True

    def test_area_stats_parsed(self):
        """Area stats report extracts cell count and area."""
        text = "Cell count: 24\nDie area: 100x100 um\nCore area: 80x80 um\nUtilization: 12.5%"
        stats = parse_area_stats(text, "area_stats.rpt")
        assert stats["cell_count"] == 24
        assert stats["die_area_um2"] == 10000.0
        assert stats["utilization_pct"] == 12.5


# ══════════════════════════════════════════════════════════════════════════════
# GDS Artifacts
# ══════════════════════════════════════════════════════════════════════════════

class TestGDSArtifacts:
    """Tests for GDS artifact hashing."""

    def test_gds_missing_classified_safely(self):
        """When no GDS file exists, result shows gds_found=False."""
        result = hash_all_artifacts(rtl_content="module test; endmodule")
        assert result.gds_found is False
        assert result.total_hash_count >= 1  # RTL should still be hashed

    def test_gds_hash_created_when_fixture_exists(self):
        """When a GDS file is provided, it gets hashed."""
        with tempfile.NamedTemporaryFile(suffix=".gds", delete=False) as f:
            f.write(b"FAKE_GDS_DATA_FOR_TESTING")
            name = f.name
        # File must be closed before hashing/unlinking: Windows locks open files.
        try:
            result = hash_all_artifacts(
                rtl_content="module test; endmodule",
                gds_path=name,
            )
            assert result.gds_found is True
            assert result.gds_hash != ""
        finally:
            os.unlink(name)

    def test_artifact_hashes_stable(self):
        """Same content produces same hash (deterministic)."""
        content = "module stable; endmodule"
        h1 = hash_content("rtl", content)
        h2 = hash_content("rtl", content)
        assert h1.sha256 == h2.sha256


# ══════════════════════════════════════════════════════════════════════════════
# Evidence Record & Full Demo
# ══════════════════════════════════════════════════════════════════════════════

class TestEvidenceAndDemo:
    """Tests for evidence records and full demo run."""

    def test_evidence_record_created(self):
        """Running demo creates evidence records for each design."""
        result = run_physical_bench(demo=True)
        assert len(result.design_results) >= 1
        for d in result.design_results:
            assert "evidence_record" in d
            assert d["evidence_record"].get("created", False) is True

    def test_evidence_has_artifact_hashes(self):
        """Evidence record contains artifact hashes for safe designs."""
        result = run_physical_bench(demo=True)
        safe = [d for d in result.design_results
                if d.get("design_id", "").startswith("tiny_dtl")]
        if safe:
            ev = safe[0].get("evidence_record", {})
            hashes = ev.get("artifact_hashes", [])
            assert len(hashes) >= 1

    def test_evidence_has_replay_command(self):
        """Evidence record contains a replay command."""
        result = run_physical_bench(demo=True)
        for d in result.design_results:
            ev = d.get("evidence_record", {})
            assert "replay_command" in ev
            assert "chipgate physical" in ev["replay_command"]

    def test_safe_design_overall_pass(self):
        """The safe demo design passes overall."""
        result = run_physical_bench(demo=True)
        safe = [d for d in result.design_results
                if d.get("design_id", "").startswith("tiny_dtl")]
        if safe:
            assert safe[0]["overall_status"] == st.PHYSICAL_BENCH_PASS

    def test_unsafe_design_overall_fail(self):
        """The unsafe demo design fails overall."""
        result = run_physical_bench(demo=True)
        unsafe = [d for d in result.design_results
                  if "unsafe" in d.get("design_id", "")]
        if unsafe:
            assert unsafe[0]["overall_status"] == st.PHYSICAL_BENCH_FAIL

    def test_evidence_has_public_wording(self):
        """Evidence records include public wording disclaimer."""
        result = run_physical_bench(demo=True)
        for d in result.design_results:
            ev = d.get("evidence_record", {})
            assert "public_wording" in ev
            assert len(ev["public_wording"]) > 20


# ══════════════════════════════════════════════════════════════════════════════
# HTML Report
# ══════════════════════════════════════════════════════════════════════════════

class TestHTMLReport:
    """Tests for HTML report generation."""

    def test_html_report_generated(self):
        """HTML report is generated without errors."""
        result = run_physical_bench(demo=True)
        html = generate_physical_html(result.to_dict())
        assert "<!DOCTYPE html>" in html
        assert "OpenLanePhysicalBench" in html

    def test_html_contains_limitations(self):
        """HTML report contains limitations disclaimer."""
        result = run_physical_bench(demo=True)
        html = generate_physical_html(result.to_dict())
        assert "does not prove" in html.lower() or "Limitation" in html

    def test_html_no_external_dependencies(self):
        """HTML report has no external CSS/JS dependencies."""
        result = run_physical_bench(demo=True)
        html = generate_physical_html(result.to_dict())
        assert "<link" not in html  # no external stylesheets
        assert "<script" not in html  # no javascript

    def test_json_schema_stable(self):
        """to_dict() output is JSON-serializable and stable."""
        result = run_physical_bench(demo=True)
        data = result.to_dict()
        json_str = json.dumps(data, indent=2, sort_keys=True, default=str)
        # Re-parse to verify
        reparsed = json.loads(json_str)
        assert reparsed["benchmark_name"] == "OpenLanePhysicalBench"
        assert "design_results" in reparsed


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures Directory Parsing
# ══════════════════════════════════════════════════════════════════════════════

class TestFixturesParsing:
    """Tests for parse-fixtures-directory mode."""

    def test_parse_fixtures_directory(self):
        """Parsing the fixtures dir finds reports."""
        if not Path(FIXTURES_DIR).is_dir():
            pytest.skip("Fixtures directory not available")
        parsed = parse_fixtures_directory(FIXTURES_DIR)
        assert parsed.parsed_count >= 4  # At least drc, lvs, timing, area

    def test_parse_nonexistent_dir(self):
        """Parsing a non-existent directory returns gracefully."""
        parsed = parse_fixtures_directory("/nonexistent/path/12345")
        assert parsed.parsed_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# Safety / Security
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityProperties:
    """Security-related tests for Phase 10."""

    def test_no_jarvi3_imports(self):
        """No module imports from private JARVI3 code."""
        # Check all new modules
        new_modules = [
            "chipgate.openlane_physical",
            "chipgate.drc_lvs_parser",
            "chipgate.timing_report_parser",
            "chipgate.gds_artifacts",
            "chipgate.openroad_reports",
            "chipgate.physical_score",
            "chipgate.physical_report",
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
        """No subprocess call uses shell=True."""
        new_modules = [
            "chipgate.openlane_physical",
            "chipgate.drc_lvs_parser",
            "chipgate.timing_report_parser",
            "chipgate.gds_artifacts",
            "chipgate.openroad_reports",
            "chipgate.physical_score",
            "chipgate.physical_report",
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
            "chipgate.openlane_physical",
            "chipgate.drc_lvs_parser",
            "chipgate.timing_report_parser",
            "chipgate.gds_artifacts",
            "chipgate.openroad_reports",
            "chipgate.physical_score",
            "chipgate.physical_report",
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
        """Demo output contains only ASCII/English characters."""
        result = run_physical_bench(demo=True)
        data = result.to_dict()
        json_str = json.dumps(data, default=str)
        # Check for non-ASCII (CJK, etc.) in status/message fields
        for d in data.get("design_results", []):
            for key, value in d.items():
                if isinstance(value, str):
                    assert all(ord(c) < 128 or c in "\n\r\t" for c in value), \
                        f"Non-ASCII in design_result[{key}]"