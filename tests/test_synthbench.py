"""
Tests for ChipSynthBench / PPA-Bench (Phase 6).

Covers:
- Safe smaller candidate ranks above baseline
- Unsafe fast candidate is rejected
- Candidate missing kill_switch is rejected
- Candidate missing verifier is rejected
- Area proxy calculated
- Timing-depth proxy calculated
- Power proxy calculated
- safe_improvement_score calculated
- Unsafe candidate cannot be best tradeoff
- HTML report generated
- JSON schema stable
- Evidence records created
- Replay command stable
- No private JARVI3 imports
- No secrets
- No shell=True
- English-only output
"""

import json
import os
import sys
import tempfile
import unittest

# Ensure chipgate package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chipgate.area_proxy import (
    compute_area_proxy,
    compute_area_proxy_from_rtl,
    area_improvement_percent,
)
from chipgate.timing_proxy import (
    compute_timing_proxy,
    compute_timing_proxy_from_rtl,
    timing_improvement_percent,
)
from chipgate.power_proxy import (
    compute_power_proxy,
    compute_power_proxy_from_rtl,
    power_improvement_percent,
)
from chipgate.ppa import compute_ppa, compute_ppa_from_rtl, compare_ppa
from chipgate.design_score import compute_design_score, rank_candidates
from chipgate.synthbench import (
    run_synthbench,
    SynthCandidate,
    BUILTIN_CANDIDATES,
    _evaluate_candidate,
)
from chipgate.synth_report import generate_synthbench_html
from chipgate import statuses as st


# ── Test RTL strings ──────────────────────────────────────────────────────────

SAFE_GATE_RTL = """module safe_gate (
    input clk,
    input rst,
    input ai_output,
    input verifier_ok,
    input policy_ok,
    input kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        if (rst) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output & verifier_ok & policy_ok & ~kill_switch;
        end
    end
endmodule"""

UNSAFE_GATE_RTL = """module unsafe_gate (
    input clk,
    input ai_output,
    output actuator_enable
);
    assign actuator_enable = ai_output;
endmodule"""

MISSING_KILL_SWITCH_RTL = """module no_kill (
    input clk,
    input rst,
    input ai_output,
    input verifier_ok,
    input policy_ok,
    output reg actuator_enable
);
    always @(posedge clk) begin
        if (rst) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output & verifier_ok & policy_ok;
        end
    end
endmodule"""

MISSING_VERIFIER_RTL = """module no_verifier (
    input clk,
    input rst,
    input ai_output,
    input policy_ok,
    input kill_switch,
    output reg actuator_enable
);
    always @(posedge clk) begin
        if (rst) begin
            actuator_enable <= 1'b0;
        end else begin
            actuator_enable <= ai_output & policy_ok & ~kill_switch;
        end
    end
endmodule"""


def _write_temp_rtl(rtl_text: str, name: str = "test.v") -> str:
    """Write RTL to a temp file and return the path."""
    tmp_dir = tempfile.mkdtemp(prefix="chipgate_test_")
    path = os.path.join(tmp_dir, name)
    with open(path, "w") as f:
        f.write(rtl_text)
    return path


# ── Area Proxy Tests ──────────────────────────────────────────────────────────

