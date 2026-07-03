"""
ChipGate adapter base interface.

Defines the contract between the benchmark runner and proposal sources.
Every adapter receives a case context and returns a proposal with
candidate RTL and metadata. The public repo must not know how any
external DTL system works internally.

Adapter contract:
    Input:  ProposalInput (case_id, rtl_before, mutation_set, risk_level,
            expected_gate_requirements)
    Output: ProposalResult (proposal_id, proposed_rtl, proposal_source,
            adapter_name, adapter_version, confidence?, route_label?, reason?,
            metadata?)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Type alias for the mutation set — a list of (mutation_name, description) tuples.
MutationSet = List[tuple]


@dataclass
class ProposalInput:
    """
    Input to an adapter — describes the benchmark case context.

    Attributes:
        case_id: Unique benchmark case identifier (e.g. "UA-001").
        rtl_before: Baseline RTL before mutation (empty string if none).
        mutation_set: List of (mutation_name, description) tuples applied
                      to generate the proposed RTL.
        risk_level: Expected risk level ("critical", "high", "medium", "low").
        expected_gate_requirements: List of gate signals the design should have
                                   (e.g. ["verifier_ok", "policy_ok", "kill_switch"]).
    """
    case_id: str
    rtl_before: str
    mutation_set: MutationSet
    risk_level: str
    expected_gate_requirements: List[str] = field(default_factory=list)


@dataclass
class ProposalResult:
    """
    Output from an adapter — the proposed RTL and metadata.

    Attributes:
        proposal_id: Unique identifier for this proposal (e.g. "dtl-001").
        proposed_rtl: The candidate RTL string to evaluate.
        proposal_source: Source label (e.g. "synthetic", "jsonl", "external_dtl").
        adapter_name: Name of the adapter that produced this proposal.
        adapter_version: Version string of the adapter.
        confidence: Optional confidence score (0.0–1.0). Omitted if not applicable.
        route_label: Optional routing/decision label from the adapter
                     (e.g. "safety_gate_missing", "safe_to_proceed").
        reason: Optional human-readable reason for the adapter's decision.
        metadata: Optional additional metadata from the adapter.
    """
    proposal_id: str
    proposed_rtl: str
    proposal_source: str
    adapter_name: str
    adapter_version: str
    confidence: Optional[float] = None
    route_label: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """
    Abstract base class for benchmark adapters.

    Subclasses must implement:
        - name: Short identifier for the adapter.
        - version: Version string.
        - source_label: The proposal_source value (e.g. "synthetic", "external_dtl").
        - get_proposal(input: ProposalInput) -> ProposalResult

    The adapter is a black-box boundary. The public repository must not
    know how any external DTL system works internally.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this adapter."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string for this adapter."""
        ...

    @property
    @abstractmethod
    def source_label(self) -> str:
        """The proposal_source label (e.g. 'synthetic', 'external_dtl')."""
        ...

    @abstractmethod
    def get_proposal(self, inp: ProposalInput) -> ProposalResult:
        """
        Generate a proposal from the given case context.

        Args:
            inp: The benchmark case context.

        Returns:
            A ProposalResult with candidate RTL and metadata.
        """
        ...

    def get_proposals(self, inputs: List[ProposalInput]) -> List[ProposalResult]:
        """Generate proposals for a batch of inputs. Default: sequential."""
        return [self.get_proposal(inp) for inp in inputs]


# ── Adapter Registry ────────────────────────────────────────────────────────────

ADAPTER_REGISTRY: Dict[str, type] = {}


def register_adapter(cls: type) -> type:
    """Decorator to register an adapter class by its source_label."""
    instance = cls()
    ADAPTER_REGISTRY[instance.source_label] = cls
    return cls


def get_adapter(source_label: str) -> Optional[type]:
    """Look up a registered adapter class by source_label."""
    return ADAPTER_REGISTRY.get(source_label)