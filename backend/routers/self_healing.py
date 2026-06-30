"""Self-Healing Dashboard Router for ComplaintIQ (v3.0).

Features 13 & 14: APIs for execution status, timeline, audit logs,
metrics, escalations, and the simulator.

All existing APIs remain unchanged. These are purely additive.

Base prefix: /api/self-healing
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from auth_utils import get_current_user, require_roles
from db import get_db
from execution_models import ExecutionTriggerIn, SimulatorScenarioIn
from models import UserPublic, new_id, utcnow_iso
from simulator import build_simulator_complaint, list_scenarios

logger = logging.getLogger("complaintiq.self_healing_api")

router = APIRouter(prefix="/self-healing", tags=["self-healing"])


def _parse_dt(iso: str) -> datetime:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Feature 13: Execution Status
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    user: UserPublic = Depends(get_current_user),
):
    """Get full execution record by ID."""
    db = get_db()
    doc = await db.executions.find_one({"id": execution_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution not found")
    return doc


@router.get("/executions")
async def list_executions(
    complaint_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    user: UserPublic = Depends(require_roles("admin", "manager", "support")),
):
    """List execution records with optional filters."""
    db = get_db()
    q: dict[str, Any] = {}
    if complaint_id:
        q["complaint_id"] = complaint_id
    if status:
        q["final_status"] = status.upper()
    docs = await db.executions.find(q, {"_id": 0}).sort("started_at", -1).limit(limit).to_list(length=limit)
    return docs


@router.get("/complaints/{complaint_id}/execution")
async def get_complaint_execution(
    complaint_id: str,
    user: UserPublic = Depends(get_current_user),
):
    """Get the latest execution record for a specific complaint."""
    db = get_db()
    # Check complaint exists and user has access
    complaint = await db.complaints.find_one({"id": complaint_id}, {"_id": 0, "user_id": 1})
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if user.role == "customer" and complaint.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    doc = await db.executions.find_one(
        {"complaint_id": complaint_id},
        {"_id": 0},
        sort=[("started_at", -1)],
    )
    if not doc:
        return {"complaint_id": complaint_id, "status": "NO_EXECUTION", "message": "No self-healing execution found"}
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# Feature 8 & 13: Incident Timeline
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/complaints/{complaint_id}/timeline")
async def get_timeline(
    complaint_id: str,
    user: UserPublic = Depends(get_current_user),
):
    """Get the full incident timeline for a complaint."""
    db = get_db()
    complaint = await db.complaints.find_one({"id": complaint_id}, {"_id": 0, "user_id": 1})
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if user.role == "customer" and complaint.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    doc = await db.executions.find_one(
        {"complaint_id": complaint_id},
        {"_id": 0, "timeline": 1, "id": 1, "final_status": 1, "duration_ms": 1},
        sort=[("started_at", -1)],
    )
    if not doc:
        return {
            "complaint_id": complaint_id,
            "timeline": [],
            "message": "No execution timeline available yet",
        }
    return {
        "complaint_id": complaint_id,
        "execution_id": doc.get("id"),
        "final_status": doc.get("final_status"),
        "duration_ms": doc.get("duration_ms"),
        "timeline": doc.get("timeline") or [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Feature 7 & 13: Audit Trail
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/audit")
async def get_audit_log(
    complaint_id: str | None = None,
    execution_id: str | None = None,
    limit: int = Query(default=100, le=500),
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    """Feature 7: Retrieve audit trail entries."""
    db = get_db()
    q: dict[str, Any] = {}
    if complaint_id:
        q["complaint_id"] = complaint_id
    if execution_id:
        q["execution_id"] = execution_id
    docs = await db.audit_trail.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(length=limit)
    return {"count": len(docs), "entries": docs}


@router.get("/complaints/{complaint_id}/audit")
async def get_complaint_audit(
    complaint_id: str,
    user: UserPublic = Depends(require_roles("admin", "manager", "support")),
):
    """Get complete audit trail for one complaint."""
    db = get_db()
    docs = await db.audit_trail.find(
        {"complaint_id": complaint_id}, {"_id": 0}
    ).sort("timestamp", 1).to_list(length=500)
    return {"complaint_id": complaint_id, "count": len(docs), "entries": docs}


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5 & 13: Escalations
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/escalations")
async def list_escalations(
    level: str | None = None,
    limit: int = Query(default=50, le=200),
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    """List auto-escalation records."""
    db = get_db()
    q: dict[str, Any] = {}
    if level:
        q["level"] = level.upper()
    docs = await db.auto_escalations.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(length=limit)
    return {"count": len(docs), "escalations": docs}


# ─────────────────────────────────────────────────────────────────────────────
# Feature 6 & 13: Notifications
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/notifications")
async def list_notifications(
    complaint_id: str | None = None,
    recipient_type: str | None = None,
    limit: int = Query(default=50, le=200),
    user: UserPublic = Depends(require_roles("admin", "manager", "support")),
):
    """List notification records."""
    db = get_db()
    q: dict[str, Any] = {}
    if complaint_id:
        q["complaint_id"] = complaint_id
    if recipient_type:
        q["recipient_type"] = recipient_type
    docs = await db.notifications.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(length=limit)
    return {"count": len(docs), "notifications": docs}


# ─────────────────────────────────────────────────────────────────────────────
# Feature 14: Metrics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def execution_metrics(
    days: int = Query(default=30, le=365),
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    """Feature 14: Comprehensive self-healing execution metrics."""
    db = get_db()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    docs = await db.executions.find(
        {"started_at": {"$gte": since}},
        {"_id": 0},
    ).to_list(length=10000)

    if not docs:
        return {
            "period_days": days,
            "total_executions": 0,
            "message": "No executions in this period",
        }

    total = len(docs)
    completed = sum(1 for d in docs if d.get("final_status") == "COMPLETED")
    failed = sum(1 for d in docs if d.get("final_status") == "FAILED")
    escalated = sum(1 for d in docs if d.get("final_status") == "ESCALATED")
    cancelled = sum(1 for d in docs if d.get("final_status") == "CANCELLED")

    # Resolution time
    durations = [d.get("duration_ms") or 0 for d in docs if d.get("duration_ms")]
    avg_duration = round(sum(durations) / len(durations), 0) if durations else 0
    max_duration = max(durations) if durations else 0
    min_duration = min(durations) if durations else 0

    # Retry stats
    retries = [d.get("retry_count") or 0 for d in docs]
    avg_retries = round(sum(retries) / len(retries), 2)
    docs_with_retries = sum(1 for r in retries if r > 0)

    # Verification stats
    verification_counts: Counter = Counter()
    for d in docs:
        vs = d.get("verification_status") or "UNKNOWN"
        verification_counts[vs] += 1

    # Rollback stats
    rollbacks = sum(1 for d in docs if d.get("rollback_performed"))

    # Notification stats
    total_notifications = sum(len(d.get("notifications_sent") or []) for d in docs)

    # Action type distribution
    action_counter: Counter = Counter()
    for d in docs:
        action_counter[d.get("action_type") or "unknown"] += 1

    # Daily trend (last 14 days)
    today = datetime.now(timezone.utc).date()
    daily: dict[str, int] = defaultdict(int)
    for d in docs:
        try:
            dt = _parse_dt(d.get("started_at", ""))
            daily[dt.strftime("%Y-%m-%d")] += 1
        except Exception:
            pass
    trend = [
        {"date": (today - timedelta(days=i)).strftime("%Y-%m-%d"),
         "count": daily.get((today - timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
        for i in range(13, -1, -1)
    ]

    return {
        "period_days": days,
        "total_executions": total,

        # Feature 14 metrics
        "automation_success_rate_pct": round(completed / total * 100, 1),
        "human_escalation_rate_pct": round(escalated / total * 100, 1),
        "execution_failure_rate_pct": round(failed / total * 100, 1),

        "avg_resolution_time_ms": avg_duration,
        "min_resolution_time_ms": min_duration,
        "max_resolution_time_ms": max_duration,
        "avg_resolution_time_sec": round(avg_duration / 1000, 2),

        "avg_retry_count": avg_retries,
        "executions_with_retries": docs_with_retries,
        "retry_rate_pct": round(docs_with_retries / total * 100, 1),

        "verification_success_rate_pct": round(
            verification_counts.get("SUCCESS", 0) / total * 100, 1
        ),
        "verification_distribution": dict(verification_counts),

        "rollback_count": rollbacks,
        "rollback_frequency_pct": round(rollbacks / total * 100, 1),

        "total_notifications_sent": total_notifications,
        "avg_notifications_per_execution": round(total_notifications / total, 1),

        "status_distribution": {
            "completed": completed,
            "escalated": escalated,
            "failed": failed,
            "cancelled": cancelled,
        },
        "action_type_distribution": [
            {"action_type": k, "count": v} for k, v in action_counter.most_common()
        ],
        "daily_execution_trend": trend,
    }


@router.get("/metrics/adaptive-learning")
async def learning_metrics(
    days: int = Query(default=30, le=365),
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    """Feature 11: Adaptive learning statistics from execution history."""
    db = get_db()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    docs = await db.learning_signals.find(
        {"timestamp": {"$gte": since}},
        {"_id": 0},
    ).to_list(length=10000)

    if not docs:
        return {"period_days": days, "total_signals": 0}

    total = len(docs)

    # Success rate by action
    action_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0, "escalated": 0})
    for d in docs:
        a = d.get("action") or "Unknown"
        sig = d.get("outcome_signal") or "FAILURE"
        if sig == "SUCCESS":
            action_stats[a]["success"] += 1
        elif sig == "ESCALATED":
            action_stats[a]["escalated"] += 1
        else:
            action_stats[a]["failure"] += 1

    action_success_rates = [
        {
            "action": a,
            "total": s["success"] + s["failure"] + s["escalated"],
            "success": s["success"],
            "failure": s["failure"],
            "escalated": s["escalated"],
            "success_rate_pct": round(s["success"] / max(1, s["success"] + s["failure"] + s["escalated"]) * 100, 1),
        }
        for a, s in sorted(action_stats.items(), key=lambda x: -(x[1]["success"]))
    ]

    # Retry patterns
    retry_by_severity: dict[str, list[int]] = defaultdict(list)
    for d in docs:
        retry_by_severity[d.get("severity") or "medium"].append(int(d.get("retry_count") or 0))

    retry_patterns = [
        {
            "severity": sev,
            "avg_retries": round(sum(retries) / len(retries), 2),
            "max_retries": max(retries),
            "sample_size": len(retries),
        }
        for sev, retries in retry_by_severity.items()
    ]

    # Tag aggregation
    tag_counts: Counter = Counter()
    for d in docs:
        tags = d.get("tags") or {}
        for tag, val in tags.items():
            if val:
                tag_counts[tag] += 1

    return {
        "period_days": days,
        "total_signals": total,
        "action_success_rates": action_success_rates,
        "retry_patterns_by_severity": retry_patterns,
        "outcome_tag_counts": dict(tag_counts),
        "top_failure_actions": [
            a for a in action_success_rates
            if a["success_rate_pct"] < 70
        ],
        "top_performing_actions": [
            a for a in action_success_rates
            if a["success_rate_pct"] >= 90
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Feature 9 & 13: Execution State Query
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/state-machine")
async def state_machine_info(user: UserPublic = Depends(get_current_user)):
    """Return the state machine definition and valid transitions."""
    from execution_models import _VALID_TRANSITIONS
    return {
        "states": list(_VALID_TRANSITIONS.keys()),
        "transitions": {k: list(v) for k, v in _VALID_TRANSITIONS.items()},
        "terminal_states": ["COMPLETED", "FAILED", "CANCELLED"],
        "description": "ExecutionStatus state machine for ComplaintIQ self-healing workflow",
    }


@router.get("/complaints/{complaint_id}/state")
async def get_execution_state(
    complaint_id: str,
    user: UserPublic = Depends(get_current_user),
):
    """Get current workflow state for a complaint's execution."""
    db = get_db()
    complaint = await db.complaints.find_one({"id": complaint_id}, {"_id": 0, "user_id": 1})
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if user.role == "customer" and complaint.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    doc = await db.executions.find_one(
        {"complaint_id": complaint_id},
        {"_id": 0, "id": 1, "status": 1, "final_status": 1, "retry_count": 1,
         "verification_status": 1, "escalation_performed": 1, "rollback_performed": 1,
         "started_at": 1, "completed_at": 1, "duration_ms": 1},
        sort=[("started_at", -1)],
    )
    if not doc:
        return {"complaint_id": complaint_id, "state": "NO_EXECUTION"}
    return {
        "complaint_id": complaint_id,
        "execution_id": doc.get("id"),
        "current_state": doc.get("final_status") or doc.get("status"),
        "retry_count": doc.get("retry_count", 0),
        "verification_status": doc.get("verification_status"),
        "escalation_performed": doc.get("escalation_performed", False),
        "rollback_performed": doc.get("rollback_performed", False),
        "started_at": doc.get("started_at"),
        "completed_at": doc.get("completed_at"),
        "duration_ms": doc.get("duration_ms"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Manual Execution Trigger (Feature 13)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/complaints/{complaint_id}/execute")
async def trigger_execution(
    complaint_id: str,
    payload: ExecutionTriggerIn,
    background: BackgroundTasks,
    user: UserPublic = Depends(require_roles("admin", "manager", "support")),
):
    """Manually trigger self-healing execution for an already-analyzed complaint."""
    db = get_db()
    doc = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if not doc.get("analysis"):
        raise HTTPException(status_code=400, detail="Complaint has not been analyzed yet")

    if payload.dry_run:
        analysis = doc.get("analysis") or {}
        from action_executor import resolve_action_type
        action = payload.action or analysis.get("recommendation_action") or "Escalation"
        action_type = resolve_action_type(action, analysis.get("intent") or "")
        return {
            "dry_run": True,
            "complaint_id": complaint_id,
            "action": action,
            "action_type": action_type,
            "message": "Dry run — no execution performed",
        }

    # Launch as background task
    from self_healing import run_self_healing
    analysis = doc.get("analysis") or {}
    if payload.action:
        analysis = {**analysis, "recommendation_action": payload.action}

    background.add_task(
        run_self_healing,
        complaint_id,
        analysis,
        doc,
        payload.simulator,
    )

    return {
        "complaint_id": complaint_id,
        "message": "Self-healing execution triggered",
        "simulator": payload.simulator,
        "action": analysis.get("recommendation_action"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Feature 12: Simulator
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/simulator/scenarios")
async def list_simulator_scenarios(user: UserPublic = Depends(get_current_user)):
    """Feature 12: List all available simulator scenarios."""
    return {"scenarios": list_scenarios()}


@router.post("/simulator/run")
async def run_simulator(
    payload: SimulatorScenarioIn,
    background: BackgroundTasks,
    user: UserPublic = Depends(require_roles("admin", "manager", "support")),
):
    """Feature 12: Run a predefined simulator scenario through the full pipeline.

    Creates a real complaint document (tagged as simulated) and runs the
    complete 13-agent analysis + self-healing workflow.
    """
    from agent_workflow import run_workflow
    from models import new_id, utcnow_iso

    try:
        sim_data = build_simulator_complaint(
            payload.scenario,
            customer_name=payload.customer_name,
            description_override=payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db = get_db()
    complaint_id = new_id()
    now = utcnow_iso()

    # Create a simulator complaint document
    complaint_doc = {
        "id": complaint_id,
        "user_id": user.id,
        "domain": sim_data["domain"],
        "category": sim_data.get("category"),
        "description": sim_data["description"],
        "customer_name": sim_data["customer_name"],
        "customer_email": sim_data.get("customer_email"),
        "customer_phone": None,
        "status": "analyzing",
        "analysis": None,
        "reopen_count": 0,
        "feedback": None,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
        "history": [{"at": now, "status": "submitted", "note": f"Simulator: {payload.scenario}"}],
        # Simulator metadata
        "simulator": True,
        "scenario": payload.scenario,
        "scenario_label": sim_data["scenario_label"],
        "expected_intent": sim_data["expected_intent"],
        "expected_action_type": sim_data["expected_action_type"],
    }
    await db.complaints.insert_one(complaint_doc)
    complaint_doc.pop("_id", None)

    # Run analysis + self-healing in background
    background.add_task(
        _run_simulator_pipeline,
        complaint_id,
        sim_data["description"],
        sim_data["domain"],
        sim_data.get("category"),
        sim_data["customer_name"],
        complaint_doc,
    )

    return {
        "complaint_id": complaint_id,
        "scenario": payload.scenario,
        "scenario_label": sim_data["scenario_label"],
        "domain": sim_data["domain"],
        "expected_intent": sim_data["expected_intent"],
        "expected_action_type": sim_data["expected_action_type"],
        "message": "Simulator complaint created. Full pipeline running in background.",
        "status_url": f"/api/self-healing/complaints/{complaint_id}/state",
        "timeline_url": f"/api/self-healing/complaints/{complaint_id}/timeline",
    }


async def _run_simulator_pipeline(
    complaint_id: str,
    description: str,
    domain: str,
    category: str | None,
    customer_name: str,
    complaint_doc: dict,
) -> None:
    """Background: run analysis then self-healing for a simulator complaint."""
    db = get_db()
    try:
        from agent_workflow import run_workflow
        from routers.complaints import _run_and_persist
        # Re-use the existing analysis pipeline
        await _run_and_persist(complaint_id, description, domain, category, customer_name)

        # Fetch the now-analyzed complaint
        doc = await db.complaints.find_one({"id": complaint_id}, {"_id": 0})
        if doc and doc.get("analysis"):
            from self_healing import run_self_healing
            await run_self_healing(complaint_id, doc["analysis"], doc, simulator_mode=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("Simulator pipeline failed for %s: %s", complaint_id, exc)
        await db.complaints.update_one(
            {"id": complaint_id},
            {"$set": {"status": "submitted", "updated_at": utcnow_iso()},
             "$push": {"history": {"at": utcnow_iso(), "status": "error",
                                   "note": f"Simulator pipeline error: {exc}"}}}
        )