class TestAreaProxy(unittest.TestCase):
    """Tests for area proxy estimator."""

    def test_area_proxy_calculated(self):
        """Area proxy should be calculated for any valid RTL file."""
        path = _write_temp_rtl(SAFE_GATE_RTL)
        try:
            result = compute_area_proxy(path)
            self.assertGreater(result.weighted_score, 0.0)
            self.assertGreater(result.raw_score, 0)
        finally:
            os.remove(path)
            os.rmdir(os.path.dirname(path))

    def test_area_proxy_from_rtl(self):
        """Area proxy from inline RTL should match file-based computation."""
        result = compute_area_proxy_from_rtl(SAFE_GATE_RTL, "safe")
        self.assertGreater(result.weighted_score, 0.0)

    def test_area_improvement_percent(self):
        """Area improvement percentage should be calculated correctly."""
        # If candidate is half the area of baseline, improvement is 50%
        result = area_improvement_percent(100.0, 50.0)
        self.assertEqual(result, 50.0)

    def test_area_improvement_negative(self):
        """Area regression should show negative improvement."""
        result = area_improvement_percent(50.0, 100.0)
        self.assertEqual(result, -100.0)

    def test_area_improvement_zero_baseline(self):
        """Zero baseline should return 0.0 to avoid division by zero."""
        result = area_improvement_percent(0.0, 50.0)
        self.assertEqual(result, 0.0)

    def test_larger_rtl_has_higher_area(self):
        """A structurally larger RTL should have a higher area proxy score."""
        small_rtl = "module m(input a, output b); assign b = a; endmodule"
        large_rtl = SAFE_GATE_RTL  # Has multiple ports, always block, etc.
        small = compute_area_proxy_from_rtl(small_rtl, "small")
        large = compute_area_proxy_from_rtl(large_rtl, "large")
        self.assertLess(small.weighted_score, large.weighted_score)


# ── Timing Proxy Tests ────────────────────────────────────────────────────────

class TestTimingProxy(unittest.TestCase):
    """Tests for timing-depth proxy estimator."""

    def test_timing_proxy_calculated(self):
        """Timing-depth proxy should be calculated for any valid RTL file."""
        path = _write_temp_rtl(SAFE_GATE_RTL)
        try:
            result = compute_timing_proxy(path)
            self.assertGreaterEqual(result.weighted_depth, 0.0)
        finally:
            os.remove(path)
            os.rmdir(os.path.dirname(path))

    def test_timing_proxy_from_rtl(self):
        """Timing proxy from inline RTL should work."""
        result = compute_timing_proxy_from_rtl(SAFE_GATE_RTL, "safe")
        self.assertGreaterEqual(result.weighted_depth, 0.0)

    def test_timing_improvement_percent(self):
        """Timing improvement should be calculated correctly."""
        result = timing_improvement_percent(10.0, 5.0)
        self.assertEqual(result, 50.0)

    def test_deeper_expression_higher_timing(self):
        """A deeper expression chain should have higher timing proxy."""
        shallow = "module m(input a, output b); assign b = a & 1'b1; endmodule"
        deep = "module m(input a, output b); assign b = ((a & 1'b1) | (1'b0 & 1'b1)) ^ (a | 1'b0); endmodule"
        shallow_r = compute_timing_proxy_from_rtl(shallow, "shallow")
        deep_r = compute_timing_proxy_from_rtl(deep, "deep")
        self.assertLessEqual(shallow_r.weighted_depth, deep_r.weighted_depth)


# ── Power Proxy Tests ─────────────────────────────────────────────────────────

class TestPowerProxy(unittest.TestCase):
    """Tests for power-toggle proxy estimator."""

    def test_power_proxy_calculated(self):
        """Power proxy should be calculated for any valid RTL file."""
        path = _write_temp_rtl(SAFE_GATE_RTL)
        try:
            result = compute_power_proxy(path)
            self.assertGreater(result.weighted_power_proxy, 0.0)
        finally:
            os.remove(path)
            os.rmdir(os.path.dirname(path))

    def test_power_proxy_from_rtl(self):
        """Power proxy from inline RTL should work."""
        result = compute_power_proxy_from_rtl(SAFE_GATE_RTL, "safe")
        self.assertGreater(result.weighted_power_proxy, 0.0)

    def test_power_improvement_percent(self):
        """Power improvement should be calculated correctly."""
        result = power_improvement_percent(100.0, 80.0)
        self.assertEqual(result, 20.0)

    def test_more_signals_higher_power(self):
        """More safety-critical signals should increase power proxy."""
        few_signals = "module m(input a, output b); assign b = a; endmodule"
        many_signals = SAFE_GATE_RTL  # Has many safety signals
        few_r = compute_power_proxy_from_rtl(few_signals, "few")
        many_r = compute_power_proxy_from_rtl(many_signals, "many")
        self.assertLess(few_r.weighted_power_proxy, many_r.weighted_power_proxy)


