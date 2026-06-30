"""Analytics router — aggregations for the admin dashboard.

Feature 9: Extended with risk, root cause, confidence, emotion, and sentiment
distribution endpoints while keeping all existing endpoints backward-compatible.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends

from auth_utils import get_current_user
from db import get_db
from models import UserPublic
from vector_db import collection_stats
from embeddings import cache_stats

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _parse_dt(iso: str) -> datetime:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _staff_query(user: UserPublic) -> dict:
    return {} if user.role in ("admin", "manager", "support") else {"user_id": user.id}


# ─────────────────────────────────────────────────────────────────────
# Existing overview endpoint (backward-compatible, extended)
# ─────────────────────────────────────────────────────────────────────

@router.get("/overview")
async def overview(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    q = _staff_query(user)
    total = await db.complaints.count_documents(q)
    pending = await db.complaints.count_documents(
        {**q, "status": {"$in": ["submitted", "analyzing", "analyzed", "assigned", "in_progress"]}}
    )
    resolved = await db.complaints.count_documents({**q, "status": "resolved"})
    critical = await db.complaints.count_documents({**q, "analysis.severity": "critical"})

    docs = await db.complaints.find(
        q,
        {"_id": 0, "analysis": 1, "created_at": 1, "resolved_at": 1, "status": 1, "domain": 1},
    ).to_list(length=5000)

    cat_counter: Counter = Counter()
    dept_counter: Counter = Counter()
    priority_counter: Counter = Counter()
    domain_counter: Counter = Counter()
    daily: dict[str, int] = defaultdict(int)
    monthly: dict[str, int] = defaultdict(int)
    resolution_hours_by_priority: dict[str, list[float]] = defaultdict(list)

    for d in docs:
        a = d.get("analysis") or {}
        cat_counter[a.get("intent") or a.get("category") or "Uncategorized"] += 1
        if a.get("department"):
            dept_counter[a["department"]] += 1
        if a.get("priority"):
            priority_counter[a["priority"]] += 1
        domain_counter[d.get("domain", "general")] += 1

        created = _parse_dt(d["created_at"])
        daily[created.strftime("%Y-%m-%d")] += 1
        monthly[created.strftime("%Y-%m")] += 1
        if d.get("resolved_at") and d.get("status") == "resolved":
            resolved_at = _parse_dt(d["resolved_at"])
            hours = max(0.0, (resolved_at - created).total_seconds() / 3600.0)
            resolution_hours_by_priority[a.get("priority", "medium")].append(hours)

    today = datetime.now(timezone.utc).date()
    trend = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        trend.append({"date": key, "count": daily.get(key, 0)})

    monthly_trend = []
    cursor_d = today.replace(day=1)
    months = []
    for _ in range(6):
        months.append(cursor_d.strftime("%Y-%m"))
        prev_last = cursor_d - timedelta(days=1)
        cursor_d = prev_last.replace(day=1)
    months.reverse()
    for m in months:
        monthly_trend.append({"month": m, "count": monthly.get(m, 0)})

    resolution_avg = []
    for prio in ["critical", "high", "medium", "low"]:
        vals = resolution_hours_by_priority.get(prio, [])
        resolution_avg.append({
            "priority": prio,
            "avg_hours": round(sum(vals) / len(vals), 1) if vals else 0,
            "count": len(vals),
        })

    return {
        "totals": {"total": total, "pending": pending, "resolved": resolved, "critical": critical},
        "top_categories": [{"name": k, "count": v} for k, v in cat_counter.most_common(6)],
        "department_distribution": [{"name": k, "count": v} for k, v in dept_counter.most_common(8)],
        "priority_distribution": [{"name": k, "count": v} for k, v in priority_counter.items()],
        "domain_distribution": [{"name": k, "count": v} for k, v in domain_counter.items()],
        "complaint_trend": trend,
        "monthly_trend": monthly_trend,
        "resolution_time_by_priority": resolution_avg,
    }


# ─────────────────────────────────────────────────────────────────────
# Feature 9: Risk Distribution
# ─────────────────────────────────────────────────────────────────────

@router.get("/risk-distribution")
async def risk_distribution(user: UserPublic = Depends(get_current_user)):
    """Distribution of complaints by Risk Category and Risk Score histogram."""
    db = get_db()
    q = _staff_query(user)
    docs = await db.complaints.find(
        q, {"_id": 0, "analysis.risk_score": 1, "analysis.risk_category": 1, "analysis.severity": 1}
    ).to_list(length=5000)

    cat_counter: Counter = Counter()
    score_buckets: Counter = Counter()  # 0-9, 10-19, …, 90-100
    severity_risk: dict[str, list[int]] = defaultdict(list)

    for d in docs:
        a = d.get("analysis") or {}
        cat = a.get("risk_category") or "Unknown"
        cat_counter[cat] += 1
        score = a.get("risk_score")
        if score is not None:
            bucket = min(9, int(score) // 10) * 10
            score_buckets[f"{bucket}-{bucket+9}"] += 1
        sev = a.get("severity", "medium")
        if score is not None:
            severity_risk[sev].append(int(score))

    severity_avg_risk = {
        sev: round(sum(scores) / len(scores), 1) if scores else 0
        for sev, scores in severity_risk.items()
    }

    return {
        "risk_category_distribution": [
            {"name": k, "count": v}
            for k, v in cat_counter.most_common()
        ],
        "risk_score_histogram": [
            {"bucket": k, "count": v}
            for k, v in sorted(score_buckets.items())
        ],
        "severity_vs_avg_risk": [
            {"severity": sev, "avg_risk_score": avg}
            for sev, avg in severity_avg_risk.items()
        ],
    }


# ─────────────────────────────────────────────────────────────────────
# Feature 9: Sentiment Distribution
# ─────────────────────────────────────────────────────────────────────

@router.get("/sentiment-distribution")
async def sentiment_distribution(user: UserPublic = Depends(get_current_user)):
    """Sentiment and Emotion distribution across complaints."""
    db = get_db()
    q = _staff_query(user)
    docs = await db.complaints.find(
        q, {"_id": 0, "analysis.sentiment": 1, "analysis.emotion": 1, "analysis.sentiment_score": 1,
             "created_at": 1}
    ).to_list(length=5000)

    sentiment_counter: Counter = Counter()
    emotion_counter: Counter = Counter()
    scores: list[float] = []
    monthly_sentiment: dict[str, Counter] = defaultdict(Counter)

    for d in docs:
        a = d.get("analysis") or {}
        sent = a.get("sentiment") or "Unknown"
        emo = a.get("emotion") or "Unknown"
        sentiment_counter[sent] += 1
        emotion_counter[emo] += 1
        s = a.get("sentiment_score")
        if s is not None:
            scores.append(float(s))
        month = _parse_dt(d.get("created_at", "")).strftime("%Y-%m")
        monthly_sentiment[month][sent] += 1

    # Last 6 months trend
    today = datetime.now(timezone.utc).date()
    months = []
    cursor_d = today.replace(day=1)
    for _ in range(6):
        months.append(cursor_d.strftime("%Y-%m"))
        prev = cursor_d - timedelta(days=1)
        cursor_d = prev.replace(day=1)
    months.reverse()

    sentiment_trend = [
        {
            "month": m,
            "Positive": monthly_sentiment[m].get("Positive", 0),
            "Neutral": monthly_sentiment[m].get("Neutral", 0),
            "Negative": monthly_sentiment[m].get("Negative", 0),
        }
        for m in months
    ]

    return {
        "sentiment_distribution": [{"name": k, "count": v} for k, v in sentiment_counter.most_common()],
        "emotion_distribution": [{"name": k, "count": v} for k, v in emotion_counter.most_common()],
        "avg_sentiment_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "sentiment_trend": sentiment_trend,
    }


# ─────────────────────────────────────────────────────────────────────
# Feature 9: Root Cause Distribution
# ─────────────────────────────────────────────────────────────────────

@router.get("/root-cause-distribution")
async def root_cause_distribution(user: UserPublic = Depends(get_current_user)):
    """Distribution of detected root causes across complaints."""
    db = get_db()
    q = _staff_query(user)
    docs = await db.complaints.find(
        q,
        {"_id": 0, "analysis.root_causes": 1, "analysis.root_cause_summary": 1, "analysis.intent": 1},
    ).to_list(length=5000)

    cause_counter: Counter = Counter()
    category_counter: Counter = Counter()
    intent_cause_map: dict[str, Counter] = defaultdict(Counter)

    for d in docs:
        a = d.get("analysis") or {}
        causes = a.get("root_causes") or []
        intent = a.get("intent") or "Unknown"
        for rc in causes:
            cause = rc.get("cause") or "Unknown"
            cat = rc.get("category") or "Unknown"
            cause_counter[cause] += 1
            category_counter[cat] += 1
            intent_cause_map[intent][cause] += 1

    top_intent_causes = {
        intent: [{"cause": k, "count": v} for k, v in ctr.most_common(3)]
        for intent, ctr in intent_cause_map.items()
    }

    return {
        "top_root_causes": [{"name": k, "count": v} for k, v in cause_counter.most_common(10)],
        "root_cause_categories": [{"name": k, "count": v} for k, v in category_counter.most_common()],
        "top_causes_by_intent": top_intent_causes,
    }


# ─────────────────────────────────────────────────────────────────────
# Feature 9: Resolution Statistics (extended)
# ─────────────────────────────────────────────────────────────────────

@router.get("/resolution-stats")
async def resolution_stats(user: UserPublic = Depends(get_current_user)):
    """Comprehensive resolution and HITL statistics."""
    db = get_db()
    q = _staff_query(user)
    docs = await db.complaints.find(
        q,
        {"_id": 0, "analysis": 1, "status": 1, "created_at": 1, "resolved_at": 1},
    ).to_list(length=5000)

    action_counter: Counter = Counter()
    routing_counter: Counter = Counter()
    hitl_count = 0
    escalation_count = 0
    override_count = 0
    confidence_buckets: dict[str, int] = defaultdict(int)
    resolution_times: list[float] = []

    for d in docs:
        a = d.get("analysis") or {}
        action_counter[a.get("recommendation_action") or "Unknown"] += 1
        routing_counter[a.get("routing") or "Unknown"] += 1
        if a.get("human_review_required"):
            hitl_count += 1
        if a.get("escalation_required"):
            escalation_count += 1
        if a.get("manager_override"):
            override_count += 1

        conf = a.get("recommendation_confidence")
        if conf is not None:
            bucket = (
                "High (≥80%)" if float(conf) >= 0.80
                else "Medium (60-79%)" if float(conf) >= 0.60
                else "Low (<60%)"
            )
            confidence_buckets[bucket] += 1

        if d.get("resolved_at") and d.get("status") == "resolved":
            try:
                created = _parse_dt(d["created_at"])
                resolved = _parse_dt(d["resolved_at"])
                hours = max(0.0, (resolved - created).total_seconds() / 3600.0)
                resolution_times.append(hours)
            except Exception:
                pass

    total = len(docs)
    resolved_count = sum(1 for d in docs if d.get("status") == "resolved")

    return {
        "action_distribution": [{"name": k, "count": v} for k, v in action_counter.most_common()],
        "routing_distribution": [{"name": k, "count": v} for k, v in routing_counter.most_common()],
        "hitl_stats": {
            "total_flagged": hitl_count,
            "hitl_rate_pct": round(hitl_count / total * 100, 1) if total else 0,
        },
        "escalation_stats": {
            "total_escalated": escalation_count,
            "escalation_rate_pct": round(escalation_count / total * 100, 1) if total else 0,
        },
        "override_stats": {
            "total_overridden": override_count,
            "override_rate_pct": round(override_count / total * 100, 1) if total else 0,
        },
        "confidence_distribution": [
            {"bucket": k, "count": v} for k, v in confidence_buckets.items()
        ],
        "resolution_rate_pct": round(resolved_count / total * 100, 1) if total else 0,
        "avg_resolution_hours": round(sum(resolution_times) / len(resolution_times), 2) if resolution_times else 0,
        "median_resolution_hours": (
            sorted(resolution_times)[len(resolution_times) // 2] if resolution_times else 0
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# Feature 9: Top Companies / Products from NER
# ─────────────────────────────────────────────────────────────────────

@router.get("/entity-insights")
async def entity_insights(user: UserPublic = Depends(get_current_user)):
    """Top companies, products, and locations extracted by NER."""
    db = get_db()
    q = _staff_query(user)
    docs = await db.complaints.find(
        q, {"_id": 0, "analysis.entities": 1}
    ).to_list(length=5000)

    company_counter: Counter = Counter()
    product_counter: Counter = Counter()
    location_counter: Counter = Counter()

    for d in docs:
        a = d.get("analysis") or {}
        for ent in (a.get("entities") or []):
            t = (ent.get("type") or "").upper()
            v = ent.get("value") or ""
            if not v:
                continue
            if t == "COMPANY":
                company_counter[v] += 1
            elif t == "PRODUCT":
                product_counter[v] += 1
            elif t == "LOCATION":
                location_counter[v] += 1

    return {
        "top_companies": [{"name": k, "count": v} for k, v in company_counter.most_common(10)],
        "top_products": [{"name": k, "count": v} for k, v in product_counter.most_common(10)],
        "top_locations": [{"name": k, "count": v} for k, v in location_counter.most_common(10)],
    }


# ─────────────────────────────────────────────────────────────────────
# Feature 9: Severity Distribution
# ─────────────────────────────────────────────────────────────────────

@router.get("/severity-distribution")
async def severity_distribution(user: UserPublic = Depends(get_current_user)):
    """Severity and priority distribution with trend."""
    db = get_db()
    q = _staff_query(user)
    docs = await db.complaints.find(
        q,
        {"_id": 0, "analysis.severity": 1, "analysis.priority": 1, "created_at": 1},
    ).to_list(length=5000)

    severity_counter: Counter = Counter()
    priority_counter: Counter = Counter()
    monthly_critical: dict[str, int] = defaultdict(int)

    today = datetime.now(timezone.utc).date()
    cursor_d = today.replace(day=1)
    months = []
    for _ in range(6):
        months.append(cursor_d.strftime("%Y-%m"))
        prev = cursor_d - timedelta(days=1)
        cursor_d = prev.replace(day=1)
    months.reverse()

    for d in docs:
        a = d.get("analysis") or {}
        sev = a.get("severity") or "medium"
        pri = a.get("priority") or "medium"
        severity_counter[sev] += 1
        priority_counter[pri] += 1
        if sev == "critical":
            month = _parse_dt(d.get("created_at", "")).strftime("%Y-%m")
            monthly_critical[month] += 1

    critical_trend = [{"month": m, "count": monthly_critical.get(m, 0)} for m in months]

    return {
        "severity_distribution": [{"name": k, "count": v} for k, v in severity_counter.most_common()],
        "priority_distribution": [{"name": k, "count": v} for k, v in priority_counter.most_common()],
        "critical_trend": critical_trend,
    }


# ─────────────────────────────────────────────────────────────────────
# Feature 10: Performance & System Health
# ─────────────────────────────────────────────────────────────────────

@router.get("/system-health")
async def system_health(user: UserPublic = Depends(get_current_user)):
    """Vector DB and embedding cache statistics (Feature 10 + admin diagnostics)."""
    vdb_stats = {}
    emb_stats = {}
    try:
        vdb_stats = collection_stats()
    except Exception as exc:  # noqa: BLE001
        vdb_stats = {"error": str(exc)}
    try:
        emb_stats = cache_stats()
    except Exception as exc:  # noqa: BLE001
        emb_stats = {"error": str(exc)}

    db = get_db()
    total_complaints = await db.complaints.count_documents({})
    total_kb = await db.kb_documents.count_documents({})

    return {
        "vector_db": vdb_stats,
        "embedding_cache": emb_stats,
        "mongodb": {
            "total_complaints": total_complaints,
            "total_kb_documents": total_kb,
        },
    }
