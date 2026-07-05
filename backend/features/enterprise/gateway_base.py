"""Abstract base class for enterprise gateway adapters.

All gateway adapters must implement execute(), health_check(), and rollback().
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseGateway(ABC):
    """Base class for all enterprise integration gateways.

    Attributes:
        name: Unique short name for the gateway, e.g. "payment".
        mode: Current operating mode — "mock" or "live".
    """

    name: str
    mode: str  # "mock" or "live"

    @abstractmethod
    async def execute(self, action_type: str, context: dict) -> dict:
        """Execute a gateway action.

        Args:
            action_type: The type of action, e.g. "refund", "create_ticket".
            context:     Payload dict specific to the action type.

        Returns:
            dict with at minimum: {success: bool, mode: str, ...action_result}
        """
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """Ping the gateway to verify connectivity.

        Returns:
            dict with {status: "ok"|"degraded"|"unavailable", mode: str, latency_ms: float|None}
        """
        ...

    @abstractmethod
    async def rollback(self, transaction_id: str) -> dict:
        """Attempt to roll back a previously executed transaction.

        Args:
            transaction_id: Identifier returned by a prior execute() call.

        Returns:
            dict with {success: bool, message: str}
        """
        ...
