"""Gateway registry — single source of truth for all enterprise adapters.

Reads GATEWAY_MODE env var (default "mock") and instantiates each adapter.
Provides execute(), health_check_all(), and rollback() convenience wrappers.
"""
from __future__ import annotations

import logging
import os

from features.enterprise.adapters.payment_gateway import PaymentGateway
from features.enterprise.adapters.crm_adapter import CRMAdapter
from features.enterprise.adapters.ticketing_adapter import TicketingAdapter

logger = logging.getLogger("complaintiq.enterprise.registry")

# Default mode is "mock" unless GATEWAY_MODE=live is set
_MODE = os.environ.get("GATEWAY_MODE", "mock")

_REGISTRY: dict = {}


def _get_registry() -> dict:
    """Lazy-initialise and return the adapter registry."""
    global _REGISTRY
    if not _REGISTRY:
        _REGISTRY = {
            "payment":  PaymentGateway(mode=_MODE),
            "crm":      CRMAdapter(mode=_MODE),
            "ticketing": TicketingAdapter(mode=_MODE),
        }
        logger.info("Gateway registry initialised in mode=%s with adapters: %s", _MODE, list(_REGISTRY))
    return _REGISTRY


def get_adapter(name: str):
    """Return a specific adapter by name, or None if not found."""
    return _get_registry().get(name)


def list_adapters() -> list[dict]:
    """Return summary info for all registered adapters."""
    return [
        {"name": k, "mode": v.mode, "class": type(v).__name__}
        for k, v in _get_registry().items()
    ]


async def execute_gateway_action(gateway: str, action_type: str, context: dict) -> dict:
    """Execute an action on the named gateway.

    Args:
        gateway:     Gateway name, e.g. "payment", "crm", "ticketing".
        action_type: Action to perform, e.g. "refund", "create_ticket".
        context:     Payload dict for the action.

    Returns:
        Gateway result dict with at minimum {success, mode}.
    """
    adapter = get_adapter(gateway)
    if adapter is None:
        return {
            "success": False,
            "mode": "unknown",
            "error": f"Unknown gateway: '{gateway}'. Available: {list(_get_registry())}",
        }
    logger.info("Executing gateway=%s action=%s", gateway, action_type)
    return await adapter.execute(action_type, context)


async def health_check_all() -> dict:
    """Run health checks on all registered adapters and return combined status."""
    results = {}
    overall = "ok"
    for name, adapter in _get_registry().items():
        result = await adapter.health_check()
        results[name] = result
        if result.get("status") != "ok":
            overall = "degraded"
    return {"overall": overall, "gateways": results}


async def rollback_gateway(gateway: str, transaction_id: str) -> dict:
    """Attempt to roll back a gateway transaction."""
    adapter = get_adapter(gateway)
    if adapter is None:
        return {"success": False, "error": f"Unknown gateway: '{gateway}'"}
    return await adapter.rollback(transaction_id)