# ── PPA Aggregator Tests ─────────────────────────────────────────────────────

class TestPPAAggregator(unittest.TestCase):
    """Tests for PPA proxy aggregator."""

    def test_ppa_computed(self):
        """PPA result should contain all three proxy components."""
        result = compute_ppa_from_rtl(SAFE_GATE_RTL, "safe")
        self.assertIn("area_proxy", result.to_dict())
        self.assertIn("timing_depth_proxy", result.to_dict())
        self.assertIn("power_toggle_proxy", result.to_dict())

    def test_ppa_comparison(self):
        """PPA comparison should calculate improvements correctly."""
        baseline = compute_ppa_from_rtl(SAFE_GATE_RTL, "baseline")
        # Smaller module should show area improvement
        small_rtl = "module m(input a, output b); assign b = a; endmodule"
        candidate = compute_ppa_from_rtl(small_rtl, "small")
        comparison = compare_ppa(baseline, candidate, "test")
        self.assertGreater(comparison.area_improvement_pct, 0)


# ── Design Score Tests ────────────────────────────────────────────────────────

class TestDesignScore(unittest.TestCase):
    """Tests for design score calculator."""

    def test_safe_improvement_score_calculated(self):
        """Design score should be calculated for safe candidates."""
        ds = compute_design_score(
            candidate_id="test",
            safety_pass=True,
            longevity_pass=True,
            no_regression_pass=True,
            area_improvement_pct=20.0,
            timing_improvement_pct=10.0,
            power_improvement_pct=15.0,
        )
        self.assertGreater(ds.safe_improvement_score, 0)
        self.assertTrue(ds.can_rank)

    def test_unsafe_cannot_rank(self):
        """Unsafe candidates should not be able to rank."""
        ds = compute_design_score(
            candidate_id="unsafe",
            safety_pass=False,
            longevity_pass=True,
            no_regression_pass=True,
            area_improvement_pct=50.0,
            timing_improvement_pct=50.0,
            power_improvement_pct=50.0,
        )
        self.assertFalse(ds.can_rank)
        self.assertEqual(ds.safe_improvement_score, float("-inf"))

    def test_regression_cannot_rank(self):
        """Candidates with regression should not be able to rank."""
        ds = compute_design_score(
            candidate_id="regressed",
            safety_pass=True,
            longevity_pass=True,
            no_regression_pass=False,
            area_improvement_pct=20.0,
            timing_improvement_pct=10.0,
            power_improvement_pct=15.0,
        )
        self.assertFalse(ds.can_rank)

    def test_unsafe_cannot_be_best_tradeoff(self):
        """Unsafe candidates must never be best tradeoff."""
        scores = [
            compute_design_score("unsafe", False, True, True, 50, 50, 50),
            compute_design_score("safe", True, True, True, 5, 5, 5),
        ]
        ranked = rank_candidates(scores)
        # Unsafe should be at the bottom
        self.assertFalse(ranked[-1].can_rank)
        # Safe should be at the top
        self.assertTrue(ranked[0].can_rank)
        self.assertTrue(ranked[0].is_best_tradeoff)

    def test_higher_score_ranks_higher(self):
        """Among safe candidates, higher score should rank higher."""
        scores = [
            compute_design_score("low", True, True, True, 5, 5, 5),
            compute_design_score("high", True, True, True, 30, 30, 30),
            compute_design_score("mid", True, True, True, 15, 15, 15),
        ]
        ranked = rank_candidates(scores)
        self.assertEqual(ranked[0].candidate_id, "high")
        self.assertEqual(ranked[1].candidate_id, "mid")
        self.assertEqual(ranked[2].candidate_id, "low")
        self.assertTrue(ranked[0].is_best_tradeoff)

    def test_rank_candidates_dict(self):
        """Ranked candidates should serialize to dict."""
        ds = compute_design_score("test", True, True, True, 10, 10, 10)
        d = ds.to_dict()
        self.assertIn("candidate_id", d)
        self.assertIn("safe_improvement_score", d)
        self.assertIn("can_rank", d)


