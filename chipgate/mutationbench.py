"""
ChipGate MutationBench — Main orchestration module.

Stress-tests ChipGate by attacking safe RTL with thousands of unsafe
mutations and bypass attempts. Measures detection rates per category,
identifies escaped mutations for rule hardening, and creates evidence
artifacts with full SHA-256 audit trails.

Does not guarantee silicon correctness, fabrication readiness,
timing signoff, physical safety, real power or real area.
"""

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, statuses as st
from .mutators import generate_mutations, get_mutation_names, _sha256
from .mutation_catalog import (
    get_critical_categories, list_categories, get_category,
)
from .mutation_runner import run_mutation_scan, scan_seed_design, MutationResult
from .mutation_score import compute_mutation_score
from .mutation_artifacts import create_mutation_evidence, save_mutation_evidence
from .mutation_report import generate_mutation_html as _gen_html
from .scanner import scan_file


# ── Paths ───────────────────────────────────────────────────────────

BENCHMARK_DIR = str(Path(__file__).parent.parent / "benchmarks" / "mutationbench_v0")
SEEDS_DIR = str(Path(BENCHMARK_DIR) / "seeds")
GENERATED_DIR = str(Path(BENCHMARK_DIR) / "generated")
FIXTURES_DIR = str(Path(BENCHMARK_DIR) / "fixtures")
REPORTS_DIR = str(Path(BENCHMARK_DIR) / "reports")

DEFAULT_SEED = str(Path(SEEDS_DIR) / "safe_dtl_gate.v")
DEFAULT_COUNT = 1000

PUBLIC_WORDING = st.MUTATIONBENCH_PUBLIC_WORDING
LIMITATION = st.MUTATIONBENCH_LIMITATION


# ── Result dataclass ───────────────────────────────────────────────────────

@dataclass
class MutationBenchResult:
    """Top-level MutationBench result."""
    overall_status: str = ""
    timestamp_utc: str = ""
    benchmark_name: str = "ChipGate-MutationBench"
    benchmark_version: str = __version__
    mode: str = "mutation"
    seed_designs_tested: int = 0
    seed_designs_safe: int = 0
    toolchain_status: Dict[str, Any] = field(default_factory=dict)
    mutation_results: List[Dict[str, Any]] = field(default_factory=list)
    escaped_mutations: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    classification: Dict[str, Any] = field(default_factory=dict)
    review_items: List[str] = field(default_factory=list)
    public_wording: str = PUBLIC_WORDING
    limitation: str = LIMITATION
    artifact_hashes: List[Dict[str, str]] = field(default_factory=list)
    evidence_packs_created: int = 0

    def to_dict(self) -> dict:
        return {
            "overall_status": self.overall_status,
            "timestamp_utc": self.timestamp_utc,
            "benchmark_name": self.benchmark_name,
            "benchmark_version": self.benchmark_version,
            "mode": self.mode,
            "seed_designs_tested": self.seed_designs_tested,
            "seed_designs_safe": self.seed_designs_safe,
            "toolchain_status": self.toolchain_status,
            "mutation_results": self.mutation_results,
            "escaped_mutations": self.escaped_mutations,
            "metrics": self.metrics,
            "classification": self.classification,
            "review_items": self.review_items,
            "public_wording": self.public_wording,
            "limitation": self.limitation,
            "artifact_hashes": self.artifact_hashes,
            "evidence_packs_created": self.evidence_packs_created,
        }


# ── Public API ────────────────────────────────────────────────────────────

def list_mutators() -> list:
    """List all available mutation categories.

    Returns list of dicts with keys: name, description, criticality, group.
    """
    return list_categories()


