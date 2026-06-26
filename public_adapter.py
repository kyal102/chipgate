"""Public DesignGuard Adapter Interface.

This module defines the expected public interface for a DesignGuard adapter.
All methods raise NotImplementedError because this is a public interface
demonstration only and does not contain actual gate logic.
"""
from __future__ import annotations
from typing import Any, Dict


class PublicDesignGuardAdapter:
    """Public interface for the JARVI3 Chip DesignGuard adapter.

    This class shows the expected method signatures. Implementations
    are not provided here because this is a public interface only.
    Actual gate logic resides in the private ChipGate system.
    """

    def __init__(self) -> None:
        """Initialize the public DesignGuard adapter interface.

        Note: This is a public interface demonstration. The actual
        adapter implementation is part of the private ChipGate system.
        """

    def check(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a DesignGuard check request.

        Args:
            request: DesignGuard request dict following jarvi3.designguard.v0 schema.

        Returns:
            DesignGuard response dict following jarvi3.designguard.response.v0 schema.

        Raises:
            NotImplementedError: This is a public interface only.
        """
        raise NotImplementedError(
            "PublicDesignGuardAdapter.check() is a public interface signature. "
            "Actual gate logic is part of the private ChipGate system and is not "
            "included in this public demonstration package."
        )

    def get_status(self, request_id: str) -> Dict[str, Any]:
        """Retrieve the status of a previous DesignGuard check.

        Args:
            request_id: The request_id from a previous check call.

        Returns:
            Status dict for the requested check.

        Raises:
            NotImplementedError: This is a public interface only.
        """
        raise NotImplementedError(
            "PublicDesignGuardAdapter.get_status() is a public interface signature. "
            "Actual status retrieval is part of the private ChipGate system and is not "
            "included in this public demonstration package."
        )