"""
ChipGate RealToolchainCI — Artifact manifest and hashing.

Creates a CI artifact manifest with commit SHA, workflow info,
toolchain status, artifact hashes and evidence pack hashes.

Does not guarantee silicon correctness, fabrication readiness, timing
signoff, physical safety, real power or real area.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, statuses as st


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_string(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_file(path: str) -> Dict[str, str]:
    """Hash a single file, returning {path, sha256, size_bytes}."""
    p = Path(path)
    if not p.exists():
        return {"path": path, "sha256": "", "size_bytes": 0}
    data = p.read_bytes()
    return {
        "path": str(p),
        "sha256": _sha256_bytes(data),
        "size_bytes": len(data),
    }


def hash_string(label: str, content: str) -> Dict[str, str]:
    """Hash a string content, returning {label, sha256, size_bytes}."""
    data = content.encode("utf-8")
    return {
        "label": label,
        "sha256": _sha256_bytes(data),
        "size_bytes": len(data),
    }


def create_artifact_manifest(
    ci_result: Dict[str, Any],
    commit_sha: str = "",
    workflow_name: str = "",
    run_id: str = "",
) -> Dict[str, Any]:
    """Create a CI artifact manifest.

    Args:
        ci_result: Dict from CIResult.to_dict().
        commit_sha: Git commit SHA (if available).
        workflow_name: CI workflow name.
        run_id: CI run ID.

    Returns:
        Manifest dict with all CI metadata and hashes.
    """
    manifest = {
        "chipgate_version": __version__,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit_sha": commit_sha,
        "workflow_name": workflow_name,
        "run_id": run_id,
        "overall_status": ci_result.get("overall_status", ""),
        "mode": ci_result.get("mode", ""),
        "toolchain_status": ci_result.get("toolchain_status", {}),
        "python_tests_passed": ci_result.get("python_tests_passed", 0),
        "python_tests_failed": ci_result.get("python_tests_failed", 0),
        "toolchain_tools_found": ci_result.get("toolchain_tools_found", 0),
        "toolchain_tools_missing": ci_result.get("toolchain_tools_missing", 0),
        "public_wording": ci_result.get("public_wording", ""),
    }

    # Hash each stage output
    artifact_hashes = []
    for stage in ci_result.get("stages", []):
        output = stage.get("output", "")
        if output:
            h = hash_string(f"stage_{stage.get('stage_name', 'unknown')}", output)
            artifact_hashes.append(h)

    # Hash each demo result
    for demo in ci_result.get("demo_results", []):
        cmd_str = demo.get("command", "")
        if cmd_str:
            h = hash_string(f"demo_{cmd_str}", cmd_str)
            artifact_hashes.append(h)

    # Hash hygiene report
    hygiene_json = json.dumps(ci_result.get("hygiene", {}), sort_keys=True)
    if hygiene_json:
        h = hash_string("hygiene_report", hygiene_json)
        artifact_hashes.append(h)

    manifest["artifact_hashes"] = artifact_hashes
    manifest["hashes_created"] = len(artifact_hashes)

    # Self-hash
    manifest_str = json.dumps(manifest, sort_keys=True, default=str)
    manifest["manifest_hash"] = _sha256_string(manifest_str)[:32]

    return manifest


def get_ci_evidence_packs(ci_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract evidence pack information from CI results.

    Returns list of evidence-related dicts from stages.
    """
    packs = []
    for stage in ci_result.get("stages", []):
        if stage.get("artifacts"):
            packs.append({
                "stage": stage.get("stage_name", ""),
                "status": stage.get("status", ""),
                "artifacts": stage["artifacts"],
            })
    return packs


def get_formal_evidence_packs(ci_data: Dict) -> list:
    """Extract formal evidence records from CI data.

    Scans the stages list in *ci_data* for entries whose stage name contains "formal" and
    returns their evidence / artifacts information.
    """
    packs = []
    for stage in ci_data.get("stages", []):
        stage_name = stage.get("stage_name", "")
        if "formal" not in stage_name.lower():
            continue
        pack_info = {
            "stage": stage_name,
            "status": stage.get("status", ""),
            "artifacts": stage.get("artifacts"),
        }
        if stage.get("evidence_records"):
            pack_info["evidence_records"] = stage["evidence_records"]
        packs.append(pack_info)
    return packs