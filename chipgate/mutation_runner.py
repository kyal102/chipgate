"""
ChipGate MutationBench — Mutation runner.

Takes seed designs, generates mutations, runs ChipGate scan on each,
and records detected/escaped status.

Does not guarantee silicon correctness, fabrication readiness,
timing signoff, physical safety, real power or real area.
"""

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, statuses as st
from .mutators import generate_mutations, apply_mutation, _sha256
from .scanner import scan_file
from .mutation_catalog import get_critical_categories, get_category


@dataclass
class MutationResult:
    """Result of scanning a single mutation."""
    mutation_id: str = ""
    category: str = ""
    original_hash: str = ""
    mutated_hash: str = ""
    diff_hash: str = ""
    detected: bool = False
    statuses: List[str] = field(default_factory=list)
    blocking_statuses: List[str] = field(default_factory=list)
    escaped: bool = False
    scan_duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mutation_id": self.mutation_id,
            "category": self.category,
            "original_hash": self.original_hash,
            "mutated_hash": self.mutated_hash,
            "diff_hash": self.diff_hash,
            "detected": self.detected,
            "statuses": self.statuses,
            "blocking_statuses": self.blocking_statuses,
            "escaped": self.escaped,
            "scan_duration_seconds": self.scan_duration_seconds,
        }


def run_mutation_scan(
    original_rtl: str,
    mutated_rtl: str,
    mutation_id: str,
    category: str,
    original_hash: str = "",
    diff_hash: str = "",
) -> MutationResult:
    """Run ChipGate scan on a mutated design and check detection.

    Args:
        original_rtl: Original safe RTL text.
        mutated_rtl: Mutated RTL text.
        mutation_id: Unique mutation identifier.
        category: Mutation category name.
        original_hash: SHA-32 hash of original RTL.
        diff_hash: SHA-32 hash of original+mutated.

    Returns:
        MutationResult with detection status.
    """
    result = MutationResult(
        mutation_id=mutation_id,
        category=category,
        original_hash=original_hash,
        mutated_hash=_sha256(mutated_rtl),
        diff_hash=diff_hash,
    )

    # Write mutated RTL to a temp file for scanning
    import tempfile
    suffix = ".v"
    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix, mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(mutated_rtl)
            tmp_path = f.name

        t0 = time.time()
        try:
            scan_result = scan_file(tmp_path)
        except Exception:
            scan_result = None
        duration = time.time() - t0

        if scan_result is not None:
            result.scan_duration_seconds = round(duration, 3)
            result.statuses = list(scan_result.statuses)

            # Check if any blocking/unsafe status was found
            blocking = [
                st.UNGATED_OUTPUT, st.KILL_SWITCH_MISSING,
                st.KILL_SWITCH_BYPASS, st.TIMEOUT_BYPASS,
                st.RESET_MISSING, st.UNSAFE_BYPASS_PATH,
                st.SAFE_STATE_VIOLATION, st.FAILSAFE_ESCAPED,
                st.UNSAFE_ACCEPTED, st.ASSERTION_MISSING,
                st.FAULT_DETECTED,
            ]
            for s in result.statuses:
                if s in st.FAIL_STATUSES or s in blocking:
                    result.detected = True
                    result.blocking_statuses.append(s)
                    break
            if not result.detected:
                # Check for private leak (hygiene-level)
                for s in result.statuses:
                    if "PRIVATE" in s.upper() or "LEAK" in s.upper():
                        result.detected = True
                        result.blocking_statuses.append(s)
                        break

        # Determine if this is an escape
        cat_meta = get_category(category)
        is_critical = cat_meta.get("must_detect", False)
        result.escaped = (not result.detected) and is_critical
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return result


def scan_seed_design(rtl_path: str) -> List[str]:
    """Scan a seed design and return its statuses for baseline."""
    try:
        result = scan_file(rtl_path)
        return list(result.statuses) if result else []
    except Exception:
        return []


def replay_mutation(
    original_rtl: str,
    mutated_rtl: str,
    original_path: str = "seed.v",
) -> Dict[str, Any]:
    """Check if replaying the scan produces the same result."""
    r1 = run_mutation_scan(
        original_rtl, mutated_rtl, "REPLAY_001", "replay",
    )
    r2 = run_mutation_scan(
        original_rtl, mutated_rtl, "REPLAY_002", "replay",
    )
    match = (
        r1.detected == r2.detected
        and set(r1.blocking_statuses) == set(r2.blocking_statuses)
    )
    return {
        "match": match,
        "replay_1": r1.blocking_statuses,
        "replay_2": r2.blocking_statuses,
    }