def run_mutation_bench(
    demo: bool = False,
    benchmark_path: Optional[str] = None,
    seed: Optional[str] = None,
    count: int = DEFAULT_COUNT,
    generate_only: bool = False,
) -> MutationBenchResult:
    """Run the MutationBench pipeline.

    Args:
        demo: If True, use built-in seeds with default count.
        benchmark_path: Path to a benchmark directory.
        seed: Path to a single seed design file.
        count: Number of mutations to generate.
        generate_only: If True, only generate and save mutations, skip scanning.

    Returns:
        MutationBenchResult with all results.
    """
    result = MutationBenchResult(
        timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        mode="demo" if demo else "benchmark",
        public_wording=PUBLIC_WORDING,
        limitation=LIMITATION,
    )

    # ── Step 1: Find seed designs ──────────────────────────────────────
    seed_files = _find_seeds(demo, benchmark_path, seed)

    if not seed_files:
        result.overall_status = st.MUTATIONBENCH_FAIL
        result.metrics["mutations_generated"] = 0
        return result

    # Verify seed designs are safe
    for sf in seed_files:
        try:
            scan_result = scan_file(sf)
            result.seed_designs_tested += 1
            is_safe = all(s not in st.FAIL_STATUSES for s in scan_result.statuses)
            if is_safe:
                result.seed_designs_safe += 1
        except Exception:
            result.seed_designs_tested += 1

    # ── Step 2: Generate mutations ────────────────────────────────────
    all_mutations = []
    all_results = []
    for seed_path in seed_files:
        try:
            rtl_text = Path(seed_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        mutations = generate_mutations(
            rtl_text,
            count=count,
            seed=hash(seed_path) if seed is None else hash(seed),
        )
        all_mutations.extend(mutations)

    if generate_only:
        # Save generated mutations and return
        _save_mutations(all_mutations, GENERATED_DIR)
        result.metrics["mutations_generated"] = len(all_mutations)
        result.overall_status = st.MUTATION_GENERATED
        return result

    # ── Step 3: Scan each mutation ───────────────────────────────────
    for mut in all_mutations:
        mr = run_mutation_scan(
            original_rtl="",
            mutated_rtl=mut.mutated_text,
            mutation_id=mut.mutation_id,
            category=mut.category,
            original_hash=mut.original_hash,
            diff_hash=mut.diff_hash,
        )
        mr_dict = mr.to_dict()
        all_results.append(mr_dict)

        # Track escaped mutations
        if mr.escaped:
            result.escaped_mutations.append({
                "mutation_id": mr.mutation_id,
                "category": mr.category,
                "detected": mr.detected,
                "blocking_statuses": mr.blocking_statuses,
                "mutated_hash": mr.mutated_hash,
            })

    result.mutation_results = all_results

    # ── Step 4: Compute scores ─────────────────────────────────────
    score = compute_mutation_score(
        results=[MutationResult(**r) for r in all_results],
        seed_designs_tested=result.seed_designs_tested,
        seed_designs_safe=result.seed_designs_safe,
    )

    result.overall_status = score["overall_status"]
    result.metrics = score["metrics"]
    result.classification = score["classification"]
    result.review_items = score["review_items"]

    # ── Step 5: Generate artifact hashes ───────────────────────────
    for mr_dict in all_results:
        h = _sha256(json.dumps(mr_dict, sort_keys=True, default=str))
        result.artifact_hashes.append({
            "label": f"mutation_{mr_dict.get('mutation_id', '')}",
            "sha256": h,
            "size_bytes": len(json.dumps(mr_dict, default=str)),
        })

    # Update metrics with artifact counts
    result.metrics["artifact_hash_count"] = len(result.artifact_hashes)
    result.metrics["evidence_packs_created"] = result.evidence_packs_created

    # ── Step 6: Create evidence pack ─────────────────────────────────
    for sf in seed_files:
        ev = create_mutation_evidence(
            seed_path=sf,
            mutation_results=[r for r in all_results
                             if Path(sf).stem in r.get("mutation_id", "") or True],
            score_data=score,
        )
        path = save_mutation_evidence(ev)
        result.evidence_packs_created += 1

    return result


def generate_mutation_count(
    count: int,
    categories: Optional[List[str]] = None,
    seed_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate mutations and save them. Returns list of mutation dicts."""
    seed_path = seed_path or DEFAULT_SEED
    try:
        rtl_text = Path(seed_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    mutations = generate_mutations(rtl_text, count=count, categories=categories)
    _save_mutations(mutations, GENERATED_DIR)

    return [m.to_dict() for m in mutations]


# ── Internal helpers ─────────────────────────────────────────────────────

def _find_seeds(
    demo: bool,
    benchmark_path: Optional[str],
    seed: Optional[str],
) -> List[str]:
    """Find seed design files."""
    if seed and Path(seed).exists():
        return [seed]

    seed_dir = SEEDS_DIR
    if benchmark_path:
        seed_dir = str(Path(benchmark_path) / "seeds")

    if not Path(seed_dir).is_dir():
        return []

    files = sorted(Path(seed_dir).glob("*.v"))
    return [str(f) for f in files]


def _save_mutations(mutations: list, output_dir: str) -> None:
    """Save mutation variants to output directory."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for mut in mutations:
        name = f"{mut.category}_{mut.mutation_id}.v"
        path = Path(output_dir) / name
        path.write_text(mut.mutated_text, encoding="utf-8")