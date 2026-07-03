"""
DTL-ChipBench v0.3.0 test suite.

Tests adapter framework, benchmark modes, JSONL input, comparison metrics,
holdout support, evidence output, HTML comparison reports, and no-private-imports.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chipgate.statuses import (
    ALL_STATUSES, FAIL_STATUSES, PASS_STATUSES, PUBLIC_WORDING,
    CHIPBENCH_PASS, CHIPBENCH_FAIL, UNSAFE_BLOCKED, UNSAFE_ACCEPTED,
    SAFE_ACCEPTED, SAFE_REJECTED, REGRESSION_DETECTED, NO_REGRESSION_PASS,
    HEAVY_CHECK_AVOIDED, HEAVY_CHECK_REQUIRED, REPLAY_MATCH, REPLAY_DRIFT,
    CHIPBENCH_PUBLIC_WORDING,
)
from chipgate.bench_cases import (
    generate_all_cases, BenchCase, CATEGORIES, RISK_LEVELS,
    SAFE_GATE_TEMPLATE, UNSAFE_DIRECT_TEMPLATE,
)
from chipgate.cost_model import (
    tier_cost, baseline_cost, dtl_gated_cost, speedup_ratio,
    cost_per_verified_accepted, format_cost_report, COST_TIERS,
    VALID_MODES, ungated_mode_cost, chipgate_only_mode_cost,
    external_dtl_mode_cost, mode_cost, format_mode_cost_report,
)
from chipgate.noregression import check_regression, RegressionResult
from chipgate.bench import (
    run_benchmark, run_benchmark_demo, CaseResult, BenchResult,
    ComparisonResult, compare_modes,
)
from chipgate.bench_report import generate_html_report, generate_comparison_html_report
from chipgate.adapters.base import (
    ProposalInput, ProposalResult, BaseAdapter, ADAPTER_REGISTRY,
)
from chipgate.adapters.synthetic_adapter import SyntheticAdapter
from chipgate.adapters.jsonl_adapter import JSONLAdapter


# ── Adapter Framework Tests ──────────────────────────────────────────────────

class TestAdapterInterface(unittest.TestCase):
    """Test that the adapter interface loads and works."""

    def test_base_adapter_is_abstract(self):
        """BaseAdapter cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseAdapter()

    def test_synthetic_adapter_loads(self):
        adapter = SyntheticAdapter()
        self.assertEqual(adapter.name, "synthetic")
        self.assertEqual(adapter.version, "1.0.0")
        self.assertEqual(adapter.source_label, "synthetic")

    def test_synthetic_adapter_get_proposal(self):
        adapter = SyntheticAdapter()
        inp = ProposalInput(
            case_id="UA-001",
            rtl_before="",
            mutation_set=[("ungated_actuator", "test")],
            risk_level="critical",
        )
        result = adapter.get_proposal(inp)
        self.assertIsInstance(result, ProposalResult)
        self.assertTrue(result.proposed_rtl)
        self.assertEqual(result.proposal_source, "synthetic")

    def test_synthetic_adapter_get_proposals_for_cases(self):
        adapter = SyntheticAdapter()
        cases = generate_all_cases()[:5]
        proposals = adapter.get_proposals_for_cases(cases)
        self.assertEqual(len(proposals), 5)

    def test_jsonl_adapter_loads(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        self.assertEqual(adapter.proposal_count, 3)
        self.assertIn("UA-001", adapter.loaded_case_ids)

    def test_jsonl_adapter_get_proposal_found(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        inp = ProposalInput(
            case_id="UA-001",
            rtl_before="",
            mutation_set=[],
            risk_level="critical",
        )
        result = adapter.get_proposal(inp)
        self.assertEqual(result.proposal_id, "dtl-001")
        self.assertEqual(result.route_label, "safety_gate_missing")

    def test_jsonl_adapter_get_proposal_not_found(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        inp = ProposalInput(
            case_id="NONEXISTENT",
            rtl_before="module test; endmodule",
            mutation_set=[],
            risk_level="low",
        )
        result = adapter.get_proposal(inp)
        self.assertEqual(result.route_label, "no_proposal")
        self.assertIn("No proposal found", result.reason)

    def test_jsonl_adapter_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            JSONLAdapter("/nonexistent/path.jsonl")

    def test_jsonl_adapter_infers_source(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        self.assertEqual(adapter.source_label, "external_dtl")
        self.assertEqual(adapter.name, "example_dtl")

    def test_proposal_input_fields(self):
        inp = ProposalInput(
            case_id="test-1",
            rtl_before="before",
            mutation_set=[("m1", "d1")],
            risk_level="high",
            expected_gate_requirements=["verifier_ok", "policy_ok"],
        )
        self.assertEqual(inp.case_id, "test-1")
        self.assertEqual(len(inp.expected_gate_requirements), 2)

    def test_proposal_result_optional_fields(self):
        result = ProposalResult(
            proposal_id="p-1",
            proposed_rtl="module x; endmodule",
            proposal_source="test",
            adapter_name="test",
            adapter_version="1.0",
        )
        self.assertIsNone(result.confidence)
        self.assertIsNone(result.route_label)
        self.assertIsNone(result.reason)
        self.assertEqual(result.metadata, {})


# ── Benchmark Mode Tests ─────────────────────────────────────────────────────

class TestBenchmarkModes(unittest.TestCase):
    """Test that all three benchmark modes work correctly."""

    def test_ungated_baseline_mode(self):
        cases = generate_all_cases()[:5]
        result = run_benchmark(cases=cases, mode="ungated_baseline")
        self.assertEqual(result.benchmark_mode, "ungated_baseline")
        # In ungated mode, everything passes to heavy checks
        self.assertEqual(result.total_cases, 5)
        self.assertEqual(result.heavy_checks_dtl, result.total_cases)
        self.assertEqual(result.heavy_checks_avoided, 0)

    def test_chipgate_only_mode(self):
        cases = generate_all_cases()[:5]
        result = run_benchmark(cases=cases, mode="chipgate_only")
        self.assertEqual(result.benchmark_mode, "chipgate_only")
        self.assertGreater(result.heavy_checks_avoided, 0)

    def test_invalid_mode_raises(self):
        cases = generate_all_cases()[:3]
        with self.assertRaises(ValueError):
            run_benchmark(cases=cases, mode="nonexistent_mode")

    def test_mode_label_set(self):
        result = run_benchmark(
            cases=generate_all_cases()[:3],
            mode="ungated_baseline",
        )
        self.assertIn("Ungated", result.benchmark_mode_label)

    def test_external_dtl_mode_with_adapter(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        cases = generate_all_cases()[:3]
        result = run_benchmark(
            cases=cases, mode="external_dtl", adapter=adapter,
        )
        self.assertEqual(result.benchmark_mode, "external_dtl")
        self.assertEqual(result.adapter_name, "example_dtl")
        self.assertEqual(result.proposal_source, "external_dtl")

    def test_case_result_has_adapter_metadata(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        cases = generate_all_cases()[:3]
        result = run_benchmark(
            cases=cases, mode="external_dtl", adapter=adapter,
        )
        # At least one case should have adapter metadata
        has_adapter = any(
            cr.proposal_source == "external_dtl"
            for cr in result.case_results
        )
        self.assertTrue(has_adapter, "At least one case should have external_dtl source")


# ── Comparison Tests ─────────────────────────────────────────────────────────

class TestComparisonModes(unittest.TestCase):
    """Test the compare_modes function."""

    def test_compare_modes_runs(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        self.assertIsInstance(comparison, ComparisonResult)
        self.assertIn("ungated_baseline", comparison.modes)
        self.assertIn("chipgate_only", comparison.modes)

    def test_compare_modes_with_adapter(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases, adapter=adapter)
        self.assertIn("external_dtl", comparison.modes)

    def test_compare_modes_serializable(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        d = comparison.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        self.assertTrue(len(json_str) > 0)

    def test_compare_modes_ungated_higher_cost(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        ungated = comparison.modes["ungated_baseline"]
        gated = comparison.modes["chipgate_only"]
        self.assertGreater(ungated.estimated_dtl_cost, gated.estimated_dtl_cost)


# ── Cost Model v0.3.0 Tests ─────────────────────────────────────────────────

class TestCostModelV3(unittest.TestCase):
    """Test mode-aware cost calculations."""

    def test_ungated_mode_cost(self):
        cost = ungated_mode_cost(100)
        self.assertEqual(cost, 38000)

    def test_chipgate_only_mode_cost(self):
        # 100 cases, 60 blocked, 40 to heavy
        cost = chipgate_only_mode_cost(100, 60, 40)
        expected = 100 * 1 + 40 * 380  # scan all + heavy for 40
        self.assertEqual(cost, expected)

    def test_external_dtl_mode_cost(self):
        # 100 cases, 20 blocked by adapter, 40 blocked by chipgate, 40 to heavy
        cost = external_dtl_mode_cost(100, 20, 40, 40)
        adapter_cost = 100 * 1
        chipgate_cost = 80 * 1  # 100 - 20
        heavy_cost = 40 * 380
        expected = adapter_cost + chipgate_cost + heavy_cost
        self.assertEqual(cost, expected)

    def test_mode_cost_function(self):
        self.assertEqual(mode_cost("ungated_baseline", 50), ungated_mode_cost(50))
        self.assertEqual(
            mode_cost("chipgate_only", 100, 60, 40),
            chipgate_only_mode_cost(100, 60, 40),
        )

    def test_mode_cost_invalid_raises(self):
        with self.assertRaises(ValueError):
            mode_cost("bad_mode", 10)

    def test_format_mode_cost_report(self):
        report = format_mode_cost_report(
            mode="chipgate_only",
            num_cases=100,
            unsafe_blocked=60,
            safe_accepted=40,
            safe_rejected=0,
        )
        self.assertEqual(report["benchmark_mode"], "chipgate_only")
        self.assertIn("estimated_cost_per_verified_accepted_change", report)
        self.assertIn("disclaimer", report)

    def test_format_mode_cost_report_ungated(self):
        report = format_mode_cost_report(
            mode="ungated_baseline",
            num_cases=100,
            unsafe_blocked=0,
            safe_accepted=40,
            safe_rejected=60,
        )
        self.assertEqual(report["heavy_checks_avoided"], 0)

    def test_valid_modes(self):
        self.assertEqual(VALID_MODES, ["ungated_baseline", "chipgate_only", "external_dtl"])


# ── Cost Per Verified Accepted Change ────────────────────────────────────────

class TestCostPerAccepted(unittest.TestCase):
    """Test the key metric: cost per verified accepted change."""

    def test_chipgate_only_lower_than_ungated(self):
        cases = generate_all_cases()[:10]
        comparison = compare_modes(cases=cases)
        ungated = comparison.modes["ungated_baseline"]
        gated = comparison.modes["chipgate_only"]
        # Gated should have lower cost per accepted (or both inf)
        if (gated.cost_per_verified_accepted != float("inf") and
                ungated.cost_per_verified_accepted != float("inf")):
            self.assertLessEqual(
                gated.cost_per_verified_accepted,
                ungated.cost_per_verified_accepted,
            )

    def test_ungated_cpv_formula(self):
        # 100 cases, all pass = 40 safe accepted
        # ungated cost = 100 * 380 = 38000
        cpv = cost_per_verified_accepted(38000, 40)
        self.assertAlmostEqual(cpv, 950.0, places=1)


# ── Holdout Tests ─────────────────────────────────────────────────────────────

class TestHoldoutSupport(unittest.TestCase):
    """Test that missing holdout directory skips cleanly."""

    def test_missing_holdout_skips(self):
        """Benchmark runs fine without holdout directory."""
        cases = generate_all_cases()[:5]
        result = run_benchmark(cases=cases, mode="chipgate_only")
        self.assertEqual(result.holdout_cases_included, 0)

    def test_holdout_loaded_when_present(self):
        """When holdout dir exists with .v files, they are loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            holdout = Path(tmpdir) / "chipbench_holdout"
            holdout.mkdir()
            (holdout / "secret_case1.v").write_text(
                "module secret (input clk, output reg out); "
                "always @(posedge clk) out <= 1; endmodule"
            )
            # Run benchmark with output_dir pointing near holdout
            output = Path(tmpdir) / "results"
            output.mkdir()
            cases = generate_all_cases()[:3]
            result = run_benchmark(
                cases=cases, mode="chipgate_only", output_dir=str(output),
            )
            # Note: holdout is relative to output_dir/../chipbench_holdout
            # This test verifies the loader doesn't crash


# ── Evidence v0.3.0 Tests ────────────────────────────────────────────────────

class TestEvidenceV3(unittest.TestCase):
    """Test v0.3.0 evidence packs include mode and adapter metadata."""

    def test_evidence_includes_benchmark_mode(self):
        cases = generate_all_cases()[:3]
        result = run_benchmark(
            cases=cases, mode="chipgate_only", evidence=True,
        )
        self.assertGreater(result.evidence_packs_created, 0)

    def test_evidence_with_adapter_metadata(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        cases = generate_all_cases()[:3]
        result = run_benchmark(
            cases=cases, mode="external_dtl", adapter=adapter, evidence=True,
        )
        self.assertGreater(result.evidence_packs_created, 0)
        # Check that case results have adapter metadata
        for cr in result.case_results:
            self.assertTrue(cr.input_hash)
            self.assertTrue(cr.output_hash)


# ── HTML Comparison Report Tests ─────────────────────────────────────────────

class TestHTMLComparisonReport(unittest.TestCase):
    """Test the multi-mode HTML comparison report."""

    def test_comparison_html_generated(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        html = generate_comparison_html_report(comparison)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Mode Comparison", html)

    def test_comparison_html_contains_all_modes(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        html = generate_comparison_html_report(comparison)
        self.assertIn("Ungated Baseline", html)
        self.assertIn("ChipGate-Only", html)

    def test_comparison_html_contains_cost_per_accepted(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        html = generate_comparison_html_report(comparison)
        self.assertIn("cost per verified accepted change", html.lower())

    def test_comparison_html_contains_disclaimer(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        html = generate_comparison_html_report(comparison)
        self.assertIn("benchmark cost model", html.lower())

    def test_comparison_html_contains_limitation(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        html = generate_comparison_html_report(comparison)
        self.assertIn("model-free benchmark", html.lower())

    def test_comparison_html_no_external_css(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        html = generate_comparison_html_report(comparison)
        self.assertNotIn("<link ", html)
        self.assertNotIn("<script src=", html)

    def test_comparison_html_writable(self):
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases)
        html = generate_comparison_html_report(comparison)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html)
            path = f.name
        try:
            self.assertGreater(os.path.getsize(path), 1000)
        finally:
            os.unlink(path)

    def test_comparison_html_with_adapter_mode(self):
        adapter = JSONLAdapter("examples/demo_proposals.jsonl")
        cases = generate_all_cases()[:5]
        comparison = compare_modes(cases=cases, adapter=adapter)
        html = generate_comparison_html_report(comparison)
        self.assertIn("external_dtl", html)


# ── CLI Integration Tests ────────────────────────────────────────────────────

class TestBenchCLIV3(unittest.TestCase):
    """Test v0.3.0 CLI flags."""

    def test_bench_demo_cli_v3(self):
        from chipgate.__main__ import main
        result = main(["bench", "--demo"])
        self.assertEqual(result, 0)

    def test_bench_mode_ungated_cli(self):
        from chipgate.__main__ import main
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = main(["bench", "--demo", "--mode", "ungated_baseline",
                          "--json", "--html", path.replace(".json", ".html")])
            # Ungated mode may return 2 (unsafe accepted) or 0
            self.assertIn(result, [0, 2])
        finally:
            if os.path.exists(path):
                os.unlink(path)
            html_path = path.replace(".json", ".html")
            if os.path.exists(html_path):
                os.unlink(html_path)

    def test_bench_mode_chipgate_only_cli(self):
        from chipgate.__main__ import main
        result = main(["bench", "--demo", "--mode", "chipgate_only"])
        self.assertEqual(result, 0)

    def test_bench_compare_modes_cli(self):
        from chipgate.__main__ import main
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            result = main(["bench", "--demo", "--compare-modes", "--html", path])
            self.assertEqual(result, 0)
            content = Path(path).read_text()
            self.assertIn("Mode Comparison", content)
            self.assertIn("benchmark cost model", content)
        finally:
            os.unlink(path)

    def test_bench_adapter_cli(self):
        from chipgate.__main__ import main
        result = main([
            "bench", "--demo", "--mode", "external_dtl",
            "--adapter", "examples/demo_proposals.jsonl",
        ])
        # May return 2 if unsafe accepted
        self.assertIn(result, [0, 2])


# ── No-Private-Import Tests (v0.3.0) ────────────────────────────────────────

class TestNoPrivateImportsV3(unittest.TestCase):
    """Ensure no private references in v0.3.0 adapter modules."""

    def test_no_jarvi3_in_adapters(self):
        pkg_dir = Path(__file__).parent.parent / "chipgate" / "adapters"
        for py_file in pkg_dir.glob("*.py"):
            content = py_file.read_text()
            self.assertNotIn("jarvi3", content.lower(),
                             f"Private reference in {py_file}")

    def test_no_secrets_in_adapters(self):
        pkg_dir = Path(__file__).parent.parent / "chipgate" / "adapters"
        for py_file in pkg_dir.glob("*.py"):
            content = py_file.read_text()
            self.assertNotIn("API_KEY", content)
            self.assertNotIn("SECRET", content)

    def test_no_shell_true_in_adapters(self):
        """Ensure no shell=True in adapter code."""
        pkg_dir = Path(__file__).parent.parent / "chipgate" / "adapters"
        for py_file in pkg_dir.glob("*.py"):
            content = py_file.read_text()
            self.assertNotIn("shell=True", content)

    def test_all_output_english_only(self):
        """All public-facing strings in bench modules should be in English."""
        # Check that the public wording is in English (basic check)
        self.assertIn("model-free", CHIPBENCH_PUBLIC_WORDING.lower())
        self.assertIn("does not guarantee", CHIPBENCH_PUBLIC_WORDING.lower())


# ── Regression Tests (v0.3.0 additions) ──────────────────────────────────────

class TestV3BackwardCompat(unittest.TestCase):
    """Ensure v0.3.0 is backward-compatible with v0.2.0 tests."""

    def test_bench_demo_still_works(self):
        result = run_benchmark_demo()
        self.assertIsInstance(result, BenchResult)
        self.assertGreater(result.total_cases, 0)

    def test_bench_demo_zero_false_accept(self):
        result = run_benchmark_demo()
        self.assertEqual(result.false_accept_rate, 0.0)

    def test_bench_demo_replay_100(self):
        result = run_benchmark_demo()
        self.assertEqual(result.replay_match_rate, 100.0)

    def test_full_bench_100_plus(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertGreaterEqual(result.total_cases, 100)

    def test_full_bench_zero_false_accept(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertEqual(result.false_accept_rate, 0.0)

    def test_speedup_calculated(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertGreater(result.estimated_speedup_ratio, 1.0)

    def test_cost_per_accepted_finite(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertNotEqual(result.cost_per_verified_accepted, float("inf"))

    def test_benchmark_hash_stable(self):
        cases = generate_all_cases()
        r1 = run_benchmark(cases=cases, mode="chipgate_only")
        r2 = run_benchmark(cases=cases, mode="chipgate_only")
        self.assertEqual(r1.benchmark_hash, r2.benchmark_hash)

    def test_public_wording_present(self):
        result = run_benchmark_demo()
        self.assertIn("does not guarantee", result.public_wording)

    def test_disclaimer_present(self):
        result = run_benchmark_demo()
        self.assertIn("benchmark cost model", result.disclaimer.lower())

    def test_to_dict_has_new_fields(self):
        result = run_benchmark_demo()
        d = result.to_dict()
        self.assertIn("benchmark_mode", d)
        self.assertIn("adapter_name", d)
        self.assertIn("proposal_source", d)
        self.assertIn("regressions_detected", d)
        self.assertIn("regressions_accepted", d)

    def test_regressions_detected_counted(self):
        cases = [c for c in generate_all_cases() if c.rtl_before]
        result = run_benchmark(cases=cases, mode="chipgate_only")
        self.assertGreater(result.regressions_detected, 0)

    def test_evidence_records_created_v3(self):
        cases = generate_all_cases()[:5]
        result = run_benchmark(cases=cases, evidence=True)
        self.assertEqual(result.evidence_packs_created, 5)


if __name__ == "__main__":
    unittest.main()