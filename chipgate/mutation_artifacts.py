"""
ChipGate MutationBench — Evidence artifacts.

Creates JSON evidence packs for mutation results with SHA-256 hashes
for reproducibility and audit trails.

Does not guarantee silicon correctness, fabrication readiness,
timing signoff, physical safety, real power or real area.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .mutation_catalog import get_category


BENCHMARK_NAME = "ChipGate-MutationBench"
BENCHMARK_VERSION = __version__
PUBLIC_WORDING = (
    "ChipGate is a model-free benchmark that checks RTL structure and "
    "verification-gated safety patterns. "
    "It does not guarantee hardware correctness, silicon readiness, physical safety, "
    "regulatory conformance or experimental validity."
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_string(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return _sha256_bytes(p.read_bytes())


def create_mutation_evidence(
    seed_path: str,
    mutation_results: list,
    score_data: Dict[str, Any],
    toolchain_status: Optional[Dict] = None,
    commit_sha: str = "",
    workflow_name: str = "",
    run_id: str = "",
) -> Dict[str, Any]:
    """Create an evidence pack for a mutation bench run.

    Args:
        seed_path: Path to the seed design.
        mutation_results: List of dicts (from MutationResult.to_dict()).
        score_data: Dict from compute_mutation_score().
        toolchain_status: Optional toolchain info.
        commit_sha: Git commit SHA.
        workflow_name: CI workflow name.
        run_id: CI run ID.

    Returns:
        Evidence pack dict with all records and hashes.
    """
    seed_p = Path(seed_path)
    seed_id = seed_p.stem if seed_p.exists() else "unknown"
    seed_hash = _hash_file(seed_path)
    timestamp = datetime.now(timezone.utc).isoformat()

    records = []
    for mr in mutation_results:
        cert_payload = json.dumps({
            "seed_hash": seed_hash,
            "mutation_id": mr.get("mutation_id", ""),
            "category": mr.get("category", ""),
            "mutated_hash": mr.get("mutated_hash", ""),
            "detected": mr.get("detected", False),
            "escaped": mr.get("escaped", False),
        }, sort_keys=True)
        cert_hash = _sha256_string(cert_payload)

        records.append({
            "benchmark_name": BENCHMARK_NAME,
            "benchmark_version": BENCHMARK_VERSION,
            "seed_design_id": seed_id,
            "mutation_id": mr.get("mutation_id", ""),
            "mutation_category": mr.get("category", ""),
            "original_rtl_hash": mr.get("original_hash", ""),
            "mutated_rtl_hash": mr.get("mutated_hash", ""),
            "mutation_diff_hash": mr.get("diff_hash", ""),
            "chipgate_result": mr.get("detected", False),
            "blocking_statuses": mr.get("blocking_statuses", []),
            "detected_or_escaped": "DETECTED" if mr.get("detected") else "ESCAPED",
            "replay_command": f"python -m chipgate mutation --seed {seed_path} --generate 1",
            "certificate_hash": cert_hash,
            "public_wording": PUBLIC_WORDING,
        })

    total_hashes = len(records)
    pack_hash_input = json.dumps({
        "seed_id": seed_id,
        "seed_hash": seed_hash,
        "timestamp": timestamp,
        "records": [
            {k: v for k, v in r.items()
             if k != "public_wording"}
            for r in records
        ],
    }, sort_keys=True, default=str)
    pack_hash = _sha256_string(pack_hash_input)

    evidence = {
        "timestamp_utc": timestamp,
        "seed_design_id": seed_id,
        "seed_rtl_hash": seed_hash,
        "overall_status": score_data.get("overall_status", ""),
        "benchmark_name": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "toolchain_status": toolchain_status or {},
        "commit_sha": commit_sha,
        "workflow_name": workflow_name,
        "run_id": run_id,
        "evidence_records": records,
        "evidence_records_count": len(records),
        "total_hashes": total_hashes,
        "public_wording": PUBLIC_WORDING,
        "evidence_pack_hash": pack_hash[:32],
    }

    return evidence


def save_mutation_evidence(
    evidence: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """Save mutation evidence to a JSON file.

    Args:
        evidence: Dict from create_mutation_evidence().
        output_path: Optional file path. Defaults to mutation_evidence.json.

    Returns:
        Path to saved file.
    """
    if output_path is None:
        output_path = "mutation_evidence.json"
    p = Path(output_path)
    p.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return str(p)


def get_mutation_evidence_packs(ci_data: Dict) -> list:
    """Extract mutation evidence from CI data stages."""
    packs = []
    for stage in ci_data.get("stages", []):
        if "mutation" in stage.get("stage_name", "").lower():
            packs.append({
                "stage": stage.get("stage_name", ""),
                "status": stage.get("status", ""),
                "artifacts": stage.get("artifacts", []),
            })
    return packs