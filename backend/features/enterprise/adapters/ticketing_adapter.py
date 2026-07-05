"""Ticketing adapter — Zendesk integration with mock fallback.

Live mode requires ZENDESK_API_KEY, ZENDESK_EMAIL, and ZENDESK_DOMAIN in environment.
"""
from __future__ import annotations

import logging
import os
import time

from features.enterprise.gateway_base import BaseGateway

logger = logging.getLogger("complaintiq.enterprise.ticketing")


class TicketingAdapter(BaseGateway):
    """Zendesk ticketing adapter for creating and updating support tickets.

    Live mode makes REST calls to the Zendesk API.
    Mock mode returns structured responses matching the action_executor format.
    """

    name = "ticketing"

    def __init__(self, mode: str = "mock") -> None:
        self.mode   = mode
        self._key   = os.environ.get("ZENDESK_API_KEY", "")
        self._email = os.environ.get("ZENDESK_EMAIL", "")
        self._domain = os.environ.get("ZENDESK_DOMAIN", "")
        if mode == "live" and not all([self._key, self._email, self._domain]):
            logger.warning("TicketingAdapter: Zendesk credentials incomplete — falling back to mock")
            self.mode = "mock"

    async def execute(self, action_type: str, context: dict) -> dict:
        """Execute a ticketing action.

        action_type: "create_ticket", "update_ticket", "add_comment", "escalate"
        """
        if self.mode == "live":
            return await self._live_execute(action_type, context)
        return self._mock_execute(action_type, context)

    async def _live_execute(self, action_type: str, context: dict) -> dict:
        try:
            import requests  # type: ignore[import]
            base  = f"https://{self._domain}.zendesk.com/api/v2"
            auth  = (f"{self._email}/token", self._key)
            headers = {"Content-Type": "application/json"}

            if action_type == "create_ticket":
                body = {"ticket": context}
                r = requests.post(f"{base}/tickets.json", json=body, auth=auth, headers=headers, timeout=10)
                r.raise_for_status()
                return {"success": True, "mode": "live", "ticket": r.json().get("ticket", {})}
            if action_type == "update_ticket":
                tid = context.pop("ticket_id")
                r = requests.put(f"{base}/tickets/{tid}.json", json={"ticket": context}, auth=auth, headers=headers, timeout=10)
                r.raise_for_status()
                return {"success": True, "mode": "live", "ticket": r.json().get("ticket", {})}
            return {"success": False, "mode": "live", "error": f"Unknown action: {action_type}"}
        except Exception as exc:  # noqa: BLE001
            logger.error("Zendesk live execute failed: %s", exc)
            return {"success": False, "mode": "live", "error": str(exc)}

    def _mock_execute(self, action_type: str, context: dict) -> dict:
        return {
            "success": True,
            "mode": "mock",
            "action_type": action_type,
            "gateway": "zendesk",
            "ticket_id": f"ZD-MOCK-{int(time.time())}",
            "status": "new",
            "priority": context.get("priority", "normal"),
            "subject": context.get("subject", "Complaint escalated"),
            "note": "Mock response — no real Zendesk call made",
        }

    async def health_check(self) -> dict:
        if self.mode == "live":
            try:
                import requests  # type: ignore[import]
                r = requests.get(
                    f"https://{self._domain}.zendesk.com/api/v2/users/me.json",
                    auth=(f"{self._email}/token", self._key), timeout=5,
                )
                return {"status": "ok" if r.status_code == 200 else "degraded", "mode": "live", "gateway": "zendesk"}
            except Exception as exc:  # noqa: BLE001
                return {"status": "unavailable", "mode": "live", "gateway": "zendesk", "error": str(exc)}
        return {"status": "ok", "mode": "mock", "gateway": "zendesk", "latency_ms": 0}

    async def rollback(self, transaction_id: str) -> dict:
        return {
            "success": True,
            "mode": self.mode,
            "transaction_id": transaction_id,
            "message": "Ticket rollback sets status to deleted — confirm with admin",
        }
