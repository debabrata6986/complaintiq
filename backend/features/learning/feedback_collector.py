"""Feedback collector — persists agent resolution feedback to MongoDB.

Each feedback document records:
    complaint_id  — the complaint being rated
    user_id       — who gave the feedback
    rating        — "thumbs_up" | "thumbs_down"
    category      — "resolution" | "classification" | "priority" | "response"
    correction    — optional free-text correction from the user
    agent_outputs — snapshot of agent outputs at time of feedback
    created_at    — ISO timestamp
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from db import get_db
from models import new_id

logger = logging.getLogger("complaintiq.learning.collector")

COLLECTION = "agent_feedback"


async def record_feedback(
    complaint_id: str,
    user_id: str,
    rating: str,                     # "thumbs_up" | "thumbs_down"
    category: str = "resolution",    # what aspect is being rated
    correction: str | None = None,   # user's free-text correction
    agent_outputs: dict | None = None,
) -> dict:
    """Persist a feedback document and return it.

    Returns the stored feedback document with its generated _id as 'id'.
    """
    if rating not in ("thumbs_up", "thumbs_down"):
        raise ValueError(f"Invalid rating '{rating}'. Must be thumbs_up or thumbs_down.")

    db = get_db()
    doc = {
        "_id":          new_id(),
        "complaint_id": complaint_id,
        "user_id":      user_id,
        "rating":       rating,
        "category":     category,
        "correction":   correction,
        "agent_outputs": agent_outputs or {},
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "processed":    False,   # set True once learning engine ingests this
    }
    await db[COLLECTION].insert_one(doc)
    logger.info(
        "Feedback recorded: complaint=%s user=%s rating=%s category=%s",
        complaint_id, user_id, rating, category,
    )
    return {**doc, "id": doc["_id"]}


async def get_feedback_for_complaint(complaint_id: str) -> list[dict]:
    """Return all feedback documents for a given complaint."""
    db = get_db()
    cursor = db[COLLECTION].find({"complaint_id": complaint_id}, {"_id": 0})
    return await cursor.to_list(length=100)


async def get_unprocessed_feedback(limit: int = 200) -> list[dict]:
    """Return feedback that has not yet been processed by the learning engine."""
    db = get_db()
    cursor = db[COLLECTION].find({"processed": False}, {"_id": 0}).limit(limit)
    return await cursor.to_list(length=limit)


async def mark_processed(feedback_ids: list[str]) -> int:
    """Mark a batch of feedback documents as processed. Returns update count."""
    db = get_db()
    result = await db[COLLECTION].update_many(
        {"_id": {"$in": feedback_ids}},
        {"$set": {"processed": True}},
    )
    return result.modified_count


async def get_feedback_stats() -> dict:
    """Return aggregated feedback statistics across all complaints."""
    db = get_db()
    total      = await db[COLLECTION].count_documents({})
    thumbs_up  = await db[COLLECTION].count_documents({"rating": "thumbs_up"})
    thumbs_down = await db[COLLECTION].count_documents({"rating": "thumbs_down"})
    unprocessed = await db[COLLECTION].count_documents({"processed": False})
    with_correction = await db[COLLECTION].count_documents(
        {"correction": {"$ne": None, "$gt": ""}}
    )

    satisfaction = round(thumbs_up / total * 100, 1) if total else 0.0

    return {
        "total":            total,
        "thumbs_up":        thumbs_up,
        "thumbs_down":      thumbs_down,
        "satisfaction_pct": satisfaction,
        "unprocessed":      unprocessed,
        "with_correction":  with_correction,
    }
