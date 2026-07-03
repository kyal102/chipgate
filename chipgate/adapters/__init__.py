"""
ChipGate adapter framework.

Provides a clean black-box boundary for benchmark proposal sources.
The public repository only knows: input case context -> adapter returns
candidate RTL + metadata. Private DTL internals stay outside
the public repo.

This is a boundary interface. Model-connected testing is future work.
"""

from .base import (
    ProposalInput,
    ProposalResult,
    BaseAdapter,
    ADAPTER_REGISTRY,
    register_adapter,
    get_adapter,
)

__all__ = [
    "ProposalInput",
    "ProposalResult",
    "BaseAdapter",
    "ADAPTER_REGISTRY",
    "register_adapter",
    "get_adapter",
]