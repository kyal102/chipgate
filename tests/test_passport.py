import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from chipgate.passport_schema import (
    SCHEMA_VERSION, BENCHMARK_NAME, BENCHMARK_VERSION,
    ALL_PASSPORT_STATUSES, ALL_EXPORT_DECISIONS, ALL_RISK_LEVELS,
    ALL_BADGE_TYPES, ALL_ARTIFACT_TYPES, ALL_GATE_IDS,
    FORBIDDEN_PHRASES, PRIVATE_PATTERNS,
    PASSPORT_PUBLIC_WORDING, PASSPORT_LIMITATION,
    REQUIRED_PASSPORT_FIELDS, PassportData, BadgeData, PassportMetrics,
)
from chipgate.passport_artifacts import (
    compute_artifact_hash, compute_artifact_hash_file, read_artifact_content,
    check_private_leak, check_unsafe_claims,
    check_no_absolute_local_path, check_english_only, validate_artifact_intake,
)
from chipgate.passport_policy import (
    assign_risk_level, select_gates, compute_export_decision, classify_artifact_type,
    ARTIFACT_RISK_MAP, ARTIFACT_GATE_MAP,
)
from chipgate.passport_builder import build_passport
from chipgate.passport_badges import (
    determine_badge, generate_badge_json, generate_badge_svg, BADGE_COLORS, STATUS_TO_BADGE,
)
from chipgate.passport_export import prepare_handoff_pack
from chipgate.passport_replay import (
    generate_replay_command, replay_passport, check_replay_stability,
)
from chipgate.passport_manifest import (
    compute_hash, compute_dict_hash, compute_certificate_hash,
    build_manifest, verify_passport, load_passport_from_file, save_passport_to_file,
)
from chipgate.passport_report import (
    generate_passport_json_report, generate_passport_html_report,
)
from chipgate.passport_examples import (
    DEMO_RTL_SAFE, DEMO_RTL_UNSAFE, DEMO_DOCUMENT, DEMO_PHYSICS,
    DEMO_CHEMISTRY, DEMO_ADAPTER_INPUT, DEMO_FIXTURES, BENCHMARK_INFO,
)
from chipgate.design_passport import (
    run_passport_pipeline, run_demo, verify_passport_file,
    export_badge_for_passport, run_replay_for_artifact,
)


