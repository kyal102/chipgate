"""
ChipGate verification cost model.

Provides a transparent, deterministic cost model for estimating
verification workload under the synthetic benchmark. All costs are in
abstract "verification-cost units" and do not represent real-world
monetary cost, GPU time, or EDA cloud fees.

This is a workflow-level cost model applied to synthetic RTL proposals,
not a measured model-connected benchmark.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CostTier:
    """A single cost tier in the verification pipeline."""
    name: str
    cost_units: int
    description: str


# ── Default Cost Tiers ────────────────────────────────────────────────────────
# These are benchmark cost units, not measured silicon performance,
# GPU performance or real EDA cloud cost.

COST_TIERS: Dict[str, CostTier] = {
    "dtl_scan": CostTier(
        name="DTL Scan (cheap gate)",
        cost_units=1,
        description="Deterministic RTL structure and safety-gate pattern check",
    ),
    "lint": CostTier(
        name="Lint",
        cost_units=5,
        description="Verilog/SystemVerilog lint via Verilator or equivalent",
    ),
    "simulation": CostTier(
        name="Simulation",
        cost_units=25,
        description="RTL simulation via Verilator, cocotb or equivalent",
    ),
    "formal": CostTier(
        name="Formal Verification",
        cost_units=100,
        description="Formal property checking via SymbiYosys/SBY",
    ),
    "synthesis": CostTier(
        name="Synthesis",
        cost_units=250,
        description="RTL synthesis via Yosys or equivalent",
    ),
}


def tier_cost(name: str) -> int:
    """Return the cost in units for a given verification tier."""
    tier = COST_TIERS.get(name)
    if tier is None:
        raise ValueError(f"Unknown cost tier: {name}")
    return tier.cost_units


def baseline_cost(num_cases: int) -> int:
    """
    Calculate the baseline (ungated) workflow cost.

    Every case goes through lint + simulation + formal + synthesis.
    """
    return num_cases * (
        tier_cost("lint")
        + tier_cost("simulation")
        + tier_cost("formal")
        + tier_cost("synthesis")
    )


def dtl_gated_cost(num_dtl_pass: int, num_dtl_fail: int) -> int:
    """
    Calculate the DTL-gated workflow cost.

    All cases get cheap DTL scan first.
    Cases that pass DTL proceed to heavier checks.
    Cases that fail DTL are blocked (no heavy checks).
    """
    total_dtl = num_dtl_pass + num_dtl_fail
    dtl_scan_cost = total_dtl * tier_cost("dtl_scan")
    heavy_check_cost = num_dtl_pass * (
        tier_cost("lint")
        + tier_cost("simulation")
        + tier_cost("formal")
        + tier_cost("synthesis")
    )
    return dtl_scan_cost + heavy_check_cost


def speedup_ratio(baseline: int, gated: int) -> float:
    """
    Calculate the estimated verification-cost reduction ratio.

    This is an estimated ratio under the synthetic benchmark cost model,
    not a measured real-world speedup.

    Returns 0.0 if gated cost is 0 to avoid division by zero.
    """
    if gated == 0:
        return 0.0
    return baseline / gated


def cost_per_verified_accepted(gated_cost: int, accepted_count: int) -> float:
    """Cost per verified accepted design change."""
    if accepted_count == 0:
        return float("inf")
    return gated_cost / accepted_count


def format_cost_report(
    num_cases: int,
    num_blocked: int,
    num_passed_heavy: int,
    num_accepted: int,
) -> Dict:
    """Generate a structured cost comparison report."""
    bl = baseline_cost(num_cases)
    gc = dtl_gated_cost(num_passed_heavy, num_blocked)
    sr = speedup_ratio(bl, gc)
    cpv = cost_per_verified_accepted(gc, num_accepted)
    pct_avoided = ((bl - gc) / bl * 100) if bl > 0 else 0.0

    return {
        "total_cases": num_cases,
        "cases_blocked_by_dtl": num_blocked,
        "cases_sent_to_heavy_check": num_passed_heavy,
        "cases_accepted": num_accepted,
        "baseline_cost_units": bl,
        "dtl_gated_cost_units": gc,
        "cost_units_saved": bl - gc,
        "pct_reduction": round(pct_avoided, 1),
        "speedup_ratio": round(sr, 2),
        "cost_per_verified_accepted": round(cpv, 2),
        "cost_model": {
            "dtl_scan": tier_cost("dtl_scan"),
            "lint": tier_cost("lint"),
            "simulation": tier_cost("simulation"),
            "formal": tier_cost("formal"),
            "synthesis": tier_cost("synthesis"),
        },
        "disclaimer": (
            "These are benchmark cost units, not measured silicon performance, "
            "GPU performance or real EDA cloud cost."
        ),
    }


# ── Mode-Specific Cost Calculations ────────────────────────────────────────────

def ungated_mode_cost(num_cases: int) -> int:
    """
    Cost for ungated_baseline mode.

    Every case goes through the full heavy pipeline (lint + simulation
    + formal + synthesis). No gate filtering.
    """
    return baseline_cost(num_cases)


def chipgate_only_mode_cost(
    num_cases: int,
    num_blocked: int,
    num_to_heavy: int,
) -> int:
    """
    Cost for chipgate_only mode.

    All cases get a cheap ChipGate scan (1 unit each).
    Blocked cases stop here. Passed cases go to heavy checks.
    """
    scan_cost = num_cases * tier_cost("dtl_scan")
    heavy_cost = num_to_heavy * (
        tier_cost("lint")
        + tier_cost("simulation")
        + tier_cost("formal")
        + tier_cost("synthesis")
    )
    return scan_cost + heavy_cost


def external_dtl_mode_cost(
    num_cases: int,
    num_dtl_blocked: int,
    num_chipgate_blocked: int,
    num_to_heavy: int,
    adapter_scan_cost: int = 1,
) -> int:
    """
    Cost for external_dtl mode.

    All cases get an adapter pass (default 1 unit, same as DTL scan).
    Then ChipGate scans non-blocked cases.
    Cases blocked by either stop. Remaining go to heavy checks.

    This is the full pipeline:
        adapter_pass (all) + chipgate_scan (non-adapter-blocked) + heavy (remaining)
    """
    adapter_cost = num_cases * adapter_scan_cost
    chipgate_scanned = num_cases - num_dtl_blocked
    chipgate_cost = chipgate_scanned * tier_cost("dtl_scan")
    heavy_cost = num_to_heavy * (
        tier_cost("lint")
        + tier_cost("simulation")
        + tier_cost("formal")
        + tier_cost("synthesis")
    )
    return adapter_cost + chipgate_cost + heavy_cost


def mode_cost(
    mode: str,
    num_cases: int,
    num_blocked: int = 0,
    num_to_heavy: int = 0,
    num_dtl_blocked: int = 0,
) -> int:
    """
    Calculate cost for a given benchmark mode.

    Args:
        mode: One of "ungated_baseline", "chipgate_only", "external_dtl".
        num_cases: Total number of benchmark cases.
        num_blocked: Total cases blocked by the gate (chipgate_only mode).
        num_to_heavy: Cases that proceed to heavy verification.
        num_dtl_blocked: Cases blocked by the external DTL adapter (external_dtl mode).

    Returns:
        Estimated cost in verification-cost units.
    """
    if mode == "ungated_baseline":
        return ungated_mode_cost(num_cases)
    elif mode == "chipgate_only":
        return chipgate_only_mode_cost(
            num_cases, num_blocked, num_to_heavy
        )
    elif mode == "external_dtl":
        return external_dtl_mode_cost(
            num_cases, num_dtl_blocked, num_blocked, num_to_heavy
        )
    else:
        raise ValueError(f"Unknown benchmark mode: {mode}")


VALID_MODES = ["ungated_baseline", "chipgate_only", "external_dtl"]


def format_mode_cost_report(
    mode: str,
    num_cases: int,
    unsafe_blocked: int,
    safe_accepted: int,
    safe_rejected: int,
    num_dtl_blocked: int = 0,
    adapter_name: str = "",
    proposal_source: str = "",
) -> Dict:
    """
    Generate a structured cost report for a single benchmark mode.

    Returns a dict with all cost metrics and disclaimers.
    """
    num_to_heavy = safe_accepted + safe_rejected
    num_total_blocked = unsafe_blocked + safe_rejected  # gate-level blocks

    if mode == "ungated_baseline":
        total_cost = ungated_mode_cost(num_cases)
        heavy_required = num_cases
        heavy_avoided = 0
    elif mode == "chipgate_only":
        total_cost = chipgate_only_mode_cost(num_cases, unsafe_blocked, num_to_heavy)
        heavy_required = num_to_heavy
        heavy_avoided = unsafe_blocked
    elif mode == "external_dtl":
        total_cost = external_dtl_mode_cost(
            num_cases, num_dtl_blocked, unsafe_blocked, num_to_heavy
        )
        heavy_required = num_to_heavy
        heavy_avoided = num_cases - num_to_heavy
    else:
        raise ValueError(f"Unknown mode: {mode}")

    bl = ungated_mode_cost(num_cases)
    cpv = cost_per_verified_accepted(total_cost, safe_accepted)

    report = {
        "benchmark_mode": mode,
        "adapter_name": adapter_name or "(none)",
        "proposal_source": proposal_source or "built-in synthetic",
        "total_cases": num_cases,
        "unsafe_blocked": unsafe_blocked,
        "unsafe_accepted": 0,  # will be filled by caller if applicable
        "safe_accepted": safe_accepted,
        "safe_rejected": safe_rejected,
        "dtl_adapter_blocked": num_dtl_blocked,
        "heavy_checks_required": heavy_required,
        "heavy_checks_avoided": heavy_avoided,
        "ungated_baseline_cost_units": bl,
        "mode_cost_units": total_cost,
        "cost_units_saved_vs_baseline": bl - total_cost,
        "pct_reduction_vs_baseline": round(((bl - total_cost) / bl * 100), 1) if bl > 0 else 0.0,
        "estimated_cost_per_verified_accepted_change": round(cpv, 2),
        "cost_model_tiers": {
            "dtl_scan": tier_cost("dtl_scan"),
            "lint": tier_cost("lint"),
            "simulation": tier_cost("simulation"),
            "formal": tier_cost("formal"),
            "synthesis": tier_cost("synthesis"),
        },
        "disclaimer": (
            "These are estimated verification-cost units under the synthetic "
            "benchmark cost model. They do not represent real-world EDA cost, "
            "GPU time, or monetary cost."
        ),
    }
    return report