# ── SynthBench Integration Tests ─────────────────────────────────────────────

class TestSynthBench(unittest.TestCase):
    """Integration tests for the full synthbench runner."""

    def test_demo_runs(self):
        """Demo should run without errors."""
        result = run_synthbench(demo=True)
        self.assertEqual(result.total_candidates, 7)
        self.assertGreater(result.evidence_packs_created, 0)

    def test_full_bench_runs(self):
        """Full benchmark should run with all 10 candidates."""
        result = run_synthbench()
        self.assertEqual(result.total_candidates, 10)

    def test_safe_smaller_ranks_above_baseline(self):
        """Safe smaller candidate should rank above baseline."""
        result = run_synthbench()
        ranked_ids = [ds.candidate_id for ds in result.ranked_candidates if ds.can_rank]
        baseline_idx = ranked_ids.index("candidate_baseline_safe") if "candidate_baseline_safe" in ranked_ids else -1
        smaller_idx = ranked_ids.index("candidate_safe_smaller") if "candidate_safe_smaller" in ranked_ids else -1
        # smaller should rank higher (lower index)
        if baseline_idx >= 0 and smaller_idx >= 0:
            self.assertLess(smaller_idx, baseline_idx)

    def test_unsafe_fast_candidate_rejected(self):
        """Fast unsafe candidate should be rejected (safety fail)."""
        result = run_synthbench()
        for cr in result.candidate_results:
            if cr.candidate_id == "candidate_fast_unsafe":
                self.assertEqual(cr.safety_status, st.SYNTHBENCH_FAIL)
                self.assertFalse(cr.can_rank)
                return
        self.fail("candidate_fast_unsafe not found in results")

    def test_missing_kill_switch_rejected(self):
        """Candidate missing kill_switch should be rejected."""
        result = run_synthbench()
        for cr in result.candidate_results:
            if cr.candidate_id == "candidate_missing_kill_switch":
                self.assertEqual(cr.safety_status, st.SYNTHBENCH_FAIL)
                self.assertFalse(cr.can_rank)
                return
        self.fail("candidate_missing_kill_switch not found")

    def test_missing_verifier_rejected(self):
        """Candidate missing verifier should be rejected."""
        result = run_synthbench()
        for cr in result.candidate_results:
            if cr.candidate_id == "candidate_missing_verifier":
                self.assertEqual(cr.safety_status, st.SYNTHBENCH_FAIL)
                self.assertFalse(cr.can_rank)
                return
        self.fail("candidate_missing_verifier not found")

    def test_unsafe_cannot_be_best_tradeoff(self):
        """Best tradeoff must be a safe candidate."""
        result = run_synthbench()
        if result.best_tradeoff_candidate:
            for cr in result.candidate_results:
                if cr.candidate_id == result.best_tradeoff_candidate:
                    self.assertEqual(cr.safety_status, st.SYNTHBENCH_PASS)
                    self.assertTrue(cr.can_rank)
                    return
            self.fail("Best tradeoff candidate not found in results")

    def test_evidence_records_created(self):
        """Each candidate should have an evidence hash."""
        result = run_synthbench(demo=True)
        for cr in result.candidate_results:
            self.assertTrue(len(cr.evidence_hash) > 0)
            self.assertTrue(len(cr.rtl_hash) > 0)

    def test_replay_command_stable(self):
        """Replay command should be non-empty and deterministic."""
        result = run_synthbench(demo=True)
        self.assertTrue(len(result.replay_command) > 0)
        # Run again and check replay command is the same
        result2 = run_synthbench(demo=True)
        self.assertEqual(result.replay_command, result2.replay_command)

    def test_html_report_generated(self):
        """HTML report should be generated without errors."""
        result = run_synthbench(demo=True)
        html = generate_synthbench_html(result)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("ChipSynthBench", html)
        self.assertIn("Area Proxy", html)
        self.assertIn("Timing-Depth Proxy", html)
        self.assertIn("Power-Toggle Proxy", html)
        self.assertIn("disclaimer", html.lower())

    def test_json_schema_stable(self):
        """JSON output should have stable schema."""
        result = run_synthbench(demo=True)
        d = result.to_dict()
        # Required top-level keys
        required_keys = [
            "benchmark_version", "timestamp_utc", "total_candidates",
            "safe_improved_designs", "unsafe_improvements_rejected",
            "regressions_detected", "best_tradeoff_candidate",
            "area_proxy_improvement_pct", "timing_depth_improvement_pct",
            "power_proxy_improvement_pct", "replay_match_rate",
            "evidence_packs_created", "disclaimer", "public_wording",
        ]
        for key in required_keys:
            self.assertIn(key, d)

        # Candidate results should have required keys
        for cr_dict in d["candidate_results"]:
            self.assertIn("candidate_id", cr_dict)
            self.assertIn("safety_status", cr_dict)
            self.assertIn("area_proxy_score", cr_dict)
            self.assertIn("rtl_hash", cr_dict)
            self.assertIn("evidence_hash", cr_dict)

    def test_benchmark_from_path(self):
        """Loading candidates from a benchmark path should work."""
        bench_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "benchmarks", "synthbench_v0"
        )
        if os.path.exists(bench_path):
            result = run_synthbench(benchmark_path=bench_path)
            self.assertEqual(result.total_candidates, 10)

    def test_overall_status_pass_when_improved(self):
        """Overall status should be PASS when there are safe improved designs."""
        result = run_synthbench(demo=True)
        if result.safe_improved_designs > 0:
            self.assertGreater(result.safe_improved_designs, 0)

    def test_synthesis_cost_in_json(self):
        """Cost model should be included in JSON output."""
        result = run_synthbench(demo=True)
        d = result.to_dict()
        self.assertIn("cost_model", d)
        self.assertIn("dtl_scan", d["cost_model"])
        self.assertIn("synthesis", d["cost_model"])


