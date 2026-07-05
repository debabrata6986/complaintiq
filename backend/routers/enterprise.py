"""Enterprise Integration Gateway API router — Phase 3 of ComplaintIQ v4.0.

Endpoints (all require admin or manager role):
    GET  /enterprise/gateways           — list all registered adapters
    GET  /enterprise/health             — health check all gateways
    POST /enterprise/execute            — execute a gateway action
    POST /enterprise/rollback           — roll back a transaction
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import get_current_user, require_roles
from models import UserPublic
from features.enterprise.gateway_registry import (
    execute_gateway_action,
    health_check_all,
    list_adapters,
    rollback_gateway,
)

logger = logging.getLogger("complaintiq.routers.enterprise")

router = APIRouter(prefix="/enterprise", tags=["enterprise"])

# ── Pydantic schemas ─────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    gateway: str = Field(..., description="Gateway name: payment | crm | ticketing")
    action_type: str = Field(..., description="Action to perform, e.g. refund, create_ticket")
    context: dict = Field(default_factory=dict, description="Action-specific payload")


class RollbackRequest(BaseModel):
    gateway: str
    transaction_id: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/gateways")
async def list_gateways(user: UserPublic = Depends(require_roles("admin", "manager"))):
    """List all registered gateway adapters and their current mode."""
    adapters = list_adapters()
    logger.info("Gateway list requested by user=%s", user.id)
    return {"gateways": adapters, "total": len(adapters)}


@router.get("/health")
async def gateway_health(user: UserPublic = Depends(require_roles("admin", "manager"))):
    """Run health checks on all gateways. Returns overall status + per-gateway detail."""
    logger.info("Gateway health check requested by user=%s", user.id)
    return await health_check_all()


@router.post("/execute")
async def execute_action(
    body: ExecuteRequest,
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    """Execute an action on a specific gateway.

    In mock mode, returns a simulated response identical in shape to the real gateway response.
    In live mode, makes a real API call to the external service.
    """
    logger.info(
        "Gateway execute: user=%s gateway=%s action=%s",
        user.id, body.gateway, body.action_type,
    )
    result = await execute_gateway_action(body.gateway, body.action_type, body.context)

    if not result.get("success") and result.get("error", "").startswith("Unknown gateway"):
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/rollback")
async def rollback_action(
    body: RollbackRequest,
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    """Attempt to roll back a previously executed gateway transaction."""
    logger.info(
        "Gateway rollback: user=%s gateway=%s txn=%s",
        user.id, body.gateway, body.transaction_id,
    )
    result = await rollback_gateway(body.gateway, body.transaction_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Rollback failed"))

    return result
