"""
ChipGate PPA (Performance-Power-Area) proxy aggregator.

Collects area, timing-depth, and power-toggle proxy results into
a unified PPA proxy report. Provides comparison and improvement
calculations.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from .area_proxy import (
    AreaProxyResult,
    compute_area_proxy,
    compute_area_proxy_from_rtl,
    area_improvement_percent,
)
from .timing_proxy import (
    TimingProxyResult,
    compute_timing_proxy,
    compute_timing_proxy_from_rtl,
    timing_improvement_percent,
)
from .power_proxy import (
    PowerProxyResult,
    compute_power_proxy,
    compute_power_proxy_from_rtl,
    power_improvement_percent,
)


@dataclass
class PPAProxyResult:
    """Unified PPA proxy result for a candidate."""
    file_path: str
    area: AreaProxyResult
    timing: TimingProxyResult
    power: PowerProxyResult

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "area_proxy": {
                "weighted_score": self.area.weighted_score,
                "raw_score": self.area.raw_score,
                "detail": self.area.detail,
            },
            "timing_depth_proxy": {
                "weighted_depth": self.timing.weighted_depth,
                "max_chain_depth": self.timing.max_chain_depth,
                "detail": self.timing.detail,
            },
            "power_toggle_proxy": {
                "weighted_power_proxy": self.power.weighted_power_proxy,
                "toggle_risk_score": self.power.toggle_risk_score,
                "detail": self.power.detail,
            },
        }


@dataclass
class PPAComparison:
    """Comparison of PPA proxy metrics between baseline and candidate."""
    candidate_id: str
    area_improvement_pct: float
    timing_improvement_pct: float
    power_improvement_pct: float
    area_status: str   # AREA_IMPROVED or AREA_REGRESSED
    timing_status: str  # TIMING_IMPROVED or TIMING_REGRESSED
    power_status: str   # POWER_PROXY_IMPROVED or POWER_PROXY_REGRESSED

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "area_improvement_pct": self.area_improvement_pct,
            "timing_improvement_pct": self.timing_improvement_pct,
            "power_improvement_pct": self.power_improvement_pct,
            "area_status": self.area_status,
            "timing_status": self.timing_status,
            "power_status": self.power_status,
        }


def compute_ppa(file_path: str) -> PPAProxyResult:
    """Compute all three PPA proxies for an RTL file."""
    return PPAProxyResult(
        file_path=file_path,
        area=compute_area_proxy(file_path),
        timing=compute_timing_proxy(file_path),
        power=compute_power_proxy(file_path),
    )


def compute_ppa_from_rtl(rtl_text: str, label: str = "inline") -> PPAProxyResult:
    """Compute all three PPA proxies from RTL text string."""
    return PPAProxyResult(
        file_path=label,
        area=compute_area_proxy_from_rtl(rtl_text, label),
        timing=compute_timing_proxy_from_rtl(rtl_text, label),
        power=compute_power_proxy_from_rtl(rtl_text, label),
    )


def compare_ppa(
    baseline: PPAProxyResult,
    candidate: PPAProxyResult,
    candidate_id: str,
) -> PPAComparison:
    """Compare candidate PPA against baseline."""
    from . import statuses as st

    area_pct = area_improvement_percent(
        baseline.area.weighted_score,
        candidate.area.weighted_score,
    )
    timing_pct = timing_improvement_percent(
        baseline.timing.weighted_depth,
        candidate.timing.weighted_depth,
    )
    power_pct = power_improvement_percent(
        baseline.power.weighted_power_proxy,
        candidate.power.weighted_power_proxy,
    )

    area_status = st.AREA_IMPROVED if area_pct > 0 else st.AREA_REGRESSED
    timing_status = st.TIMING_IMPROVED if timing_pct > 0 else st.TIMING_REGRESSED
    power_status = st.POWER_PROXY_IMPROVED if power_pct > 0 else st.POWER_PROXY_REGRESSED

    return PPAComparison(
        candidate_id=candidate_id,
        area_improvement_pct=area_pct,
        timing_improvement_pct=timing_pct,
        power_improvement_pct=power_pct,
        area_status=area_status,
        timing_status=timing_status,
        power_status=power_status,
    )