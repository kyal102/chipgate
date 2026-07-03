"""
Synthetic adapter — wraps the built-in benchmark cases.

This adapter simply returns the rtl_after from each BenchCase as the
proposed RTL, with "synthetic" as the proposal source. It is the
default adapter for model-free benchmarking.

No AI model is involved. Proposals are mutation-generated from templates.
"""

from typing import List

from .base import (
    BaseAdapter,
    ProposalInput,
    ProposalResult,
    register_adapter,
)
from ..bench_cases import BenchCase


@register_adapter
class SyntheticAdapter(BaseAdapter):
    """
    Adapter that returns the built-in synthetic RTL proposals.

    This is the default adapter for the model-free benchmark.
    It does not involve any AI model — proposals are mutation-generated
    from templates defined in bench_cases.py.
    """

    @property
    def name(self) -> str:
        return "synthetic"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def source_label(self) -> str:
        return "synthetic"

    def get_proposal(self, inp: ProposalInput) -> ProposalResult:
        """
        Return a synthetic proposal for the given case.

        For the synthetic adapter, we need the original BenchCase to
        get the rtl_after. This method uses the case_id to look up
        the case from generate_all_cases().
        """
        from ..bench_cases import generate_all_cases

        cases_by_id = {c.case_id: c for c in generate_all_cases()}
        case = cases_by_id.get(inp.case_id)

        if case is None:
            # If case not found, return the rtl_before as-is (identity)
            return ProposalResult(
                proposal_id=f"synthetic-{inp.case_id}",
                proposed_rtl=inp.rtl_before,
                proposal_source="synthetic",
                adapter_name=self.name,
                adapter_version=self.version,
                reason="Case not found in synthetic set — identity proposal",
            )

        return ProposalResult(
            proposal_id=f"synthetic-{case.case_id}",
            proposed_rtl=case.rtl_after,
            proposal_source="synthetic",
            adapter_name=self.name,
            adapter_version=self.version,
            reason=case.reason,
            metadata={
                "category": case.category,
                "risk_level": case.risk_level,
                "expected_gate_result": case.expected_gate_result,
            },
        )

    def get_proposals_for_cases(self, cases: List[BenchCase]) -> List[ProposalResult]:
        """Convenience method: generate proposals directly from BenchCase objects."""
        results = []
        for case in cases:
            inp = ProposalInput(
                case_id=case.case_id,
                rtl_before=case.rtl_before,
                mutation_set=[(case.category, case.reason)],
                risk_level=case.risk_level,
            )
            results.append(self.get_proposal(inp))
        return results