"""Complaints router — CRUD + AI processing."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from auth_utils import get_current_user, require_roles
from agent_workflow import run_workflow
from db import get_db
from models import (
    Complaint, ComplaintCreate, StatusUpdateIn, UserPublic, new_id, utcnow_iso,
)

router = APIRouter(prefix="/complaints", tags=["complaints"])


def _is_staff(role: str) -> bool:
    return role in ("admin", "manager", "support")


@router.post("", response_model=Complaint)
async def create_complaint(
    payload: ComplaintCreate,
    background: BackgroundTasks,
    user: UserPublic = Depends(get_current_user),
):
    db = get_db()
    cid = new_id()
    doc = {
        "id": cid,
        "user_id": user.id,
        "domain": payload.domain,
        "category": payload.category,
        "description": payload.description,
        "customer_name": payload.customer_name or user.full_name,
        "customer_email": payload.customer_email or user.email,
        "customer_phone": payload.customer_phone or user.phone,
        "status": "analyzing",
        "analysis": None,
        "created_at": utcnow_iso(),
        "updated_at": utcnow_iso(),
        "resolved_at": None,
        "history": [{"at": utcnow_iso(), "status": "submitted", "note": "Complaint submitted"}],
    }
    await db.complaints.insert_one(doc)
    # Trigger AI workflow in background so the POST returns instantly
    background.add_task(_run_and_persist, cid, payload.description, payload.domain, payload.category, doc["customer_name"])
    doc.pop("_id", None)
    return Complaint(**doc)


async def _run_and_persist(complaint_id: str, description: str, domain: str, category: str | None, customer_name: str | None):
    db = get_db()
    try:
        result = await run_workflow(
            complaint_id=complaint_id,
            description=description,
            domain=domain,
            category=category,
            customer_name=customer_name,
        )
        analysis = {
            "summary": result.get("summary", ""),
            "keywords": result.get("keywords", []),
            "intent": result.get("intent", "General Complaint"),
            "intent_confidence": result.get("intent_confidence", 0.6),
            "category": result.get("nlu_category") or result.get("intent", ""),
            "entities": result.get("entities", []),
            "sentiment": result.get("sentiment", "Negative"),
            "sentiment_score": result.get("sentiment_score", -0.3),
            "emotion": result.get("emotion", "Concerned"),
            "severity": result.get("severity", "medium"),
            "severity_reason": result.get("severity_reason", ""),
            "priority": result.get("priority", "medium"),
            "department": result.get("department", "Support"),
            "duplicate_score": result.get("duplicate_score", 0.0),
            "similar_complaint_ids": result.get("similar_complaint_ids", []),
            "similar_complaints": result.get("similar_complaints", []),
            "retrieved_policies": result.get("retrieved_policies", []),
            # Root Cause Analysis (v2.0)
            "root_causes": result.get("root_causes", []),
            "root_cause_summary": result.get("root_cause_summary", ""),
            # Risk Scoring (v2.0)
            "risk_score": result.get("risk_score", 0),
            "risk_category": result.get("risk_category", "Low"),
            "risk_components": result.get("risk_components", {}),
            "risk_explanation": result.get("risk_explanation", ""),
            # Recommendation
            "recommendation": result.get("recommendation", ""),
            "recommendation_action": result.get("recommendation_action", "Escalation"),
            "recommendation_confidence": result.get("recommendation_confidence", 0.7),
            "decision_options": result.get("decision_options", []),
            "escalation_required": result.get("escalation_required", False),
            "escalation_reason": result.get("escalation_reason", ""),
            "routing": result.get("routing", "support_review"),
            # Confidence + HITL (v2.0)
            "confidence_records": result.get("confidence_records", []),
            "human_review_required": result.get("human_review_required", False),
            # Explainability + Responses
            "explanation": result.get("explanation", {}),
            "customer_response": result.get("customer_response", ""),
            "support_notes": result.get("support_notes", ""),
            "manager_notes": result.get("manager_notes", ""),
            "agent_trace": result.get("trace", []),
        }
        await db.complaints.update_one(
            {"id": complaint_id},
            {"$set": {
                "analysis": analysis,
                "status": "analyzed",
                "updated_at": utcnow_iso(),
            },
             "$push": {"history": {"at": utcnow_iso(), "status": "analyzed", "note": "AI multi-agent analysis completed"}}},
        )

        # ── v3.0: Self-Healing Pipeline ──────────────────────────────────────
        # Run autonomously after analysis — non-blocking (errors are captured)
        try:
            from config import get_execution_cfg
            from self_healing import run_self_healing
            exec_cfg = get_execution_cfg()
            if exec_cfg.auto_execute:
                complaint_doc = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
                if complaint_doc:
                    await run_self_healing(
                        complaint_id, analysis, complaint_doc,
                        simulator_mode=exec_cfg.simulator_mode,
                    )
        except Exception as sh_err:  # noqa: BLE001
            import logging as _log
            _log.getLogger("complaintiq.complaints").warning(
                "Self-healing pipeline failed (non-fatal) for %s: %s", complaint_id, sh_err
            )

    except Exception as e:  # noqa: BLE001
        await db.complaints.update_one(
            {"id": complaint_id},
            {"$set": {"status": "submitted", "updated_at": utcnow_iso()},
             "$push": {"history": {"at": utcnow_iso(), "status": "error", "note": f"AI processing failed: {e}"}}},
        )


@router.get("", response_model=list[Complaint])
async def list_complaints(
    user: UserPublic = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    domain: str | None = None,
    limit: int = 100,
):
    db = get_db()
    query: dict[str, Any] = {}
    if not _is_staff(user.role):
        query["user_id"] = user.id
    if status_filter:
        query["status"] = status_filter
    if domain:
        query["domain"] = domain
    cursor = db.complaints.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [Complaint(**d) for d in docs]


@router.get("/{complaint_id}", response_model=Complaint)
async def get_complaint(complaint_id: str, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    doc = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if not _is_staff(user.role) and doc["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return Complaint(**doc)


@router.post("/{complaint_id}/analyze", response_model=Complaint)
async def reanalyze(complaint_id: str, user: UserPublic = Depends(require_roles("admin", "manager", "support"))):
    db = get_db()
    doc = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Complaint not found")
    await db.complaints.update_one({"id": complaint_id}, {"$set": {"status": "analyzing", "updated_at": utcnow_iso()}})
    await _run_and_persist(complaint_id, doc["description"], doc["domain"], doc.get("category"), doc.get("customer_name"))
    doc = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
    return Complaint(**doc)


@router.patch("/{complaint_id}/status", response_model=Complaint)
async def update_status(complaint_id: str, payload: StatusUpdateIn, user: UserPublic = Depends(require_roles("admin", "manager", "support"))):
    db = get_db()
    update: dict[str, Any] = {"status": payload.status, "updated_at": utcnow_iso()}
    if payload.status == "resolved":
        update["resolved_at"] = utcnow_iso()
    res = await db.complaints.update_one(
        {"id": complaint_id},
        {"$set": update,
         "$push": {"history": {"at": utcnow_iso(), "status": payload.status, "note": payload.note or f"Status changed to {payload.status} by {user.full_name}"}}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Complaint not found")
    doc = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
    return Complaint(**doc)


@router.delete("/{complaint_id}")
async def delete_complaint(complaint_id: str, user: UserPublic = Depends(require_roles("admin"))):
    db = get_db()
    res = await db.complaints.delete_one({"id": complaint_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {"deleted": True}
