"""
JSONL adapter — reads external DTL proposal results from a JSONL file.

Each line of the JSONL file must be a JSON object with at least:
    {
        "case_id": "CG-BENCH-001",
        "proposal_id": "dtl-001",
        "proposed_rtl": "...",
        "proposal_source": "external_dtl",
        "reason": "...",
        "route_label": "..."
    }

This allows a private external DTL system to run outside the public
repository and export proposal results via a JSONL file, without
exposing any private code.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from .base import (
    BaseAdapter,
    ProposalInput,
    ProposalResult,
    register_adapter,
)


class JSONLAdapter(BaseAdapter):
    """
    Adapter that loads proposals from an external JSONL file.

    The JSONL file is a text file where each line is a JSON object
    representing a proposal for one benchmark case.

    This is the recommended way to feed external DTL results
    into the benchmark without exposing private internals.
    """

    def __init__(self, jsonl_path: str):
        """
        Args:
            jsonl_path: Path to the JSONL proposal file.
        """
        self._jsonl_path = jsonl_path
        self._proposals: Dict[str, dict] = {}
        self._adapter_name = "jsonl"
        self._adapter_version = "1.0.0"
        self._proposal_source = "jsonl"
        self._load(jsonl_path)

    def _load(self, path: str) -> None:
        """Load and index proposals from the JSONL file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"JSONL proposal file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Invalid JSON on line {line_num} of {path}: {e}"
                    )

                case_id = record.get("case_id")
                if not case_id:
                    continue

                self._proposals[case_id] = record

                # Infer proposal_source from first record if not set
                if self._proposal_source == "jsonl" and record.get("proposal_source"):
                    self._proposal_source = record["proposal_source"]

                # Infer adapter_name from first record if available
                if record.get("adapter_name"):
                    self._adapter_name = record["adapter_name"]
                if record.get("adapter_version"):
                    self._adapter_version = record["adapter_version"]

    @property
    def name(self) -> str:
        return self._adapter_name

    @property
    def version(self) -> str:
        return self._adapter_version

    @property
    def source_label(self) -> str:
        return self._proposal_source

    @property
    def loaded_case_ids(self) -> List[str]:
        """Return the list of case_ids loaded from the JSONL file."""
        return list(self._proposals.keys())

    @property
    def proposal_count(self) -> int:
        """Return the number of proposals loaded."""
        return len(self._proposals)

    def get_proposal(self, inp: ProposalInput) -> ProposalResult:
        """
        Look up the proposal for the given case_id in the JSONL file.

        If the case_id is not found, returns the rtl_before as an
        identity proposal with a warning reason.
        """
        record = self._proposals.get(inp.case_id)

        if record is None:
            return ProposalResult(
                proposal_id=f"{self._proposal_source}-{inp.case_id}-not-found",
                proposed_rtl=inp.rtl_before,
                proposal_source=self._proposal_source,
                adapter_name=self._adapter_name,
                adapter_version=self._adapter_version,
                reason=f"No proposal found for case {inp.case_id} in JSONL file — identity fallback",
                route_label="no_proposal",
            )

        return ProposalResult(
            proposal_id=record.get("proposal_id", f"{self._proposal_source}-{inp.case_id}"),
            proposed_rtl=record.get("proposed_rtl", inp.rtl_before),
            proposal_source=record.get("proposal_source", self._proposal_source),
            adapter_name=record.get("adapter_name", self._adapter_name),
            adapter_version=record.get("adapter_version", self._adapter_version),
            confidence=record.get("confidence"),
            route_label=record.get("route_label"),
            reason=record.get("reason"),
            metadata={k: v for k, v in record.items()
                      if k not in ("case_id", "proposal_id", "proposed_rtl",
                                   "proposal_source", "adapter_name", "adapter_version",
                                   "confidence", "route_label", "reason")},
        )