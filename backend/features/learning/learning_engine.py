"""Learning engine — analyses accumulated feedback to surface improvement signals.

Runs periodically (driven by learning_scheduler.py) and produces:
    - Per-category satisfaction rates
    - Most common correction themes (simple keyword frequency)
    - Low-confidence patterns (categories with thumbs_down rate > threshold)
    - A learning_runs collection entry for audit trail
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from db import get_db
from features.learning.feedback_collector import get_unprocessed_feedback, mark_processed

logger = logging.getLogger("complaintiq.learning.engine")

COLLECTION        = "learning_runs"
NEGATIVE_THRESHOLD = 0.35   # flag categories where thumbs_down rate exceeds this


def _extract_keywords(texts: list[str], top_n: int = 10) -> list[dict]:
    """Return top-N keyword frequencies from a list of free-text strings."""
    stopwords = {
        "the", "a", "an", "is", "it", "was", "to", "of", "and", "in", "for",
        "my", "me", "i", "you", "we", "they", "this", "that", "with", "not",
        "are", "be", "on", "at", "by", "as", "or", "but", "from",
    }
    words: list[str] = []
    for text in texts:
        if text:
            tokens = text.lower().replace(",", " ").replace(".", " ").split()
            words.extend(t for t in tokens if t not in stopwords and len(t) > 2)
    counter = Counter(words)
    return [{"keyword": k, "count": v} for k, v in counter.most_common(top_n)]


async def run_learning_cycle() -> dict:
    """Ingest unprocessed feedback, compute signals, and store a learning run record.

    Returns a summary dict of what was processed and what signals were surfaced.
    """
    logger.info("Learning cycle started")
    feedback_batch = await get_unprocessed_feedback(limit=500)

    if not feedback_batch:
        logger.info("No unprocessed feedback — skipping cycle")
        return {"processed": 0, "signals": [], "message": "No new feedback to process"}

    # ── Aggregate by category ────────────────────────────────────────────────
    cat_up:   dict[str, int] = {}
    cat_down: dict[str, int] = {}
    corrections: list[str]   = []
    ids_to_mark: list[str]   = []

    for fb in feedback_batch:
        cat = fb.get("category", "resolution")
        if fb["rating"] == "thumbs_up":
            cat_up[cat]   = cat_up.get(cat, 0) + 1
        else:
            cat_down[cat] = cat_down.get(cat, 0) + 1

        if fb.get("correction"):
            corrections.append(fb["correction"])

        ids_to_mark.append(fb.get("_id") or fb.get("id", ""))

    # ── Compute per-category satisfaction ───────────────────────────────────
    all_cats  = set(cat_up) | set(cat_down)
    cat_stats = []
    signals   = []

    for cat in all_cats:
        up   = cat_up.get(cat, 0)
        down = cat_down.get(cat, 0)
        total = up + down
        neg_rate = round(down / total, 3) if total else 0.0
        sat_pct  = round(up / total * 100, 1) if total else 0.0

        cat_stats.append({
            "category":          cat,
            "thumbs_up":         up,
            "thumbs_down":       down,
            "satisfaction_pct":  sat_pct,
            "negative_rate":     neg_rate,
        })

        if neg_rate > NEGATIVE_THRESHOLD:
            signals.append({
                "type":         "low_satisfaction",
                "category":     cat,
                "negative_rate": neg_rate,
                "message":      f"Category '{cat}' has {neg_rate*100:.0f}% negative feedback — review agent prompts",
            })

    # ── Keyword analysis on corrections ─────────────────────────────────────
    top_keywords = _extract_keywords(corrections, top_n=10)
    if top_keywords:
        signals.append({
            "type":     "correction_keywords",
            "keywords": top_keywords,
            "message":  "Top correction keywords extracted from user feedback",
        })

    # ── Mark all batch items processed ──────────────────────────────────────
    ids_valid = [i for i in ids_to_mark if i]
    if ids_valid:
        await mark_processed(ids_valid)

    # ── Persist learning run record ──────────────────────────────────────────
    run_doc = {
        "run_at":       datetime.now(timezone.utc).isoformat(),
        "processed":    len(feedback_batch),
        "categories":   cat_stats,
        "signals":      signals,
        "top_keywords": top_keywords,
    }
    db = get_db()
    await db[COLLECTION].insert_one({**run_doc, "_id": f"run_{int(datetime.now().timestamp())}"})

    logger.info(
        "Learning cycle complete: processed=%d signals=%d",
        len(feedback_batch), len(signals),
    )
    return run_doc


async def get_latest_run() -> dict | None:
    """Return the most recent learning run record."""
    db = get_db()
    doc = await db[COLLECTION].find_one({}, sort=[("run_at", -1)])
    if doc:
        doc.pop("_id", None)
    return doc


async def get_all_runs(limit: int = 10) -> list[dict]:
    """Return the N most recent learning run records."""
    db = get_db()
    cursor = db[COLLECTION].find({}, {"_id": 0}).sort("run_at", -1).limit(limit)
    return await cursor.to_list(length=limit)