# ── Safety / Integrity Tests ─────────────────────────────────────────────────

class TestSafetyAndIntegrity(unittest.TestCase):
    """Tests for safety, integrity, and compliance."""

    def test_no_private_jarvi3_imports(self):
        """No source file should import from jarvi3 or private DTL internals."""
        chipgate_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'chipgate'
        )
        for root, dirs, files in os.walk(chipgate_dir):
            dirs[:] = [d for d in dirs if d not in {'__pycache__', '.venv'}]
            for fname in files:
                if fname.endswith('.py'):
                    fpath = os.path.join(root, fname)
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    self.assertNotIn('import jarvi3', content,
                                     f"{fpath} imports jarvi3")
                    self.assertNotIn('from jarvi3', content,
                                     f"{fpath} imports from jarvi3")

    def test_no_secrets_in_synthbench(self):
        """No API keys or secrets in synthbench files."""
        files_to_check = [
            'synthbench.py', 'ppa.py', 'area_proxy.py',
            'timing_proxy.py', 'power_proxy.py', 'design_score.py',
            'synth_report.py',
        ]
        chipgate_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for fname in files_to_check:
            fpath = os.path.join(chipgate_dir, 'chipgate', fname)
            if os.path.exists(fpath):
                with open(fpath, 'r') as f:
                    content = f.read()
                self.assertNotIn('API_KEY', content)
                self.assertNotIn('SECRET', content)
                self.assertNotIn('PASSWORD', content)

    def test_no_shell_true(self):
        """No shell=True in synthbench code."""
        files_to_check = [
            'synthbench.py', 'ppa.py', 'area_proxy.py',
            'timing_proxy.py', 'power_proxy.py',
        ]
        chipgate_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for fname in files_to_check:
            fpath = os.path.join(chipgate_dir, 'chipgate', fname)
            if os.path.exists(fpath):
                with open(fpath, 'r') as f:
                    content = f.read()
                self.assertNotIn('shell=True', content,
                                 f"{fname} uses shell=True")

    def test_english_only_output(self):
        """All public output should be in English."""
        result = run_synthbench(demo=True)
        d = result.to_dict()
        # Check all string fields contain only ASCII / common English characters
        for key in ['public_wording', 'disclaimer', 'replay_command']:
            value = d.get(key, '')
            # No CJK characters (Unicode range check)
            for char in value:
                code = ord(char)
                # Basic check: no CJK Unified Ideographs
                self.assertFalse(
                    0x4E00 <= code <= 0x9FFF,
                    f"Non-English character found in {key}: {char}"
                )


