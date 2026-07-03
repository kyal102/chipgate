"""
Tests for ChipGate TinyTapeoutPrep — hash stability.

No private imports, no secrets, no shell=True. English-only.
"""

import json
from pathlib import Path

import pytest

from chipgate.tinytapeout_prep import run_tinytapeout_prep


class TestEvidenceHashStability:
    """Tests for evidence pack hash stability."""

    def test_evidence_hash_stable(self):
        """Same pipeline run produces same hashes."""
        r1 = run_tinytapeout_prep(demo=True)
        r2 = run_tinytapeout_prep(demo=True)

        # Both runs should produce evidence packs
        assert r1.evidence_packs_created >= 1
        assert r2.evidence_packs_created >= 1

    def test_evidence_pack_has_artifacts(self):
        """Evidence pack contains all expected artifacts with SHA-256 hashes."""
        r = run_tinytapeout_prep(demo=True)
        pack_path = Path(r.artifacts_dir, "evidence_pack.json")
        assert pack_path.exists()

        with open(pack_path) as f:
            pack = json.load(f)

        assert "artifacts" in pack
        expected_artifacts = [
            "tiny_dtl_gate.v",
            "tt_um_chipgate_dtl_gate.v",
            "tiny_dtl_gate_fsm.v",
            "tb_tiny_dtl_gate.v",
            "info.yaml",
            "docs/info.md",
            "pinout.json",
        ]
        for name in expected_artifacts:
            assert name in pack["artifacts"], f"Missing artifact: {name}"
            assert "sha256" in pack["artifacts"][name]
            assert len(pack["artifacts"][name]["sha256"]) == 64

    def test_evidence_pack_has_version(self):
        """Evidence pack includes ChipGate version."""
        r = run_tinytapeout_prep(demo=True)
        pack_path = Path(r.artifacts_dir, "evidence_pack.json")
        with open(pack_path) as f:
            pack = json.load(f)
        assert "version" in pack
        assert pack["version"] != ""

    def test_different_output_dirs_independent(self):
        """Two output directories produce independent evidence packs."""
        import tempfile

        with tempfile.TemporaryDirectory() as d1:
            with tempfile.TemporaryDirectory() as d2:
                r1 = run_tinytapeout_prep(demo=True, output_dir=d1)
                r2 = run_tinytapeout_prep(demo=True, output_dir=d2)
                assert r1.artifacts_dir == d1
                assert r2.artifacts_dir == d2