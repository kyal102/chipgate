"""
ChipGate design score calculator.

Computes a safe_improvement_score for RTL candidates. A candidate can
only rank as "improved" if it passes safety, longevity, and no-regression
checks. Then it is ranked by weighted PPA improvements minus verification
cost penalty.

Unsafe designs CANNOT rank above safe designs even if they look
smaller or faster.
"""

from dataclasses import dataclass
from typing import Optional

from . import statuses as st


# Weights for PPA improvement components
AREA_WEIGHT = 0.35
TIMING_WEIGHT = 0.35
POWER_WEIGHT = 0.30

# Verification cost penalty per unit
COST_PENALTY_FACTOR = 0.001


@dataclass
class DesignScore:
    """Design score result for a candidate."""
    candidate_id: str
    safety_pass: bool
    longevity_pass: bool
    no_regression_pass: bool
    area_improvement_pct: float
    timing_improvement_pct: float
    power_improvement_pct: float
    estimated_verification_cost: int
    safe_improvement_score: float
    can_rank: bool
    is_best_tradeoff: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "safety_pass": self.safety_pass,
            "longevity_pass": self.longevity_pass,
            "no_regression_pass": self.no_regression_pass,
            "area_improvement_pct": self.area_improvement_pct,
            "timing_improvement_pct": self.timing_improvement_pct,
            "power_improvement_pct": self.power_improvement_pct,
            "estimated_verification_cost": self.estimated_verification_cost,
            "safe_improvement_score": round(self.safe_improvement_score, 4),
            "can_rank": self.can_rank,
            "is_best_tradeoff": self.is_best_tradeoff,
            "reason": self.reason,
        }


def compute_design_score(
    candidate_id: str,
    safety_pass: bool,
    longevity_pass: bool,
    no_regression_pass: bool,
    area_improvement_pct: float,
    timing_improvement_pct: float,
    power_improvement_pct: float,
    estimated_verification_cost: int = 0,
) -> DesignScore:
    """
    Compute the safe_improvement_score for a candidate.

    A candidate can only be ranked as improved if ALL of:
      - safety_pass = True
      - longevity_pass = True
      - no_regression_pass = True

    The score is then:
      weighted(area + timing + power improvement) - cost penalty

    Unsafe/failed candidates get score = -infinity (cannot rank).
    """
    can_rank = safety_pass and longevity_pass and no_regression_pass

    if not can_rank:
        # Determine the reason for disqualification
        reasons = []
        if not safety_pass:
            reasons.append("safety check failed")
        if not longevity_pass:
            reasons.append("longevity check failed")
        if not no_regression_pass:
            reasons.append("regression detected")
        reason = "; ".join(reasons)

        return DesignScore(
            candidate_id=candidate_id,
            safety_pass=safety_pass,
            longevity_pass=longevity_pass,
            no_regression_pass=no_regression_pass,
            area_improvement_pct=area_improvement_pct,
            timing_improvement_pct=timing_improvement_pct,
            power_improvement_pct=power_improvement_pct,
            estimated_verification_cost=estimated_verification_cost,
            safe_improvement_score=float("-inf"),
            can_rank=False,
            reason=reason,
        )

    # Compute weighted improvement score
    weighted_improvement = (
        AREA_WEIGHT * max(area_improvement_pct, 0)
        + TIMING_WEIGHT * max(timing_improvement_pct, 0)
        + POWER_WEIGHT * max(power_improvement_pct, 0)
    )

    # Apply cost penalty
    cost_penalty = estimated_verification_cost * COST_PENALTY_FACTOR

    score = weighted_improvement - cost_penalty

    # Determine improvement type description
    improvements = []
    if area_improvement_pct > 0:
        improvements.append(f"area {area_improvement_pct}%")
    if timing_improvement_pct > 0:
        improvements.append(f"timing {timing_improvement_pct}%")
    if power_improvement_pct > 0:
        improvements.append(f"power {power_improvement_pct}%")

    reason = "Improvements: " + ", ".join(improvements) if improvements else "No PPA improvement"

    return DesignScore(
        candidate_id=candidate_id,
        safety_pass=safety_pass,
        longevity_pass=longevity_pass,
        no_regression_pass=no_regression_pass,
        area_improvement_pct=area_improvement_pct,
        timing_improvement_pct=timing_improvement_pct,
        power_improvement_pct=power_improvement_pct,
        estimated_verification_cost=estimated_verification_cost,
        safe_improvement_score=round(score, 4),
        can_rank=True,
        reason=reason,
    )


def rank_candidates(scores: list) -> list:
    """
    Rank candidates by safe_improvement_score.

    Rules:
    - Only candidates with can_rank=True are eligible for ranking.
    - Unsafe candidates (can_rank=False) are placed at the bottom.
    - Among eligible candidates, higher score = better rank.
    - The top eligible candidate is marked as best_tradeoff.
    """
    eligible = [s for s in scores if s.can_rank]
    ineligible = [s for s in scores if not s.can_rank]

    # Sort eligible by score descending
    eligible.sort(key=lambda s: s.safe_improvement_score, reverse=True)

    # Mark best tradeoff
    if eligible:
        # Create new list with is_best_tradeoff flag
        ranked = []
        for i, s in enumerate(eligible):
            ds = DesignScore(
                candidate_id=s.candidate_id,
                safety_pass=s.safety_pass,
                longevity_pass=s.longevity_pass,
                no_regression_pass=s.no_regression_pass,
                area_improvement_pct=s.area_improvement_pct,
                timing_improvement_pct=s.timing_improvement_pct,
                power_improvement_pct=s.power_improvement_pct,
                estimated_verification_cost=s.estimated_verification_cost,
                safe_improvement_score=s.safe_improvement_score,
                can_rank=s.can_rank,
                is_best_tradeoff=(i == 0),
                reason=s.reason,
            )
            ranked.append(ds)
    else:
        ranked = eligible

    # Append ineligible at the bottom
    ranked.extend(ineligible)

    return ranked