"""Enterprise actions: messages, override, send response, reopen, feedback, escalate."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import get_current_user, require_roles
from db import get_db
from models import UserPublic, new_id, utcnow_iso

router = APIRouter(prefix="/complaints/{complaint_id}", tags=["actions"])


# ---------- Messages ----------

class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    visibility: Literal["public", "internal"] = "public"
    attachments: list[dict[str, Any]] = []


async def _get_complaint(complaint_id: str) -> dict:
    db = get_db()
    doc = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return doc


def _check_access(c: dict, user: UserPublic, allow_customer: bool = True):
    if user.role in ("admin", "manager", "support"):
        return
    if allow_customer and c["user_id"] == user.id:
        return
    raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/messages")
async def list_messages(complaint_id: str, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    c = await _get_complaint(complaint_id)
    _check_access(c, user)
    q: dict = {"complaint_id": complaint_id}
    # customer can't see internal notes
    if user.role == "customer":
        q["visibility"] = "public"
    msgs = await db.messages.find(q, {"_id": 0}).sort("created_at", 1).limit(500).to_list(length=500)
    return msgs


@router.post("/messages")
async def post_message(complaint_id: str, payload: MessageIn, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    c = await _get_complaint(complaint_id)
    _check_access(c, user)
    # only staff can post internal notes
    visibility = payload.visibility
    if visibility == "internal" and user.role == "customer":
        raise HTTPException(status_code=403, detail="Customers cannot post internal notes")
    msg = {
        "id": new_id(),
        "complaint_id": complaint_id,
        "author_id": user.id,
        "author_name": user.full_name,
        "author_role": user.role,
        "body": payload.body,
        "visibility": visibility,
        "attachments": payload.attachments,
        "created_at": utcnow_iso(),
    }
    await db.messages.insert_one(msg)
    msg.pop("_id", None)
    await db.complaints.update_one(
        {"id": complaint_id},
        {"$set": {"updated_at": utcnow_iso()},
         "$push": {"history": {"at": utcnow_iso(), "status": f"message_{visibility}", "note": f"{user.full_name} ({user.role}) added a {visibility} message"}}},
    )
    return msg


# ---------- Send AI Response (human-in-the-loop) ----------

class SendResponseIn(BaseModel):
    body: str = Field(min_length=10)


@router.post("/send-response")
async def send_response(complaint_id: str, payload: SendResponseIn, user: UserPublic = Depends(require_roles("admin", "manager", "support"))):
    db = get_db()
    await _get_complaint(complaint_id)
    msg = {
        "id": new_id(),
        "complaint_id": complaint_id,
        "author_id": user.id,
        "author_name": user.full_name,
        "author_role": user.role,
        "body": payload.body,
        "visibility": "public",
        "attachments": [],
        "is_official_response": True,
        "created_at": utcnow_iso(),
    }
    await db.messages.insert_one(msg)
    msg.pop("_id", None)
    await db.complaints.update_one(
        {"id": complaint_id},
        {"$set": {"updated_at": utcnow_iso(), "status": "in_progress"},
         "$push": {"history": {"at": utcnow_iso(), "status": "response_sent", "note": f"Official response sent by {user.full_name} ({user.role})"}}},
    )
    return msg


# ---------- Manager Override ----------

class OverrideIn(BaseModel):
    final_action: str
    reason: str | None = None


class OverrideNoteIn(BaseModel):
    reason: str | None = None


async def _regenerate_response(db, complaint_id: str) -> str | None:
    """Regenerate the customer response based on the current recommendation_action."""
    from llm_client import llm_json
    c = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
    if not c:
        return None
    a = c.get("analysis") or {}
    system = (
        "You are the Response Generation Agent. Produce three professional outputs. "
        "Output ONLY valid JSON."
    )
    user = (
        f"CUSTOMER: {c.get('customer_name') or 'Valued Customer'}\n"
        f"INTENT: {a.get('intent','')} | ACTION: {a.get('recommendation_action','')}\n"
        f"RECOMMENDATION: {a.get('recommendation','')}\n"
        f"COMPLAINT: {c.get('description','')}\n\n"
        'Return JSON: { "customer_response": "polite, empathetic 80-120 word reply addressed to the customer, reflecting the action above", '
        '"support_notes": "internal note for support agent (2-3 sentences)", '
        '"manager_notes": "internal note for manager (1-2 sentences)" }'
    )
    try:
        out = await llm_json(system, user, max_tokens=900)
        new_resp = out.get("customer_response") or a.get("customer_response", "")
        await db.complaints.update_one(
            {"id": complaint_id},
            {"$set": {
                "analysis.customer_response": new_resp,
                "analysis.support_notes": out.get("support_notes") or a.get("support_notes", ""),
                "analysis.manager_notes": out.get("manager_notes") or a.get("manager_notes", ""),
                "updated_at": utcnow_iso(),
            },
             "$push": {"history": {"at": utcnow_iso(), "status": "response_regenerated", "note": "Customer response auto-regenerated"}}},
        )
        return new_resp
    except Exception:
        return None


@router.post("/override")
async def override_recommendation(complaint_id: str, payload: OverrideIn, user: UserPublic = Depends(require_roles("admin", "manager"))):
    db = get_db()
    c = await _get_complaint(complaint_id)
    original = (c.get("analysis") or {}).get("recommendation_action")
    record = {
        "id": new_id(),
        "complaint_id": complaint_id,
        "original_action": original,
        "final_action": payload.final_action,
        "reason": payload.reason,  # may be None — optional
        "manager_id": user.id,
        "manager_name": user.full_name,
        "created_at": utcnow_iso(),
    }
    await db.overrides.insert_one(record)
    record.pop("_id", None)
    note_part = f": {payload.reason}" if payload.reason else ""
    await db.complaints.update_one(
        {"id": complaint_id},
        {"$set": {"analysis.recommendation_action": payload.final_action,
                  "analysis.manager_override": record,
                  "updated_at": utcnow_iso()},
         "$push": {"history": {"at": utcnow_iso(), "status": "override", "note": f"Manager {user.full_name} overrode '{original}' → '{payload.final_action}'{note_part}"}}},
    )
    # Auto-regenerate customer response with the new action
    new_response = await _regenerate_response(db, complaint_id)
    return {**record, "regenerated_response": new_response}


@router.patch("/override-note")
async def update_override_note(complaint_id: str, payload: OverrideNoteIn, user: UserPublic = Depends(require_roles("admin", "manager"))):
    """Add or update the optional note on the latest override — never blocks."""
    db = get_db()
    c = await _get_complaint(complaint_id)
    ovr = (c.get("analysis") or {}).get("manager_override")
    if not ovr:
        raise HTTPException(status_code=404, detail="No override to annotate")
    new_reason = payload.reason if payload.reason else None
    await db.complaints.update_one(
        {"id": complaint_id},
        {"$set": {"analysis.manager_override.reason": new_reason, "updated_at": utcnow_iso()}},
    )
    await db.overrides.update_one({"id": ovr["id"]}, {"$set": {"reason": new_reason}})
    return {"updated": True, "reason": new_reason}


@router.post("/generate-response")
async def generate_response(complaint_id: str, user: UserPublic = Depends(require_roles("admin", "manager", "support"))):
    db = get_db()
    await _get_complaint(complaint_id)
    new_response = await _regenerate_response(db, complaint_id)
    if not new_response:
        raise HTTPException(status_code=500, detail="Failed to regenerate response")
    return {"customer_response": new_response}


# ---------- Reopen ----------

@router.post("/reopen")
async def reopen(complaint_id: str, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    c = await _get_complaint(complaint_id)
    _check_access(c, user)
    if user.role == "customer" and c["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    reopen_count = c.get("reopen_count", 0) + 1
    await db.complaints.update_one(
        {"id": complaint_id},
        {"$set": {"status": "in_progress", "reopen_count": reopen_count, "resolved_at": None, "updated_at": utcnow_iso()},
         "$push": {"history": {"at": utcnow_iso(), "status": "reopened", "note": f"Reopened by {user.full_name} (count: {reopen_count})"}}},
    )
    return {"reopened": True, "reopen_count": reopen_count}


# ---------- Feedback / Rating ----------

class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


@router.post("/feedback")
async def submit_feedback(complaint_id: str, payload: FeedbackIn, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    c = await _get_complaint(complaint_id)
    if c["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Only the complaint owner can submit feedback")
    fb = {
        "id": new_id(),
        "complaint_id": complaint_id,
        "user_id": user.id,
        "rating": payload.rating,
        "comment": payload.comment,
        "created_at": utcnow_iso(),
    }
    await db.feedback.insert_one(fb)
    fb.pop("_id", None)
    await db.complaints.update_one(
        {"id": complaint_id},
        {"$set": {"feedback": {"rating": payload.rating, "comment": payload.comment, "at": utcnow_iso()},
                  "updated_at": utcnow_iso()},
         "$push": {"history": {"at": utcnow_iso(), "status": "feedback", "note": f"Customer rated {payload.rating}/5"}}},
    )
    return fb


# ---------- Manual Escalate ----------

@router.post("/escalate")
async def manual_escalate(complaint_id: str, user: UserPublic = Depends(require_roles("admin", "manager", "support"))):
    db = get_db()
    await _get_complaint(complaint_id)
    await db.complaints.update_one(
        {"id": complaint_id},
        {"$set": {"analysis.escalation_required": True, "analysis.routing": "manager_review", "updated_at": utcnow_iso()},
         "$push": {"history": {"at": utcnow_iso(), "status": "escalated", "note": f"Escalated to manager by {user.full_name}"}}},
    )
    return {"escalated": True}