def _make_temp(content: str = "") -> str:
    """Create a temp file, write content, return path, caller deletes."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False)
    f.write(content)
    return f.name

def _make_temp_py(content: str = "") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    f.write(content)
    return f.name

def _make_temp_json(content: str = "{}") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    f.write(content)
    return f.name


class TestPassportSchema(unittest.TestCase):
    """Tests for passport schema constants and data structures."""

    def test_schema_version(self):
        self.assertEqual(SCHEMA_VERSION, "designpassport.v0")

    def test_benchmark_name(self):
        self.assertEqual(BENCHMARK_NAME, "designpassport_v0")

    def test_benchmark_version(self):
        self.assertEqual(BENCHMARK_VERSION, "0.1.0")

    def test_all_passport_statuses_count(self):
        self.assertGreaterEqual(len(ALL_PASSPORT_STATUSES), 14)

    def test_all_export_decisions_count(self):
        self.assertEqual(len(ALL_EXPORT_DECISIONS), 6)

    def test_all_risk_levels_count(self):
        self.assertEqual(len(ALL_RISK_LEVELS), 5)

    def test_all_badge_types_count(self):
        self.assertEqual(len(ALL_BADGE_TYPES), 7)

    def test_all_artifact_types_count(self):
        self.assertEqual(len(ALL_ARTIFACT_TYPES), 12)

    def test_all_gate_ids_count(self):
        self.assertEqual(len(ALL_GATE_IDS), 11)

    def test_forbidden_phrases_includes_nvidia(self):
        self.assertIn("NVIDIA", FORBIDDEN_PHRASES)

    def test_forbidden_phrases_includes_gpu_replacement(self):
        self.assertIn("GPU_REPLACEMENT", FORBIDDEN_PHRASES)

    def test_private_patterns_not_empty(self):
        self.assertTrue(len(PRIVATE_PATTERNS) > 0)

    def test_required_fields_count(self):
        self.assertEqual(len(REQUIRED_PASSPORT_FIELDS), 17)

    def test_required_fields_content(self):
        expected = {
            "schema_version", "passport_id", "artifact_id", "artifact_type",
            "risk_level", "created_at", "gates_requested",
            "gates_run", "gates_passed", "gates_failed",
            "evidence_packs", "artifact_hashes",
            "replay_command", "passport_status",
            "export_decision", "limitations", "certificate_hash",
        }
        self.assertEqual(set(REQUIRED_PASSPORT_FIELDS), expected)

    def test_passport_data_defaults(self):
        p = PassportData()
        self.assertEqual(p.schema_version, SCHEMA_VERSION)
        self.assertEqual(p.artifact_type, "unknown")
        self.assertEqual(p.risk_level, "UNKNOWN")
        self.assertEqual(p.passport_status, "PASSPORT_CREATED")
        self.assertEqual(p.export_decision, "EXPORT_NEEDS_REVIEW")
        self.assertEqual(p.badge, "UNVERIFIED")
        self.assertEqual(len(p.gates_requested), 0)
        self.assertEqual(len(p.evidence_packs), 0)
        self.assertEqual(len(p.limitations), 0)

    def test_badge_data_defaults(self):
        b = BadgeData()
        self.assertEqual(b.badge, "UNVERIFIED")
        self.assertEqual(b.artifact_id, "")

    def test_passport_metrics_defaults(self):
        m = PassportMetrics()
        self.assertEqual(m.artifacts_checked, 0)
        self.assertEqual(m.gates_passed, 0)

    def test_gate_result_defaults(self):
        from chipgate.passport_schema import GateResult
        g = GateResult()
        self.assertFalse(g.passed)
        self.assertFalse(g.failed)
        self.assertEqual(g.gate_id, "")

class TestPassportPolicy(unittest.TestCase):
    """Tests for risk assignment, gate selection, export decisions, and classification."""

    def test_assign_risk_level_rtl(self):
        self.assertEqual(assign_risk_level("rtl"), "HIGH")

    def test_assign_risk_level_document(self):
        self.assertEqual(assign_risk_level("document"), "LOW")

    def test_assign_risk_level_code(self):
        self.assertEqual(assign_risk_level("code"), "MEDIUM")

    def test_assign_risk_level_unknown(self):
        self.assertEqual(assign_risk_level("unknown"), "UNKNOWN")

    def test_assign_risk_level_robotics(self):
        self.assertEqual(assign_risk_level("robotics_control_demo"), "SAFETY_CRITICAL")

    def test_select_gates_rtl(self):
        gates = select_gates("rtl")
        self.assertIn("chipgate", gates)
        self.assertIn("evidencepack", gates)
        self.assertIn("replaygate", gates)

    def test_select_gates_document(self):
        gates = select_gates("document")
        self.assertIn("claimgate", gates)
        self.assertIn("claimlint", gates)

    def test_select_gates_unknown(self):
        gates = select_gates("unknown")
        self.assertEqual(gates, [])

    def test_select_gates_with_requested(self):
        gates = select_gates("rtl", requested_gates=["chipgate", "replaygate"])
        self.assertEqual(gates, ["chipgate", "replaygate"])

    def test_select_gates_filters_unknown_requested(self):
        gates = select_gates("rtl", requested_gates=["not_a_gate"])
        self.assertEqual(gates, [])

    def test_compute_export_decision_private_leak(self):
        self.assertEqual(compute_export_decision("HIGH", [], [], [], private_leak=True), "EXPORT_BLOCKED")

    def test_compute_export_decision_unsafe_claim(self):
        self.assertEqual(compute_export_decision("LOW", [], [], [], unsafe_claim=True), "EXPORT_BLOCKED")

    def test_compute_export_decision_no_gates(self):
        self.assertEqual(compute_export_decision("UNKNOWN", [], [], []), "EXPORT_UNSUPPORTED")

    def test_compute_export_decision_high_risk_failed(self):
        self.assertEqual(compute_export_decision(risk_level="HIGH", gates_passed=[], gates_failed=["chipgate"], gates_requested=["chipgate"]), "EXPORT_BLOCKED")

    def test_compute_export_decision_safety_critical(self):
        self.assertEqual(compute_export_decision("SAFETY_CRITICAL", [], [], ["soc_safety"]), "EXPORT_NEEDS_REVIEW")

    def test_compute_export_decision_safety_critical_failed(self):
        self.assertEqual(compute_export_decision(risk_level="SAFETY_CRITICAL", gates_passed=[], gates_failed=["chipgate"], gates_requested=["chipgate"]), "EXPORT_BLOCKED")

    def test_classify_by_extension_v(self):
        self.assertEqual(classify_artifact_type(file_path="design.v"), "rtl")

    def test_classify_by_extension_sv(self):
        self.assertEqual(classify_artifact_type(file_path="top.sv"), "rtl")

    def test_classify_by_content(self):
        content = "module foo (input x, output y); endmodule"
        self.assertEqual(classify_artifact_type(content=content), "rtl")

    def test_classify_by_adapter(self):
        self.assertEqual(classify_artifact_type(adapter_type="rtl"), "rtl")

    def test_classify_unknown(self):
        self.assertEqual(classify_artifact_type(content="random stuff"), "unknown")

class TestPassportArtifacts(unittest.TestCase):
    """Tests for artifact intake, hashing, private leak detection, unsafe claim checks."""

    def test_compute_artifact_hash(self):
        h = compute_artifact_hash("hello")
        self.assertTrue(h.startswith("sha256:"))
        self.assertEqual(len(h), 7 + 64)  # "sha256:" + 64 hex chars

    def test_compute_artifact_hash_deterministic(self):
        h1 = compute_artifact_hash("test")
        h2 = compute_artifact_hash("test")
        self.assertEqual(h1, h2)

    def test_compute_artifact_hash_empty(self):
        self.assertEqual(compute_artifact_hash(""), "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_check_private_leak_detected(self):
        has, matched = check_private_leak("some jarvi3_private text here")
        self.assertTrue(has)
        self.assertIn("jarvi3_private", matched)

    def test_check_private_leak_clean(self):
        has, matched = check_private_leak("clean content with no leaks")
        self.assertFalse(has)
        self.assertEqual(matched, [])

    def test_check_private_leak_empty(self):
        has, matched = check_private_leak("")
        self.assertFalse(has)

    def test_check_unsafe_claims_detected(self):
        has, matched = check_unsafe_claims("This is CERTIFIED_SAFE")
        self.assertTrue(has)
        self.assertIn("CERTIFIED_SAFE", matched)

    def test_check_unsafe_claims_clean(self):
        has, matched = check_unsafe_claims("all gates passed")
        self.assertFalse(has)

    def test_check_english_only_passes_ascii(self):
        self.assertTrue(check_english_only("hello world"))

    def test_check_english_only_blocks_non_ascii(self):
        self.assertFalse(check_english_only("\u4e16"))

    def test_validate_artifact_intake_basic(self):
        result = validate_artifact_intake(content="some content")
        self.assertTrue(result["valid"])
        self.assertEqual(result["artifact_type"], "unknown")

    def test_validate_artifact_intake_adapter(self):
        result = validate_artifact_intake(
            adapter_input={
                "source": "test",
                "artifact_id": "a1",
                "artifact_type": "rtl",
            }
        )
        self.assertEqual(result["artifact_type"], "rtl")

    def test_validate_artifact_intake_empty(self):
        result = validate_artifact_intake()
        self.assertFalse(result["valid"])
        self.assertIn("No artifact content", result["errors"][0])

    def test_validate_artifact_intake_private_leak(self):
        result = validate_artifact_intake(
            content="has jarvi3_private pattern"
        )
        self.assertTrue(result["private_leak"])
        self.assertIn("jarvi3_private", result["private_leak_patterns"])

class TestPassportBuilder(unittest.TestCase):
    """Tests for the passport build pipeline."""

    def test_build_passport_safe_rtl(self):
        result = build_passport(
            artifact_id="test_rtl_001",
            content=DEMO_RTL_SAFE,
        )
        self.assertIn("passport", result)
        p = result["passport"]
        self.assertEqual(p["artifact_type"], "rtl")
        self.assertEqual(p["risk_level"], "HIGH")
        self.assertEqual(len(p["gates_run"]) > 0, True)
        self.assertIsNot(p["passport_id"], "")

    def test_build_passport_unsafe_rtl(self):
        result = build_passport(
            artifact_id="test_unsafe_001",
            content=DEMO_RTL_UNSAFE,
        )
        p = result["passport"]
        self.assertIn("NEEDS_REVIEW", p.get("passport_status", ""))

    def test_build_passport_document(self):
        result = build_passport(
            artifact_id="test_doc_001",
            content=DEMO_DOCUMENT,
        )
        p = result["passport"]
        self.assertIn(p["artifact_type"], ("document", "claim_set"))
        self.assertEqual(p["risk_level"], "LOW")

    def test_build_passport_private_leak(self):
        result = build_passport(
            artifact_id="test_leak_001",
            content="has jarvi3_private pattern",
        )
        p = result["passport"]
        self.assertEqual(p["passport_status"], "PASSPORT_PRIVATE_LEAK_BLOCKED")

    def test_build_passport_unsafe_claim(self):
        result = build_passport(
            artifact_id="test_claim_001",
            content="This is CERTIFIED_SAFE",
        )
        p = result["passport"]
        self.assertEqual(p["passport_status"], "PASSPORT_UNSAFE_CLAIM_BLOCKED")

    def test_build_passport_unknown(self):
        result = build_passport(
            artifact_id="test_unknown_001",
            content="random stuff with no structure",
        )
        p = result["passport"]
        self.assertEqual(p["artifact_type"], "unknown")
        self.assertEqual(p["risk_level"], "UNKNOWN")

    def test_build_passport_adapter_input(self):
        result = build_passport(
            artifact_id="adapter_001",
            adapter_input=DEMO_ADAPTER_INPUT,
        )
        self.assertIn("passport", result)
        self.assertEqual(result["passport"]["artifact_type"], "rtl")

    def test_build_passport_requested_gates(self):
        result = build_passport(
            artifact_id="req_001",
            content="module foo (input x, output y); endmodule",
            requested_gates=["chipgate"],
        )
        p = result["passport"]
        self.assertEqual(p["gates_requested"], ["chipgate"])

    def test_build_passport_metrics(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        m = result["metrics"]
        self.assertGreater(m["artifacts_checked"], 0)
        self.assertGreater(m["gates_run"], 0)
        self.assertGreater(m["badges_created"], 0)

class TestPassportReplay(unittest.TestCase):
    """Tests for replay verification and drift detection."""

    def test_replay_match_clean_passport(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        replay = replay_passport(result["passport"])
        self.assertTrue(replay["replay_match"])
        self.assertEqual(replay["replay_status"], "PASSPORT_REPLAY_MATCH")

    def test_replay_drift_on_tamper(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        p["artifact_type"] = "tampered_type"
        replay = replay_passport(p)
        self.assertFalse(replay["replay_match"])
        self.assertEqual(replay["replay_status"], "PASSPORT_REPLAY_DRIFT")

    def test_replay_drift_on_overlap(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        p["gates_passed"] = ["chipgate"]
        p["gates_failed"] = ["chipgate"]
        replay = replay_passport(p)
        self.assertFalse(replay["replay_match"])
        self.assertTrue(any("both passed and failed" in e for e in replay["errors"]))

    def test_check_replay_stability(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        self.assertTrue(check_replay_stability(result["passport"]))

class TestPassportManifest(unittest.TestCase):
    """Tests for manifest creation, verification, hash computation."""

    def test_compute_hash_format(self):
        h = compute_hash("test")
        self.assertTrue(h.startswith("sha256:"))

    def test_compute_dict_hash_deterministic(self):
        h1 = compute_dict_hash({"a": 1})
        h2 = compute_dict_hash({"a": 1})
        self.assertEqual(h1, h2)
    def test_compute_dict_hash_order_independent(self):
        h1 = compute_dict_hash({"b": 2, "a": 1})
        h2 = compute_dict_hash({"a": 1, "b": 2})
        self.assertEqual(h1, h2)

    def test_verify_passport_valid(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        verification = verify_passport(p)
        self.assertTrue(verification["valid"])
        self.assertEqual(verification["status"], "PASSPORT_VERIFIED")

    def test_verify_passport_missing_field(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        del p["schema_version"]
        verification = verify_passport(p)
        self.assertFalse(verification["valid"])
        self.assertIn("schema_version", str(verification["errors"]))

    def test_verify_passport_wrong_version(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        p["schema_version"] = "wrong_version"
        verification = verify_passport(p)
        self.assertFalse(verification["valid"])

    def test_verify_passport_tamper_hash(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        p["certificate_hash"] = "tampered"
        verification = verify_passport(p)
        self.assertEqual(verification["status"], "PASSPORT_TAMPERED")

    def test_verify_passport_forbidden_phrase(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        p["public_wording"] = "This is CERTIFIED_SAFE"
        verification = verify_passport(p)
        self.assertFalse(verification["valid"])
        self.assertIn("Forbidden overclaim phrase detected: CERTIFIED_SAFE", verification["errors"][0])

    def test_load_passport_from_file_valid(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        path = _make_temp_json(json.dumps(p))
        loaded = load_passport_from_file(path)
        self.assertEqual(loaded["passport_id"], p["passport_id"])

    def test_load_passport_from_file_missing(self):
        self.assertEqual(load_passport_from_file("/nonexistent.json"), {})

    def test_save_passport_to_file(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        path = _make_temp_json("{}")
        self.assertTrue(save_passport_to_file(p, path))
        with open(path) as fh:
            loaded = json.load(fh)
            self.assertEqual(loaded["passport_id"], p["passport_id"])

    def test_build_manifest(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        m = build_manifest(p, p.get("artifact_hashes", {}), p.get("evidence_packs", []))
        self.assertEqual(m["schema_version"], SCHEMA_VERSION)
        self.assertEqual(m["passport_id"], p["passport_id"])

class TestPassportBadges(unittest.TestCase):
    """Tests for badge determination, JSON generation, SVG generation."""

    def test_determine_badge_checked(self):
        self.assertEqual(determine_badge("PASSPORT_CHECKED", "EXPORT_NEEDS_REVIEW"), "CHECKED")

    def test_determine_badge_blocked(self):
        self.assertEqual(determine_badge("PASSPORT_BLOCKED", ""), "BLOCKED")

    def test_determine_badge_unverified(self):
        self.assertEqual(determine_badge("PASSPORT_CREATED", ""), "UNVERIFIED")

    def test_determine_badge_replayable(self):
        self.assertEqual(determine_badge("PASSPORT_REPLAY_MATCH", ""), "REPLAYABLE")

    def test_determine_badge_export_blocked(self):
        self.assertEqual(determine_badge("", "EXPORT_BLOCKED"), "BLOCKED")

    def test_determine_badge_export_unsupported(self):
        self.assertEqual(determine_badge("", "EXPORT_UNSUPPORTED"), "UNVERIFIED")

    def test_determine_badge_needs_review(self):
        self.assertEqual(determine_badge("PASSPORT_NEEDS_REVIEW", "EXPORT_NEEDS_REVIEW"), "NEEDS_REVIEW")

    def test_determine_badge_missing_evidence(self):
        self.assertEqual(determine_badge("PASSPORT_MISSING_EVIDENCE", ""), "MISSING_EVIDENCE")

    def test_generate_badge_json(self):
        b = generate_badge_json("art_001", "CHECKED", "All gates passed", "hash123")
        self.assertEqual(b["artifact_id"], "art_001")
        self.assertEqual(b["badge"], "CHECKED")
        self.assertEqual(b["passport_hash"], "hash123")

    def test_generate_badge_svg(self):
        svg = generate_badge_svg("CHECKED", "art_001")
        self.assertIn("Checked", svg)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_generate_badge_svg_all_types(self):
        for badge in ["UNVERIFIED", "CHECKED", "BLOCKED", "NEEDS_REVIEW", "REPLAYABLE", "MISSING_EVIDENCE", "EXTERNAL_REVIEW_PENDING"]:
            svg = generate_badge_svg(badge, "test")
            self.assertIn(badge.replace("_", " ").title(), svg)

class TestPassportExport(unittest.TestCase):
    """Tests for handoff pack generation."""

    def test_prepare_handoff_pack(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        b = result["badge"]
        with tempfile.TemporaryDirectory() as tmpdir:
            files = prepare_handoff_pack(p, b, tmpdir)
            self.assertIn("PASSPORT.json", files)
            self.assertIn("BADGE.json", files)
            self.assertIn("BADGE.svg", files)
            self.assertIn("LIMITATIONS.md", files)
            self.assertIn("REPLAY_COMMANDS.md", files)
            self.assertIn("PASSPORT_SUMMARY.md", files)
            self.assertIn("EVIDENCE_MANIFEST.json", files)
            self.assertIn("README_DESIGN_PASSPORT.md", files)
            self.assertIn("PASSPORT_SCHEMA.json", files)
            # Check README content has limitation
            readme_path = files["README_DESIGN_PASSPORT.md"]
            readme = open(readme_path).read()
            self.assertIn("does not prove", readme)

    def test_handoff_pack_reports(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        b = result["badge"]
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "report.html")
            with open(html_path, "w") as f:
                f.write("<html>test</html>")
            json_path = os.path.join(tmpdir, "report.json")
            with open(json_path, "w") as f:
                f.write(json.dumps({}))
            files = prepare_handoff_pack(p, b, tmpdir,
                                           html_report=html_path, json_report=json_path)
            self.assertIn("reports/_report.html", files)
            self.assertIn("reports/_report.json", files)

class TestPassportReport(unittest.TestCase):
    """Tests for JSON and HTML report generation."""

    def test_json_report_structure(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        report = generate_passport_json_report(result)
        data = json.loads(report)
        self.assertEqual(data["benchmark_name"], "designpassport_v0")
        self.assertIn("passport_id", data)
        self.assertIn("artifact_id", data)
        self.assertIn("gates_passed", data)
        self.assertIn("metrics", data)
        self.assertIn("limitation", data)

    def test_html_report_structure(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        html = generate_passport_html_report(result)
        self.assertIn("DTL Verified Design Passport", html)
        self.assertIn("<html", html)
        self.assertIn("</html>", html)
        self.assertIn("Gate Results", html)
        self.assertIn("Evidence Packs", html)
        self.assertIn("Certificate Hash", html)

    def test_html_report_badge_colors(self):
        for badge, expected_color in [
            ("CHECKED", "#4CAF50"), ("BLOCKED", "#F44336"),
            ("NEEDS_REVIEW", "#FF9800"), ("REPLAYABLE", "#2196F3"),
            ("UNVERIFIED", "#999999"), ("MISSING_EVIDENCE", "#FF5722"),
            ("EXTERNAL_REVIEW_PENDING", "#9C27B0"),
        ]:
            svg = generate_badge_svg(badge, "test")
            self.assertIn(expected_color, svg)

class TestPassportCLI(unittest.TestCase):
    """Tests CLI integration and demo flow."""

    def test_demo_run(self):
        result = run_demo()
        self.assertIn("passport", result)
        p = result["passport"]
        self.assertEqual(p["artifact_type"], "rtl")
        self.assertEqual(len(p["gates_run"]), 3)

    def test_demo_pipeline_with_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "demo_report.html")
            result = run_demo(output_html=html_path)
            self.assertIn("html_report", result)
            self.assertTrue(os.path.isfile(html_path))
    def test_verify_passport_file_integration(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        path = _make_temp_json(json.dumps(p))
        vr = verify_passport_file(path)
        self.assertTrue(vr["replay_match"])

    def test_verify_passport_file_missing_integration(self):
        vr = verify_passport_file("/nonexistent.json")
        self.assertEqual(vr["replay_match"], False)

    def test_export_badge_integration(self):
        result = build_passport(content=DEMO_RTL_SAFE)
        p = result["passport"]
        path = _make_temp_json(json.dumps(p))
        badge_out = export_badge_for_passport(path, os.path.dirname(path))
        self.assertNotIn("error", badge_out)
        self.assertEqual(badge_out["badge"], "CHECKED")

    def test_replay_integration(self):
        result = run_replay_for_artifact(
            artifact_id="replay_001",
            content=DEMO_RTL_SAFE,
        )
        self.assertIn("replay", result)
        self.assertTrue(result["replay"]["replay_match"])

def _make_temp(content: str = "") -> str:
    """Create a temp file, write content, return path, caller deletes."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False)
    f.write(content)
    return f.name
def _make_temp_py(content: str = "") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    f.write(content)
    return f.name
def _make_temp_json(content: str = "{}") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    f.write(content)
    return f.name
if __name__ == "__main__":
    unittest.main()
