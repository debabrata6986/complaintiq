"""CRM adapter — Freshdesk integration with mock fallback.

Live mode requires FRESHDESK_API_KEY and FRESHDESK_DOMAIN in environment.
"""
from __future__ import annotations

import logging
import os
import time

from features.enterprise.gateway_base import BaseGateway

logger = logging.getLogger("complaintiq.enterprise.crm")


class CRMAdapter(BaseGateway):
    """Freshdesk CRM adapter for ticket and contact management.

    Live mode makes REST calls to the Freshdesk API.
    Mock mode returns a structured dict matching the action_executor mock format.
    """

    name = "crm"

    def __init__(self, mode: str = "mock") -> None:
        self.mode = mode
        self._api_key = os.environ.get("FRESHDESK_API_KEY", "")
        self._domain  = os.environ.get("FRESHDESK_DOMAIN", "")
        if mode == "live" and not (self._api_key and self._domain):
            logger.warning("CRMAdapter: FRESHDESK_API_KEY/DOMAIN not set — falling back to mock")
            self.mode = "mock"

    async def execute(self, action_type: str, context: dict) -> dict:
        """Execute a CRM action.

        action_type: "create_contact", "update_ticket", "add_note"
        """
        if self.mode == "live":
            return await self._live_execute(action_type, context)
        return self._mock_execute(action_type, context)

    async def _live_execute(self, action_type: str, context: dict) -> dict:
        try:
            import requests  # type: ignore[import]
            base = f"https://{self._domain}.freshdesk.com/api/v2"
            auth = (self._api_key, "X")

            if action_type == "create_contact":
                r = requests.post(f"{base}/contacts", json=context, auth=auth, timeout=10)
                r.raise_for_status()
                return {"success": True, "mode": "live", "contact": r.json()}
            if action_type == "update_ticket":
                tid = context.pop("ticket_id")
                r = requests.put(f"{base}/tickets/{tid}", json=context, auth=auth, timeout=10)
                r.raise_for_status()
                return {"success": True, "mode": "live", "ticket": r.json()}
            return {"success": False, "mode": "live", "error": f"Unknown action: {action_type}"}
        except Exception as exc:  # noqa: BLE001
            logger.error("CRM live execute failed: %s", exc)
            return {"success": False, "mode": "live", "error": str(exc)}

    def _mock_execute(self, action_type: str, context: dict) -> dict:
        return {
            "success": True,
            "mode": "mock",
            "action_type": action_type,
            "gateway": "freshdesk",
            "crm_id": f"CRM-MOCK-{int(time.time())}",
            "status": "created",
            "note": "Mock response — no real Freshdesk call made",
            "context": context,
        }

    async def health_check(self) -> dict:
        if self.mode == "live":
            try:
                import requests  # type: ignore[import]
                r = requests.get(
                    f"https://{self._domain}.freshdesk.com/api/v2/agents/me",
                    auth=(self._api_key, "X"), timeout=5,
                )
                ok = r.status_code == 200
                return {"status": "ok" if ok else "degraded", "mode": "live", "gateway": "freshdesk"}
            except Exception as exc:  # noqa: BLE001
                return {"status": "unavailable", "mode": "live", "gateway": "freshdesk", "error": str(exc)}
        return {"status": "ok", "mode": "mock", "gateway": "freshdesk", "latency_ms": 0}

    async def rollback(self, transaction_id: str) -> dict:
        return {
            "success": True,
            "mode": self.mode,
            "transaction_id": transaction_id,
            "message": "CRM rollback not applicable — contacts/notes are append-only",
        }