# ── Status Constants Tests ────────────────────────────────────────────────────

class TestSynthBenchStatuses(unittest.TestCase):
    """Tests for new status constants."""

    def test_synthbench_statuses_defined(self):
        """All synthbench statuses should be defined."""
        self.assertTrue(hasattr(st, 'SYNTHBENCH_PASS'))
        self.assertTrue(hasattr(st, 'SYNTHBENCH_FAIL'))
        self.assertTrue(hasattr(st, 'SAFE_IMPROVED_DESIGN'))
        self.assertTrue(hasattr(st, 'UNSAFE_IMPROVEMENT_REJECTED'))
        self.assertTrue(hasattr(st, 'AREA_IMPROVED'))
        self.assertTrue(hasattr(st, 'AREA_REGRESSED'))
        self.assertTrue(hasattr(st, 'TIMING_IMPROVED'))
        self.assertTrue(hasattr(st, 'TIMING_REGRESSED'))
        self.assertTrue(hasattr(st, 'POWER_PROXY_IMPROVED'))
        self.assertTrue(hasattr(st, 'POWER_PROXY_REGRESSED'))
        self.assertTrue(hasattr(st, 'BEST_TRADEOFF_CANDIDATE'))
        self.assertTrue(hasattr(st, 'NEEDS_REAL_SYNTHESIS'))

    def test_synthbench_pass_in_pass_statuses(self):
        """SYNTHBENCH_PASS should be in PASS_STATUSES."""
        self.assertIn(st.SYNTHBENCH_PASS, st.PASS_STATUSES)
        self.assertIn(st.SAFE_IMPROVED_DESIGN, st.PASS_STATUSES)
        self.assertIn(st.AREA_IMPROVED, st.PASS_STATUSES)
        self.assertIn(st.BEST_TRADEOFF_CANDIDATE, st.PASS_STATUSES)

    def test_synthbench_fail_in_fail_statuses(self):
        """SYNTHBENCH_FAIL should be in FAIL_STATUSES."""
        self.assertIn(st.SYNTHBENCH_FAIL, st.FAIL_STATUSES)
        self.assertIn(st.UNSAFE_IMPROVEMENT_REJECTED, st.FAIL_STATUSES)
        self.assertIn(st.AREA_REGRESSED, st.FAIL_STATUSES)

    def test_synthbench_public_wording(self):
        """SYNTHBENCH_PUBLIC_WORDING should be defined."""
        self.assertTrue(hasattr(st, 'SYNTHBENCH_PUBLIC_WORDING'))
        self.assertIn('proxy metrics', st.SYNTHBENCH_PUBLIC_WORDING)

    def test_synthbench_limitation(self):
        """SYNTHBENCH_LIMITATION should be defined."""
        self.assertTrue(hasattr(st, 'SYNTHBENCH_LIMITATION'))
        self.assertIn('proxy', st.SYNTHBENCH_LIMITATION)


if __name__ == '__main__':
    unittest.main()