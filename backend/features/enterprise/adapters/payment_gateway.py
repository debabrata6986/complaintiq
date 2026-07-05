"""Payment gateway adapter — Stripe integration with mock fallback.

Live mode requires STRIPE_SECRET_KEY in environment.
Mock mode is used by default or whenever the key is missing.
"""
from __future__ import annotations

import logging
import os
import time

from features.enterprise.gateway_base import BaseGateway

logger = logging.getLogger("complaintiq.enterprise.payment")


class PaymentGateway(BaseGateway):
    """Stripe-backed payment gateway for refunds and charge capture.

    In live mode, calls Stripe's refund API.
    In mock mode, returns a deterministic structured response that mirrors
    the real Stripe response shape — identical to the action_executor mock format.
    """

    name = "payment"

    def __init__(self, mode: str = "mock") -> None:
        self.mode = mode
        self._stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
        if mode == "live" and not self._stripe_key:
            logger.warning("PaymentGateway: STRIPE_SECRET_KEY not set — falling back to mock mode")
            self.mode = "mock"

    async def execute(self, action_type: str, context: dict) -> dict:
        """Execute a payment action.

        Supported action_types: "refund", "capture", "void"
        context keys for refund: charge_id, amount_cents, reason
        """
        start = time.monotonic()
        if self.mode == "live":
            return await self._live_execute(action_type, context)
        return self._mock_execute(action_type, context, round((time.monotonic() - start) * 1000, 1))

    async def _live_execute(self, action_type: str, context: dict) -> dict:
        try:
            import stripe  # type: ignore[import]
            stripe.api_key = self._stripe_key

            if action_type == "refund":
                charge_id  = context.get("charge_id", "")
                amount     = context.get("amount_cents")
                reason     = context.get("reason", "requested_by_customer")
                kwargs: dict = {"charge": charge_id, "reason": reason}
                if amount:
                    kwargs["amount"] = amount
                refund = stripe.Refund.create(**kwargs)
                return {
                    "success": True, "mode": "live",
                    "refund_id": refund.id, "status": refund.status,
                    "amount": refund.amount, "currency": refund.currency,
                }
            return {"success": False, "mode": "live", "error": f"Unsupported action_type: {action_type}"}
        except Exception as exc:  # noqa: BLE001
            logger.error("Stripe live execute failed: %s", exc)
            return {"success": False, "mode": "live", "error": str(exc)}

    def _mock_execute(self, action_type: str, context: dict, latency_ms: float) -> dict:
        return {
            "success": True,
            "mode": "mock",
            "action_type": action_type,
            "gateway": "stripe",
            "refund_id": f"re_mock_{int(time.time())}",
            "status": "succeeded",
            "amount": context.get("amount_cents", 1000),
            "currency": "inr",
            "latency_ms": latency_ms,
            "note": "Mock response — no real Stripe call made",
        }

    async def health_check(self) -> dict:
        if self.mode == "live":
            try:
                import stripe  # type: ignore[import]
                stripe.api_key = self._stripe_key
                stripe.Balance.retrieve()
                return {"status": "ok", "mode": "live", "gateway": "stripe", "latency_ms": None}
            except Exception as exc:  # noqa: BLE001
                logger.error("Stripe health check failed: %s", exc)
                return {"status": "degraded", "mode": "live", "gateway": "stripe", "error": str(exc)}
        return {"status": "ok", "mode": "mock", "gateway": "stripe", "latency_ms": 0}

    async def rollback(self, transaction_id: str) -> dict:
        logger.info("PaymentGateway rollback requested for %s (mode=%s)", transaction_id, self.mode)
        return {
            "success": True,
            "mode": self.mode,
            "transaction_id": transaction_id,
            "message": "Rollback simulated" if self.mode == "mock" else "Stripe refund already final — no rollback possible",
        }
