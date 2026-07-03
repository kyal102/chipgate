"""
ChipGate OpenLanePhysicalBench — Physical flow metrics and scoring.

Computes aggregate metrics and scores for the physical flow benchmark.
All metrics are structural/readiness metrics — they do not represent
real silicon performance, real power, real timing, or real area.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import statuses as st


@dataclass
class PhysicalMetrics:
    """Aggregate metrics for OpenLanePhysicalBench."""
    designs_tested: int = 0
    physical_configs_checked: int = 0
    openlane_config_pass_rate: float = 0.0
    openroad_run_pass_rate: float = 0.0
    drc_violation_count: int = 0
    lvs_mismatch_count: int = 0
    worst_negative_slack: float = 0.0
    cell_count: Optional[int] = None
    die_area_proxy: Optional[float] = None
    gds_artifact_count: int = 0
    artifact_hash_count: int = 0
    replay_match_rate: float = 0.0
    evidence_packs_created: int = 0
    toolchain_coverage: float = 0.0
    manual_review_items: int = 0

    def to_dict(self) -> dict:
        d = {
            "designs_tested": self.designs_tested,
            "physical_configs_checked": self.physical_configs_checked,
            "openlane_config_pass_rate": self.openlane_config_pass_rate,
            "openroad_run_pass_rate": self.openroad_run_pass_rate,
            "drc_violation_count": self.drc_violation_count,
            "lvs_mismatch_count": self.lvs_mismatch_count,
            "worst_negative_slack": self.worst_negative_slack,
            "gds_artifact_count": self.gds_artifact_count,
            "artifact_hash_count": self.artifact_hash_count,
            "replay_match_rate": self.replay_match_rate,
            "evidence_packs_created": self.evidence_packs_created,
            "toolchain_coverage": self.toolchain_coverage,
            "manual_review_items": self.manual_review_items,
        }
        if self.cell_count is not None:
            d["cell_count"] = self.cell_count
        if self.die_area_proxy is not None:
            d["die_area_proxy"] = self.die_area_proxy
        return d


def compute_toolchain_coverage(toolchain_report: Dict[str, Dict]) -> float:
    """Compute fraction of tools found vs checked.

    Args:
        toolchain_report: Dict of tool_name -> {"found": bool, ...}

    Returns:
        Float 0.0 to 1.0.
    """
    if not toolchain_report:
        return 0.0
    found = sum(1 for info in toolchain_report.values() if info.get("found", False))
    return found / len(toolchain_report)


def compute_config_pass_rate(config_results: List[Dict]) -> float:
    """Compute pass rate for OpenLane config checks.

    Args:
        config_results: List of {"status": "...", ...} dicts.

    Returns:
        Float 0.0 to 1.0.
    """
    if not config_results:
        return 0.0
    passed = sum(1 for r in config_results
                 if r.get("status") == st.OPENLANE_CONFIG_PASS)
    return passed / len(config_results)


def compute_openroad_pass_rate(run_results: List[Dict]) -> float:
    """Compute pass rate for OpenROAD run results.

    Args:
        run_results: List of {"status": "...", ...} dicts.

    Returns:
        Float 0.0 to 1.0.
    """
    if not run_results:
        return 0.0
    passed = sum(1 for r in run_results
                 if r.get("status") == st.OPENROAD_RUN_PASS)
    return passed / len(run_results) if run_results else 0.0


def compute_metrics_from_results(
    design_results: List[Dict],
    toolchain_report: Dict[str, Dict],
    evidence_packs: int = 0,
) -> PhysicalMetrics:
    """Compute aggregate metrics from design results and toolchain data.

    Args:
        design_results: List of per-design result dicts.
        toolchain_report: Dict from check_toolchain_status().
        evidence_packs: Number of evidence packs created.

    Returns:
        PhysicalMetrics with all computed values.
    """
    metrics = PhysicalMetrics()
    metrics.designs_tested = len(design_results)
    metrics.toolchain_coverage = compute_toolchain_coverage(toolchain_report)
    metrics.evidence_packs_created = evidence_packs

    # Config and run pass rates
    config_statuses = []
    run_statuses = []
    for d in design_results:
        cfg = d.get("openlane_config_status", "")
        if cfg:
            config_statuses.append({"status": cfg})
        run = d.get("openroad_run_status", "")
        if run:
            run_statuses.append({"status": run})

    metrics.physical_configs_checked = len(config_statuses)
    if config_statuses:
        passed = sum(1 for r in config_statuses
                     if r["status"] == st.OPENLANE_CONFIG_PASS)
        metrics.openlane_config_pass_rate = passed / len(config_statuses)
    if run_statuses:
        passed = sum(1 for r in run_statuses
                     if r["status"] == st.OPENROAD_RUN_PASS)
        metrics.openroad_run_pass_rate = passed / len(run_statuses)

    # DRC, LVS, timing aggregations
    for d in design_results:
        drc = d.get("drc_result", {})
        if drc:
            metrics.drc_violation_count += drc.get("violation_count", 0)
        lvs = d.get("lvs_result", {})
        if lvs:
            metrics.lvs_mismatch_count += lvs.get("mismatch_count", 0)
        timing = d.get("timing_result", {})
        if timing:
            wns = timing.get("worst_negative_slack", 0.0)
            if wns < metrics.worst_negative_slack:
                metrics.worst_negative_slack = wns
        gds = d.get("gds_result", {})
        if gds and gds.get("gds_found", False):
            metrics.gds_artifact_count += 1
        evidence = d.get("evidence_record", {})
        if evidence:
            metrics.artifact_hash_count += evidence.get("artifact_hash_count", 0)

    # Manual review items
    for d in design_results:
        ev = d.get("evidence_record", {})
        if ev:
            metrics.manual_review_items += len(ev.get("manual_review_items", []))

    return metrics