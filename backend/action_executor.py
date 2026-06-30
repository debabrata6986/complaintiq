"""Mock Action Executor for ComplaintIQ Self-Healing (v3.0).

Feature 1: ActionExecutionAgent support layer.
Feature 12: Simulator mode.
Feature 16: Security boundaries — mock APIs are completely isolated.

Each handler:
  - Accepts a normalized ActionRequest
  - Returns an ActionResult
  - Supports future swap to real enterprise API without changing callers

Design contract: every handler is async, accepts `request_data: dict`,
returns `dict` with at minimum: { status, details, error }.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from config import get_execution_cfg
from models import new_id, utcnow_iso

logger = logging.getLogger("complaintiq.action_executor")


# ─────────────────────────────────────────────────────────────────────────────
# Action type registry
# ─────────────────────────────────────────────────────────────────────────────

ACTION_TYPE_MAP: dict[str, str] = {
    "Refund": "refund",
    "Replacement": "replacement",
    "Delivery Delay": "courier_escalation",
    "Delivery Complaint": "courier_escalation",
    "Wrong Product": "warehouse_return",
    "Billing Issue": "finance_investigation",
    "Payment Failure": "finance_investigation",
    "Warranty": "after_sales_ticket",
    "Fraud": "fraud_investigation",
    "Account Issue": "account_recovery",
    "Cancellation": "cancellation_workflow",
    "Technical Issue": "it_support_ticket",
    "Password Reset": "password_reset",
    "Escalation": "manager_escalation",
    "Hold": "hold_workflow",
    "Reject": "rejection_workflow",
    "General Complaint": "general_ticket",
}


def resolve_action_type(action: str, intent: str) -> str:
    """Resolve normalized action type from recommendation action + intent.

    When the action is a generic passthrough (Escalation/Hold), prefer the
    intent-specific handler so the correct workflow is dispatched.
    """
    # Generic actions: let intent decide the handler
    GENERIC_ACTIONS = {"Escalation", "Hold", "General Complaint"}
    if action in GENERIC_ACTIONS and intent and intent != action:
        t = ACTION_TYPE_MAP.get(intent)
        if t:
            return t
    t = ACTION_TYPE_MAP.get(action) or ACTION_TYPE_MAP.get(intent) or "general_ticket"
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Individual mock action handlers
# ─────────────────────────────────────────────────────────────────────────────

async def _exec_refund(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Initiate a refund workflow via payment gateway."""
    exec_cfg = get_execution_cfg()
    # Simulate realistic processing latency
    await asyncio.sleep(0.05 if exec_cfg.simulator_mode else 0.2)
    ref_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    entities = ctx.get("entities", [])
    amount_ent = next((e["value"] for e in entities if e.get("type") == "AMOUNT"), None)
    return {
        "status": "COMPLETED",
        "reference_id": ref_id,
        "workflow": "refund_initiation",
        "amount": amount_ent or "as per complaint",
        "processing_days": "3-5 business days",
        "gateway": "PaymentGateway_MOCK",
        "confirmation": f"Refund {ref_id} created and queued for processing.",
        "next_steps": ["Finance team review", "Bank transfer initiation", "Customer notification"],
    }


