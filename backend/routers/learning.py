"""Continual Learning Engine API router — Phase 4 of ComplaintIQ v4.0.

Endpoints:
    POST /learning/feedback              — submit feedback for a complaint (all roles)
    GET  /learning/feedback/:id          — get all feedback for a complaint (admin/manager)
    GET  /learning/stats                 — global feedback stats (admin/manager)
    POST /learning/trigger-cycle         — manually trigger a learning cycle (admin only)
    GET  /learning/runs                  — list recent learning run records (admin/manager)
    GET  /learning/runs/latest           — get the most recent run (admin/manager)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from auth_utils import get_current_user, require_roles
from models import UserPublic
from features.learning.feedback_collector import (
    record_feedback,
    get_feedback_for_complaint,
    get_feedback_stats,
)
from features.learning.learning_engine import get_latest_run, get_all_runs
from features.learning.learning_scheduler import trigger_manual_cycle

logger = logging.getLogger("complaintiq.routers.learning")

router = APIRouter(prefix="/learning", tags=["learning"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    complaint_id:  str = Field(..., description="ID of the complaint being rated")
    rating:        str = Field(..., description="thumbs_up | thumbs_down")
    category:      str = Field("resolution", description="resolution | classification | priority | response")
    correction:    Optional[str] = Field(None, description="Free-text correction (optional)")
    agent_outputs: Optional[dict] = Field(None, description="Snapshot of agent outputs")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    user: UserPublic = Depends(get_current_user),
):
    """Submit thumbs-up/down feedback for a complaint's AI resolution."""
    try:
        doc = await record_feedback(
            complaint_id=body.complaint_id,
            user_id=user.id,
            rating=body.rating,
            category=body.category,
            correction=body.correction,
            agent_outputs=body.agent_outputs,
        )
        logger.info(
            "Feedback submitted: user=%s complaint=%s rating=%s",
            user.id, body.complaint_id, body.rating,
        )
        return {"success": True, "feedback_id": doc.get("id"), "rating": body.rating}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback/{complaint_id}")
async def get_complaint_feedback(
    complaint_id: str,
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    """Get all feedback submitted for a specific complaint."""
    feedback = await get_feedback_for_complaint(complaint_id)
    return {"complaint_id": complaint_id, "feedback": feedback, "total": len(feedback)}


@router.get("/stats")
async def feedback_stats(user: UserPublic = Depends(require_roles("admin", "manager"))):
    """Return aggregated feedback statistics across all complaints."""
    return await get_feedback_stats()


@router.post("/trigger-cycle")
async def trigger_cycle(user: UserPublic = Depends(require_roles("admin"))):
    """Manually trigger a learning cycle immediately (admin only)."""
    logger.info("Manual learning cycle triggered by user=%s", user.id)
    result = await trigger_manual_cycle()
    return result


@router.get("/runs/latest")
async def latest_run(user: UserPublic = Depends(require_roles("admin", "manager"))):
    """Return the most recent learning run record."""
    run = await get_latest_run()
    if run is None:
        return {"message": "No learning runs recorded yet. Trigger a cycle first."}
    return run


@router.get("/runs")
async def all_runs(
    limit: int = 10,
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    """Return the N most recent learning run records."""
    runs = await get_all_runs(limit=min(limit, 50))
    return {"runs": runs, "total": len(runs)}
