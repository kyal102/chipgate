"""
DTL-ChipBench test suite.

Tests all benchmark functionality, case generation, cost model,
no-regression checking, HTML report, and CLI integration.
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
)
from chipgate.noregression import check_regression, RegressionResult
from chipgate.bench import (
    run_benchmark, run_benchmark_demo, CaseResult, BenchResult,
)
from chipgate.bench_report import generate_html_report


class TestBenchCasesGenerated(unittest.TestCase):
    """Test that benchmark cases are generated correctly."""

    def test_100_plus_cases_exist(self):
        cases = generate_all_cases()
        self.assertGreaterEqual(len(cases), 100)

    def test_all_cases_have_required_fields(self):
        cases = generate_all_cases()
        for c in cases:
            self.assertTrue(c.case_id)
            self.assertTrue(c.category)
            self.assertTrue(c.risk_level)
            self.assertTrue(c.rtl_after)
            self.assertIn(c.expected_gate_result, ("block", "pass"))
            self.assertIsInstance(c.expected_heavy_check_needed, bool)
            self.assertTrue(c.reason)

    def test_all_categories_present(self):
        cases = generate_all_cases()
        found = {c.category for c in cases}
        for cat in CATEGORIES:
            self.assertIn(cat, found, f"Missing category: {cat}")

    def test_all_risk_levels_valid(self):
        cases = generate_all_cases()
        for c in cases:
            self.assertIn(c.risk_level, RISK_LEVELS)

    def test_case_ids_unique(self):
        cases = generate_all_cases()
        ids = [c.case_id for c in cases]
        self.assertEqual(len(ids), len(set(ids)))

    def test_unsafe_cases_expect_block(self):
        cases = generate_all_cases()
        unsafe_cats = {"ungated_actuator", "missing_verifier_ok", "missing_policy_ok",
                        "missing_kill_switch", "timeout_bypass", "unsafe_direct_ai",
                        "missing_reset", "false_negative_trap"}
        for c in cases:
            if c.category in unsafe_cats:
                self.assertEqual(c.expected_gate_result, "block",
                                 f"{c.case_id} ({c.category}) should expect block")

    def test_safe_cases_expect_pass(self):
        cases = generate_all_cases()
        safe_cats = {"safe_dtl_gate", "safe_fsm_dtl_gate", "false_positive_trap"}
        for c in cases:
            if c.category in safe_cats:
                self.assertEqual(c.expected_gate_result, "pass",
                                 f"{c.case_id} ({c.category}) should expect pass")


class TestCostModel(unittest.TestCase):
    """Test the transparent cost model."""

    def test_tier_costs_defined(self):
        self.assertEqual(tier_cost("dtl_scan"), 1)
        self.assertEqual(tier_cost("lint"), 5)
        self.assertEqual(tier_cost("simulation"), 25)
        self.assertEqual(tier_cost("formal"), 100)
        self.assertEqual(tier_cost("synthesis"), 250)

    def test_unknown_tier_raises(self):
        with self.assertRaises(ValueError):
            tier_cost("nonexistent")

    def test_baseline_cost(self):
        # 100 cases x (5+25+100+250) = 38000
        self.assertEqual(baseline_cost(100), 38000)

    def test_dtl_gated_cost_all_blocked(self):
        # All blocked: 100 x 1 (scan only) = 100
        self.assertEqual(dtl_gated_cost(0, 100), 100)

    def test_dtl_gated_cost_all_pass(self):
        # All pass: 100 x 1 (scan) + 100 x 380 (heavy) = 38100
        self.assertEqual(dtl_gated_cost(100, 0), 38100)

    def test_dtl_gated_cost_mixed(self):
        # 40 pass, 60 blocked
        cost = dtl_gated_cost(40, 60)
        expected = 100 * 1 + 40 * 380  # all get scan, 40 get heavy
        self.assertEqual(cost, expected)

    def test_speedup_ratio(self):
        self.assertAlmostEqual(speedup_ratio(38000, 19000), 2.0, places=2)

    def test_speedup_zero_division(self):
        self.assertEqual(speedup_ratio(100, 0), 0.0)

    def test_cost_per_accepted(self):
        self.assertAlmostEqual(cost_per_verified_accepted(19000, 40), 475.0, places=1)

    def test_cost_per_accepted_zero(self):
        self.assertEqual(cost_per_verified_accepted(100, 0), float("inf"))

    def test_format_cost_report(self):
        report = format_cost_report(100, 60, 40, 40)
        self.assertIn("total_cases", report)
        self.assertIn("speedup_ratio", report)
        self.assertIn("disclaimer", report)
        self.assertIn("cost units", report["disclaimer"])


class TestNoRegression(unittest.TestCase):
    """Test the no-regression checker."""

    def test_safe_to_unsafe_is_regression(self):
        safe = SAFE_GATE_TEMPLATE.format(name="base")
        unsafe = UNSAFE_DIRECT_TEMPLATE.format(name="proposed")
        result = check_regression(safe, unsafe, "test_rg")
        self.assertTrue(result.is_regression)
        self.assertEqual(result.status, REGRESSION_DETECTED)

    def test_safe_to_safe_no_regression(self):
        safe1 = SAFE_GATE_TEMPLATE.format(name="base")
        safe2 = SAFE_GATE_TEMPLATE.format(name="proposed")
        result = check_regression(safe1, safe2, "test_nr")
        self.assertFalse(result.is_regression)
        self.assertEqual(result.status, NO_REGRESSION_PASS)

    def test_unsafe_to_safe_improvement(self):
        unsafe = UNSAFE_DIRECT_TEMPLATE.format(name="base")
        safe = SAFE_GATE_TEMPLATE.format(name="proposed")
        result = check_regression(unsafe, safe, "test_imp")
        self.assertFalse(result.is_regression)
        self.assertIn("Improvement", result.detail)


class TestBenchRunner(unittest.TestCase):
    """Test the benchmark runner."""

    def test_demo_runs(self):
        result = run_benchmark_demo()
        self.assertIsInstance(result, BenchResult)
        self.assertGreater(result.total_cases, 0)

    def test_demo_zero_false_accept(self):
        result = run_benchmark_demo()
        self.assertEqual(result.false_accept_rate, 0.0)

    def test_demo_replay_100(self):
        result = run_benchmark_demo()
        self.assertEqual(result.replay_match_rate, 100.0)

    def test_full_bench_runs(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertGreaterEqual(result.total_cases, 100)

    def test_full_bench_zero_false_accept(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertEqual(result.false_accept_rate, 0.0)

    def test_full_bench_unsafe_blocked(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertGreater(result.unsafe_blocked, 0)

    def test_speedup_calculated(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertGreater(result.estimated_speedup_ratio, 1.0)

    def test_heavy_checks_avoided(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertGreater(result.heavy_checks_avoided, 0)

    def test_cost_model_transparent(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertIn("cost_model", result.to_dict())
        self.assertEqual(result.to_dict()["cost_model"]["dtl_scan"], 1)

    def test_evidence_records_created(self):
        cases = generate_all_cases()[:5]
        result = run_benchmark(cases=cases, evidence=True)
        self.assertEqual(result.evidence_packs_created, 5)

    def test_benchmark_hash_stable(self):
        cases = generate_all_cases()
        r1 = run_benchmark(cases=cases)
        r2 = run_benchmark(cases=cases)
        self.assertEqual(r1.benchmark_hash, r2.benchmark_hash)

    def test_replay_command_set(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertIn("chipgate", result.replay_command)

    def test_public_wording_present(self):
        result = run_benchmark_demo()
        self.assertIn("does not guarantee", result.public_wording)

    def test_disclaimer_present(self):
        result = run_benchmark_demo()
        self.assertIn("benchmark cost model", result.disclaimer.lower())

    def test_to_dict(self):
        result = run_benchmark_demo()
        d = result.to_dict()
        self.assertIn("total_cases", d)
        self.assertIn("false_accept_rate", d)
        self.assertIn("estimated_speedup_ratio", d)

    def test_to_full_dict(self):
        result = run_benchmark_demo()
        d = result.to_full_dict()
        self.assertIn("case_results_full", d)
        self.assertIsInstance(d["case_results_full"], list)

    def test_json_schema_stable(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        d = result.to_dict()
        # Verify JSON serializable
        json_str = json.dumps(d, sort_keys=True)
        self.assertTrue(len(json_str) > 0)

    def test_case_results_count_matches(self):
        cases = generate_all_cases()
        result = run_benchmark(cases=cases)
        self.assertEqual(len(result.case_results), len(cases))


class TestHTMLReport(unittest.TestCase):
    """Test HTML report generation."""

    def test_html_generated(self):
        result = run_benchmark_demo()
        html = generate_html_report(result)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("DTL-ChipBench", html)

    def test_html_contains_metrics(self):
        result = run_benchmark_demo()
        html = generate_html_report(result)
        self.assertIn("Unsafe Blocked", html)
        self.assertIn("Verification-Cost Reduction", html)
        self.assertIn("False Accept", html)

    def test_html_contains_disclaimer(self):
        result = run_benchmark_demo()
        html = generate_html_report(result)
        self.assertIn("verification-cost units", html)
        self.assertIn("does not guarantee", html)

    def test_html_writable(self):
        result = run_benchmark_demo()
        html = generate_html_report(result)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html)
            path = f.name
        try:
            self.assertGreater(os.path.getsize(path), 1000)
        finally:
            os.unlink(path)

    def test_html_self_contained(self):
        result = run_benchmark_demo()
        html = generate_html_report(result)
        # No external CSS/JS imports
        self.assertNotIn("<link ", html)
        self.assertNotIn("<script src=", html)


class TestBenchCLI(unittest.TestCase):
    """Test bench CLI integration."""

    def test_bench_demo_cli(self):
        from chipgate.__main__ import main
        result = main(["bench", "--demo"])
        self.assertEqual(result, 0)

    def test_bench_html_cli(self):
        from chipgate.__main__ import main
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            result = main(["bench", "--demo", "--html", path])
            self.assertEqual(result, 0)
            content = Path(path).read_text()
            self.assertIn("DTL-ChipBench", content)
            self.assertIn("verification-cost units", content)
        finally:
            os.unlink(path)


class TestBenchNoPrivateImports(unittest.TestCase):
    """Ensure no private JARVI3 or secrets in bench modules."""

    def test_no_jarvi3(self):
        pkg_dir = Path(__file__).parent.parent / "chipgate"
        for py_file in pkg_dir.glob("bench*.py"):
            content = py_file.read_text()
            self.assertNotIn("jarvi3", content.lower(), f"Private import in {py_file}")

    def test_no_secrets(self):
        pkg_dir = Path(__file__).parent.parent / "chipgate"
        for py_file in pkg_dir.glob("bench*.py"):
            content = py_file.read_text()
            self.assertNotIn("API_KEY", content)
            self.assertNotIn("SECRET", content)


# ── Utilities ────────────────────────────────────────────────────────────────

from unittest.mock import patch


if __name__ == "__main__":
    unittest.main()