async def _exec_replacement(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Create a replacement order via OMS."""
    await asyncio.sleep(0.05)
    order_id = f"ORD-RPL-{uuid.uuid4().hex[:8].upper()}"
    entities = ctx.get("entities", [])
    product = next((e["value"] for e in entities if e.get("type") == "PRODUCT"), "original product")
    return {
        "status": "COMPLETED",
        "replacement_order_id": order_id,
        "workflow": "replacement_order",
        "product": product,
        "dispatch_eta": "2-3 business days",
        "fulfillment_center": "WH-CENTRAL-MOCK",
        "tracking_placeholder": f"TRACK-{uuid.uuid4().hex[:6].upper()}",
        "confirmation": f"Replacement order {order_id} created.",
        "next_steps": ["Warehouse picking", "Quality check", "Dispatch", "Customer notification"],
    }


async def _exec_courier_escalation(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Raise a courier escalation ticket."""
    await asyncio.sleep(0.05)
    ticket_id = f"CUR-{uuid.uuid4().hex[:8].upper()}"
    entities = ctx.get("entities", [])
    tracking = next((e["value"] for e in entities if e.get("type") in ("ORDER_ID", "TRANSACTION_ID")), None)
    return {
        "status": "COMPLETED",
        "ticket_id": ticket_id,
        "workflow": "courier_escalation",
        "courier_partner": "CourierService_MOCK",
        "tracking_ref": tracking or "auto-traced",
        "priority": ctx.get("severity", "medium"),
        "sla_hours": 24,
        "confirmation": f"Courier escalation ticket {ticket_id} raised with logistics partner.",
        "next_steps": ["Courier investigation", "Location trace", "Re-delivery scheduling"],
    }


async def _exec_warehouse_return(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Create a warehouse return/exchange request."""
    await asyncio.sleep(0.05)
    rma_id = f"RMA-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "rma_id": rma_id,
        "workflow": "warehouse_return",
        "return_type": "wrong_product_exchange",
        "pickup_scheduled": "Next business day",
        "warehouse": "WH-RETURNS-MOCK",
        "confirmation": f"Return authorization {rma_id} issued.",
        "next_steps": ["Pickup coordination", "Quality inspection", "Correct item dispatch"],
    }


async def _exec_finance_investigation(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Raise a billing/payment investigation request."""
    await asyncio.sleep(0.05)
    inv_id = f"FIN-{uuid.uuid4().hex[:8].upper()}"
    entities = ctx.get("entities", [])
    invoice = next((e["value"] for e in entities if e.get("type") == "INVOICE"), None)
    return {
        "status": "COMPLETED",
        "investigation_id": inv_id,
        "workflow": "finance_investigation",
        "invoice_ref": invoice or "auto-referenced",
        "finance_team": "BillingOps_MOCK",
        "sla_hours": 48,
        "confirmation": f"Finance investigation {inv_id} opened.",
        "next_steps": ["Account audit", "Charge verification", "Correction or refund"],
    }


async def _exec_fraud_investigation(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Trigger fraud investigation + account protection."""
    await asyncio.sleep(0.05)
    case_id = f"FRAUD-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "case_id": case_id,
        "workflow": "fraud_investigation",
        "risk_team": "RiskCompliance_MOCK",
        "account_freeze": True,
        "sla_hours": 4,
        "confirmation": f"Fraud case {case_id} opened. Account protection measures applied.",
        "next_steps": ["Account freeze", "Transaction review", "Customer identity verification", "Legal notification if required"],
    }


async def _exec_account_recovery(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Initiate account recovery workflow."""
    await asyncio.sleep(0.05)
    req_id = f"ACCT-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "request_id": req_id,
        "workflow": "account_recovery",
        "channel": "CustomerSuccess_MOCK",
        "confirmation": f"Account recovery request {req_id} initiated.",
        "next_steps": ["Identity verification", "Account unlock", "Session reset"],
    }


async def _exec_password_reset(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Generate a secure password reset request."""
    await asyncio.sleep(0.05)
    token_id = f"RST-{uuid.uuid4().hex[:10].upper()}"
    # Feature 16: Never log actual tokens — only IDs
    return {
        "status": "COMPLETED",
        "reset_request_id": token_id,
        "workflow": "password_reset",
        "delivery_channel": "email",
        "token_logged": False,      # security: token not stored
        "expiry_minutes": 30,
        "confirmation": f"Secure reset link dispatched (ref: {token_id}).",
        "next_steps": ["Customer receives reset email", "New password set", "Session invalidated"],
    }


async def _exec_it_support_ticket(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Create an IT support ticket."""
    await asyncio.sleep(0.05)
    ticket_id = f"ITS-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "ticket_id": ticket_id,
        "workflow": "it_support_ticket",
        "it_team": "TechSupport_MOCK",
        "priority": ctx.get("priority", "medium"),
        "sla_hours": 8,
        "confirmation": f"IT support ticket {ticket_id} created.",
        "next_steps": ["Engineer assignment", "Remote diagnostic", "Resolution update"],
    }


async def _exec_after_sales_ticket(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Create an after-sales/warranty ticket."""
    await asyncio.sleep(0.05)
    ticket_id = f"WRT-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "ticket_id": ticket_id,
        "workflow": "warranty_ticket",
        "after_sales_team": "AfterSales_MOCK",
        "confirmation": f"Warranty ticket {ticket_id} opened.",
        "next_steps": ["Service centre assignment", "Product inspection", "Repair or replacement"],
    }


async def _exec_cancellation(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Process order/service cancellation."""
    await asyncio.sleep(0.05)
    can_id = f"CAN-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "cancellation_id": can_id,
        "workflow": "cancellation_workflow",
        "refund_applicable": True,
        "confirmation": f"Cancellation {can_id} processed.",
        "next_steps": ["Order cancellation", "Refund initiation", "Customer confirmation"],
    }


async def _exec_manager_escalation(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Route to manager review queue."""
    await asyncio.sleep(0.05)
    esc_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "escalation_id": esc_id,
        "workflow": "manager_escalation",
        "queue": "ManagerReview_MOCK",
        "sla_hours": 2,
        "confirmation": f"Complaint routed to manager queue (ref: {esc_id}).",
        "next_steps": ["Manager review", "Decision", "Customer callback"],
    }


async def _exec_hold(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Place complaint on hold."""
    await asyncio.sleep(0.02)
    hold_id = f"HLD-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "hold_id": hold_id,
        "workflow": "hold_workflow",
        "reason": "Awaiting additional information or verification",
        "review_in_hours": 24,
        "confirmation": f"Complaint placed on hold (ref: {hold_id}).",
    }


async def _exec_rejection(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Process rejection with reason."""
    await asyncio.sleep(0.02)
    rej_id = f"REJ-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "rejection_id": rej_id,
        "workflow": "rejection_workflow",
        "reason": "Complaint does not meet eligibility criteria per policy",
        "appeal_available": True,
        "confirmation": f"Complaint rejected (ref: {rej_id}). Customer notified of appeal rights.",
    }


async def _exec_general_ticket(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mock: Create a general support ticket."""
    await asyncio.sleep(0.03)
    ticket_id = f"GEN-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "COMPLETED",
        "ticket_id": ticket_id,
        "workflow": "general_ticket",
        "team": "GeneralSupport_MOCK",
        "confirmation": f"Support ticket {ticket_id} created.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Handler dispatch table
# ─────────────────────────────────────────────────────────────────────────────

_HANDLERS: dict[str, Any] = {
    "refund":                _exec_refund,
    "replacement":           _exec_replacement,
    "courier_escalation":    _exec_courier_escalation,
    "warehouse_return":      _exec_warehouse_return,
    "finance_investigation": _exec_finance_investigation,
    "fraud_investigation":   _exec_fraud_investigation,
    "account_recovery":      _exec_account_recovery,
    "password_reset":        _exec_password_reset,
    "it_support_ticket":     _exec_it_support_ticket,
    "after_sales_ticket":    _exec_after_sales_ticket,
    "cancellation_workflow": _exec_cancellation,
    "manager_escalation":    _exec_manager_escalation,
    "hold_workflow":         _exec_hold,
    "rejection_workflow":    _exec_rejection,
    "general_ticket":        _exec_general_ticket,
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def execute_action(
    action_type: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch an action to the appropriate mock handler.

    Args:
        action_type: Normalized action type string (from resolve_action_type).
        context: Dict containing complaint state fields (entities, severity, etc.).

    Returns:
        Dict with at minimum: { status, confirmation, workflow, ... }
        Always contains: { status: COMPLETED|FAILED, error?: str }
    """
    handler = _HANDLERS.get(action_type, _exec_general_ticket)
    try:
        result = await handler(context)
        logger.info("Action executed: type=%s status=%s", action_type, result.get("status"))
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("Action execution failed: type=%s error=%s", action_type, exc)
        return {
            "status": "FAILED",
            "error": str(exc),
            "workflow": action_type,
            "confirmation": f"Action {action_type} failed: {exc}",
        }


def list_supported_actions() -> list[dict[str, str]]:
    """Return list of all supported action types (for API documentation)."""
    return [
        {"action_type": k, "description": v.__doc__ or ""}
        for k, v in _HANDLERS.items()
    ]
