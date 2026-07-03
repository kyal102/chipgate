"""
Example external DTL adapter.

This is an EXAMPLE FILE showing how to write an adapter that connects
to an external DTL system. It is NOT functional — it serves as a
template for users who want to integrate their own external DTL system.

To use:
    1. Copy this file to a private location (not committed to the public repo).
    2. Replace the get_proposal() logic with your actual DTL system call.
    3. Export results via JSONL using the jsonl_adapter, or import this
       adapter directly with the --adapter flag.

IMPORTANT:
    - Do NOT commit private DTL internals to the public repo.
    - Do NOT import from private repositories in public code.
    - Export proposals via JSONL to keep the public repo clean.
"""

from typing import List, Optional

from .base import BaseAdapter, ProposalInput, ProposalResult


class ExampleExternalDTLAdapter(BaseAdapter):
    """
    Example adapter for connecting to an external DTL system.

    This is a TEMPLATE, not a functional implementation.
    Replace get_proposal() with your actual DTL logic.
    """

    def __init__(self, dtl_endpoint: Optional[str] = None):
        """
        Args:
            dtl_endpoint: URL or path to the external DTL system.
                          Replace with your actual endpoint.
        """
        self._endpoint = dtl_endpoint or "http://localhost:8000/propose"
        # NOTE: In a real adapter, you would initialize your DTL client here.

    @property
    def name(self) -> str:
        return "example_external_dtl"

    @property
    def version(self) -> str:
        return "0.1.0-example"

    @property
    def source_label(self) -> str:
        return "external_dtl"

    def get_proposal(self, inp: ProposalInput) -> ProposalResult:
        """
        Generate a proposal using the external DTL system.

        REPLACE THIS with your actual DTL system call.
        This example just returns the rtl_before as-is.

        Example real implementation:
            1. Send inp to your DTL system via HTTP, subprocess, or Python API.
            2. Receive candidate RTL + metadata from the DTL system.
            3. Return a ProposalResult with the DTL's output.

        Example:
            response = requests.post(self._endpoint, json={
                "case_id": inp.case_id,
                "rtl_before": inp.rtl_before,
                "mutation_set": inp.mutation_set,
                "risk_level": inp.risk_level,
                "expected_gate_requirements": inp.expected_gate_requirements,
            })
            data = response.json()
            return ProposalResult(
                proposal_id=data["proposal_id"],
                proposed_rtl=data["proposed_rtl"],
                proposal_source="external_dtl",
                adapter_name=self.name,
                adapter_version=self.version,
                confidence=data.get("confidence"),
                route_label=data.get("route_label"),
                reason=data.get("reason"),
            )
        """
        # PLACEHOLDER: returns identity proposal
        return ProposalResult(
            proposal_id=f"example-dtl-{inp.case_id}",
            proposed_rtl=inp.rtl_before,
            proposal_source="external_dtl",
            adapter_name=self.name,
            adapter_version=self.version,
            reason="Example adapter — replace with actual DTL system call",
            route_label="placeholder",
        )

    def export_proposals_jsonl(
        self,
        inputs: List[ProposalInput],
        output_path: str,
    ) -> int:
        """
        Generate proposals for all inputs and write to a JSONL file.

        This is the recommended workflow:
            1. Run your DTL system offline.
            2. Export results to JSONL.
            3. Feed JSONL to the benchmark via jsonl_adapter.

        Args:
            inputs: List of case contexts.
            output_path: Path to write the JSONL file.

        Returns:
            Number of proposals written.
        """
        import json
        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for inp in inputs:
                proposal = self.get_proposal(inp)
                record = {
                    "case_id": inp.case_id,
                    "proposal_id": proposal.proposal_id,
                    "proposed_rtl": proposal.proposed_rtl,
                    "proposal_source": proposal.proposal_source,
                    "adapter_name": proposal.adapter_name,
                    "adapter_version": proposal.adapter_version,
                }
                if proposal.confidence is not None:
                    record["confidence"] = proposal.confidence
                if proposal.route_label:
                    record["route_label"] = proposal.route_label
                if proposal.reason:
                    record["reason"] = proposal.reason
                if proposal.metadata:
                    record["metadata"] = proposal.metadata
                f.write(json.dumps(record) + "\n")
                count += 1
        return count