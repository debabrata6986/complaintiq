"""Self-Healing Workflow Engine for ComplaintIQ (v3.0).

Orchestrates the autonomous self-healing pipeline after the main 13-agent
analysis completes. This module owns:

  Feature 1:  ActionExecutionAgent — dispatch action, capture result
  Feature 2:  WorkflowVerificationAgent — verify action succeeded
  Feature 3:  Retry mechanism with exponential backoff
  Feature 4:  Rollback engine for partial failures
  Feature 5:  Auto-escalation agent with multi-criteria triggers
  Feature 6:  NotificationAgent — multi-channel, multi-recipient notifications
  Feature 7:  Execution audit trail (every step recorded)
  Feature 8:  Incident timeline construction
  Feature 11: Adaptive learning data collection

The engine is invoked as a background task by the complaints router after
analysis completes, ensuring the main analysis API remains fast.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from action_executor import execute_action, resolve_action_type
from config import get_execution_cfg
from db import get_db
from execution_models import (
    ActionResult, AuditEntry, AutoEscalationRecord, EscalationLevel,
    ExecutionRecord, ExecutionStatus, IncidentTimelineEvent,
    NotificationRecord, RetryRecord, RollbackRecord,
    VerificationResult, VerificationStatus, validate_transition,
)
from models import new_id, utcnow_iso

logger = logging.getLogger("complaintiq.self_healing")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


def _now() -> str:
    return utcnow_iso()


async def _persist_execution(record: ExecutionRecord) -> None:
    """Upsert ExecutionRecord to MongoDB."""
    try:
        db = get_db()
        data = record.model_dump()
        await db.executions.replace_one({"id": record.id}, data, upsert=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist execution record %s: %s", record.id, exc)


async def _persist_audit(entry: AuditEntry) -> None:
    """Insert AuditEntry to MongoDB."""
    try:
        db = get_db()
        await db.audit_trail.insert_one(entry.model_dump())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist audit entry: %s", exc)


async def _persist_notification(n: NotificationRecord) -> None:
    try:
        db = get_db()
        await db.notifications.insert_one(n.model_dump())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist notification: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Feature 2: Workflow Verification Agent
# ─────────────────────────────────────────────────────────────────────────────

async def _verify_action(
    action_result: ActionResult,
    context: dict[str, Any],
    exec_cfg=None,
) -> VerificationResult:
    """Verify that an action was successfully executed.

    Performs a series of checks appropriate to the action type.
    Returns VerificationResult with SUCCESS | FAILED | PENDING | TIMEOUT.
    """
    if exec_cfg is None:
        exec_cfg = get_execution_cfg()

    t = time.time()
    checks: list[dict[str, Any]] = []

    # Check 1: Action status
    status_ok = action_result.status in ("INITIATED", "COMPLETED")
    checks.append({
        "check": "action_status",
        "expected": "COMPLETED or INITIATED",
        "actual": action_result.status,
        "passed": status_ok,
    })

    # Check 2: No error field
    no_error = action_result.error is None
    checks.append({
        "check": "no_error",
        "passed": no_error,
        "detail": action_result.error or "",
    })

    # Check 3: Details populated
    details_ok = bool(action_result.details)
    checks.append({
        "check": "details_populated",
        "passed": details_ok,
    })

    # Check 4: Action-type-specific verification
    action_type = action_result.action_type
    specific_pass = True
    specific_detail = ""
    if action_type == "refund":
        specific_pass = bool(action_result.details.get("reference_id"))
        specific_detail = f"reference_id={'present' if specific_pass else 'missing'}"
    elif action_type == "replacement":
        specific_pass = bool(action_result.details.get("replacement_order_id"))
        specific_detail = f"replacement_order_id={'present' if specific_pass else 'missing'}"
    elif action_type in ("courier_escalation", "it_support_ticket", "after_sales_ticket", "general_ticket"):
        specific_pass = bool(action_result.details.get("ticket_id"))
        specific_detail = f"ticket_id={'present' if specific_pass else 'missing'}"
    elif action_type == "fraud_investigation":
        specific_pass = bool(action_result.details.get("case_id"))
        specific_detail = f"case_id={'present' if specific_pass else 'missing'}"
    elif action_type == "finance_investigation":
        specific_pass = bool(action_result.details.get("investigation_id"))
        specific_detail = f"investigation_id={'present' if specific_pass else 'missing'}"
    checks.append({
        "check": f"{action_type}_specific",
        "passed": specific_pass,
        "detail": specific_detail,
    })

    all_passed = all(c["passed"] for c in checks)
    verification_status: VerificationStatus = "SUCCESS" if all_passed else "FAILED"

    elapsed = _ms(t)
    if elapsed > int(exec_cfg.verification_timeout_seconds * 1000):
        verification_status = "TIMEOUT"

    passed_count = sum(1 for c in checks if c["passed"])
    reasoning = (
        f"Verification {'passed' if all_passed else 'failed'}: "
        f"{passed_count}/{len(checks)} checks passed in {elapsed}ms."
    )

    return VerificationResult(
        execution_id=action_result.execution_id,
        complaint_id=action_result.complaint_id,
        action=action_result.action,
        verification_status=verification_status,
        reasoning=reasoning,
        checks=checks,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Feature 4: Rollback Engine
# ─────────────────────────────────────────────────────────────────────────────

_ROLLBACK_ACTIONS: dict[str, str] = {
    "refund":                "cancel_pending_refund",
    "replacement":           "cancel_replacement_order",
    "courier_escalation":    "close_courier_ticket",
    "warehouse_return":      "cancel_rma",
    "finance_investigation": "close_investigation",
    "fraud_investigation":   "unfreeze_account_if_safe",
    "it_support_ticket":     "close_ticket",
    "after_sales_ticket":    "close_warranty_ticket",
    "manager_escalation":    "remove_from_manager_queue",
    "general_ticket":        "close_ticket",
    "hold_workflow":         "remove_hold",
    "cancellation_workflow": "reinstate_order",
    # Gap-fix: previously missing rollback entries
    "rejection_workflow":    "reverse_rejection_notify_customer",
    "account_recovery":      "cancel_recovery_request",
    "password_reset":        "invalidate_reset_token",
}


async def _perform_rollback(
    action_result: ActionResult,
    reason: str,
) -> RollbackRecord:
    """Attempt to roll back a partially completed action."""
    rollback_action = _ROLLBACK_ACTIONS.get(action_result.action_type, "manual_review_required")
    applicable = rollback_action != "manual_review_required"

    status_val = "COMPLETED" if applicable else "NOT_APPLICABLE"
    details = {
        "original_action": action_result.action_type,
        "original_details": action_result.details,
        "rollback_action": rollback_action,
        "mock": True,
    }

    if applicable:
        # Mock: simulate rollback operation
        await asyncio.sleep(0.02)
        details["rollback_reference"] = f"RBK-{new_id()[:8].upper()}"
        logger.info("Rollback performed: %s → %s", action_result.action_type, rollback_action)
    else:
        logger.warning("Rollback not applicable for %s — manual review required", action_result.action_type)

    return RollbackRecord(
        execution_id=action_result.execution_id,
        complaint_id=action_result.complaint_id,
        reason=reason,
        action_rolled_back=action_result.action_type,
        rollback_action=rollback_action,
        status=status_val,
        details=details,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5: Auto-Escalation Agent
# ─────────────────────────────────────────────────────────────────────────────

def _determine_escalation_level(reasons: list[str], analysis: dict[str, Any]) -> EscalationLevel:
    """Determine escalation level based on reasons and complaint analysis.

    Priority order (highest first):
      FRAUD    — fraud keywords detected in reasons or intent
      LEGAL    — legal keywords detected
      EXECUTIVE — critical risk category
      L3       — critical severity or repeated failures
      L2       — high severity or VIP customer
      L1       — all other cases
    """
    reason_text = " ".join(reasons).lower()
    intent = (analysis.get("intent") or "").lower()
    action_type = (analysis.get("recommendation_action") or "").lower()

    # FRAUD: fraud investigation specifically (gap-fix: FRAUD level was unreachable)
    if "fraud" in intent or action_type == "fraud" or "fraud investigation" in reason_text:
        return "FRAUD"
    # LEGAL: legal keywords in reasons
    if "legal" in reason_text or "lawsuit" in reason_text or "ombudsman" in reason_text:
        return "LEGAL"
    risk_cat = (analysis.get("risk_category") or "Low").lower()
    if risk_cat == "critical" or "critical" in reason_text:
        return "EXECUTIVE"
    sev = (analysis.get("severity") or "medium").lower()
    if sev == "critical" or "repeated" in reason_text:
        return "L3"
    if sev == "high" or "vip" in reason_text:
        return "L2"
    return "L1"


async def _auto_escalate(
    complaint_id: str,
    execution_id: str,
    reasons: list[str],
    analysis: dict[str, Any],
    exec_cfg=None,
) -> AutoEscalationRecord:
    """Feature 5: Create and persist an auto-escalation record."""
    if exec_cfg is None:
        exec_cfg = get_execution_cfg()

    level = _determine_escalation_level(reasons, analysis)
    dept_map: dict[str, str] = {
        "L1": "Support",
        "L2": "Senior Support",
        "L3": "Management",
        "EXECUTIVE": "Executive Team",
        "LEGAL": "Legal & Compliance",
        "FRAUD": "Risk & Compliance",
    }
    queue_map: dict[str, str] = {
        "L1": "QUEUE_SUPPORT",
        "L2": "QUEUE_SENIOR_SUPPORT",
        "L3": "QUEUE_MANAGEMENT",
        "EXECUTIVE": "QUEUE_EXECUTIVE",
        "LEGAL": "QUEUE_LEGAL",
        "FRAUD": "QUEUE_FRAUD",
    }

    risk_score = int(analysis.get("risk_score") or 0)
    priority = (
        "critical" if risk_score >= 85
        else "high" if risk_score >= 70
        else "medium"
    )

    record = AutoEscalationRecord(
        execution_id=execution_id,
        complaint_id=complaint_id,
        level=level,
        department=dept_map.get(level, "Support"),
        priority=priority,
        queue=queue_map.get(level, "QUEUE_SUPPORT"),
        reasons=reasons,
    )

    try:
        db = get_db()
        await db.auto_escalations.insert_one(record.model_dump())
        # Also update the complaint's routing field
        await db.complaints.update_one(
            {"id": complaint_id},
            {"$set": {
                "analysis.escalation_required": True,
                "analysis.routing": "manager_review",
                "updated_at": utcnow_iso(),
            },
             "$push": {"history": {
                 "at": utcnow_iso(),
                 "status": "auto_escalated",
                 "note": f"Auto-escalated [{level}]: {'; '.join(reasons[:2])}",
             }}},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist auto-escalation: %s", exc)

    logger.info("Auto-escalated complaint %s: level=%s reasons=%s", complaint_id, level, reasons)
    return record


# ─────────────────────────────────────────────────────────────────────────────
# Feature 6: Notification Agent
# ─────────────────────────────────────────────────────────────────────────────

async def _send_notification(
    execution_id: str,
    complaint_id: str,
    recipient_type: str,
    channel: str,
    subject: str,
    body: str,
    recipient_id: str | None = None,
) -> NotificationRecord:
    """Feature 6: Generate and store a notification (mock channels)."""
    # Mock: simulate channel delivery
    await asyncio.sleep(0.01)
    n = NotificationRecord(
        execution_id=execution_id,
        complaint_id=complaint_id,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        channel=channel,
        subject=subject,
        body=body,
        status="SENT",
        mock=True,
    )
    await _persist_notification(n)
    logger.debug("Notification sent: recipient=%s channel=%s subject=%s", recipient_type, channel, subject)
    return n


async def _notify_all(
    execution_id: str,
    complaint_id: str,
    action: str,
    action_details: dict[str, Any],
    verification_status: str,
    analysis: dict[str, Any],
    complaint_doc: dict[str, Any],
    exec_cfg,
) -> list[NotificationRecord]:
    """Send all relevant notifications for a completed execution."""
    notifications: list[NotificationRecord] = []
    customer_name = complaint_doc.get("customer_name") or "Valued Customer"
    intent = analysis.get("intent", "")
    action_conf = action_details.get("confirmation", f"{action} processed")

    # Customer notification
    if exec_cfg.notify_customer:
        customer_body = (
            f"Dear {customer_name},\n\n"
            f"Your complaint regarding '{intent}' has been processed.\n\n"
            f"Action taken: {action}\n"
            f"Status: {verification_status}\n"
            f"Reference: {action_conf}\n\n"
            f"Our team will follow up with you shortly.\n\n"
            f"ComplaintIQ — Automated Resolution System"
        )
        n = await _send_notification(
            execution_id, complaint_id, "customer", "email",
            f"Complaint Update — {action}",
            customer_body,
            recipient_id=complaint_doc.get("user_id"),
        )
        notifications.append(n)

    # Support team notification
    if exec_cfg.notify_support:
        support_body = (
            f"Automated action completed for complaint {complaint_id}.\n"
            f"Action: {action} | Status: {verification_status}\n"
            f"Risk: {analysis.get('risk_category','?')} ({analysis.get('risk_score',0)}/100)\n"
            f"Details: {action_conf}"
        )
        n = await _send_notification(
            execution_id, complaint_id, "support", "dashboard",
            f"Action Completed: {action}",
            support_body,
        )
        notifications.append(n)

    # Manager notification (escalations or critical)
    if exec_cfg.notify_manager and (
        verification_status == "FAILED"
        or (analysis.get("risk_category") or "Low") in ("High", "Critical")
        or analysis.get("escalation_required")
    ):
        manager_body = (
            f"ATTENTION: Complaint {complaint_id} requires manager review.\n"
            f"Action: {action} | Verification: {verification_status}\n"
            f"Risk Score: {analysis.get('risk_score',0)}/100 ({analysis.get('risk_category','?')})\n"
            f"Escalation: {analysis.get('escalation_reason','')}"
        )
        n = await _send_notification(
            execution_id, complaint_id, "manager", "dashboard",
            f"Manager Alert: {complaint_id}",
            manager_body,
        )
        notifications.append(n)

    # SMS notification for urgent/critical risk complaints (gap-fix: F6 SMS channel)
    risk_score = int(analysis.get("risk_score") or 0)
    customer_phone = complaint_doc.get("customer_phone")
    if customer_phone and risk_score >= 70 and exec_cfg.notify_customer:
        sms_body = (
            f"ComplaintIQ: Your {action} request (ID: {complaint_id[:8]}) "
            f"has been {'processed' if verification_status == 'SUCCESS' else 'escalated'}. "
            f"Our team will contact you shortly."
        )
        n = await _send_notification(
            execution_id, complaint_id, "customer", "sms",
            f"Complaint {action} Update",
            sms_body,
            recipient_id=complaint_doc.get("user_id"),
        )
        notifications.append(n)

    # Push notification for support staff on new escalations (gap-fix: F6 push channel)
    if analysis.get("escalation_required") and exec_cfg.notify_support:
        push_body = (
            f"New escalation: {complaint_id[:12]} | "
            f"Action: {action} | Risk: {analysis.get('risk_category','?')} "
            f"({risk_score}/100)"
        )
        n = await _send_notification(
            execution_id, complaint_id, "support", "push",
            f"Escalation: {action}",
            push_body,
        )
        notifications.append(n)

    return notifications


# ─────────────────────────────────────────────────────────────────────────────
# Feature 8: Incident Timeline Builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_timeline(
    agent_trace: list[dict[str, Any]],
    execution_record: ExecutionRecord,
    notifications: list[NotificationRecord],
) -> list[dict[str, Any]]:
    """Feature 8: Build ordered incident timeline from all workflow events."""
    events: list[IncidentTimelineEvent] = []
    seq = 0

    # Map agent trace entries to timeline events
    agent_event_map = {
        "ComplaintUnderstandingAgent":     ("Complaint Understood", "brain"),
        "IntentClassificationAgent":       ("Intent Classified", "tag"),
        "NamedEntityRecognitionAgent":     ("Entities Extracted", "search"),
        "SentimentEmotionAgent":           ("Sentiment Analyzed", "heart"),
        "SeverityPredictionAgent":         ("Severity Predicted", "alert-triangle"),
        "DuplicateComplaintAgent":         ("Duplicate Check Completed", "copy"),
        "KnowledgeRetrievalAgent":         ("Knowledge Retrieved", "book"),
        "RootCauseAnalysisAgent":          ("Root Cause Identified", "git-branch"),
        "ResolutionRecommendationAgent":   ("Resolution Recommended", "check-circle"),
        "RiskScoringAgent":                ("Risk Score Calculated", "shield"),
        "EscalationAgent":                 ("Escalation Evaluated", "arrow-up"),
        "ExplainabilityAgent":             ("Explanation Generated", "info"),
        "ResponseGenerationAgent":         ("Response Generated", "message-square"),
    }

    # Complaint submitted (synthetic first event)
    seq += 1
    events.append(IncidentTimelineEvent(
        sequence=seq,
        event="Complaint Submitted",
        agent="System",
        status="SUCCESS",
        detail="Complaint received and queued for AI analysis",
        icon="file-plus",
    ))

    # Agent trace events
    for tr in agent_trace:
        agent_name = tr.get("agent", "")
        label, icon = agent_event_map.get(agent_name, (agent_name, "circle"))
        seq += 1
        events.append(IncidentTimelineEvent(
            sequence=seq,
            event=label,
            agent=agent_name,
            status="SUCCESS" if tr.get("status") == "success" else "FAILURE",
            detail=str(tr.get("output") or ""),
            duration_ms=tr.get("duration_ms", 0),
            icon=icon,
        ))

    # Action execution
    if execution_record.action_result:
        seq += 1
        exec_status = "SUCCESS" if execution_record.action_result.get("status") == "COMPLETED" else "FAILURE"
        events.append(IncidentTimelineEvent(
            sequence=seq,
            event=f"Action Executed: {execution_record.action}",
            agent="ActionExecutionAgent",
            status=exec_status,
            detail=execution_record.action_result.get("confirmation", ""),
            icon="zap",
        ))

    # Retries
    for retry in execution_record.retry_history:
        seq += 1
        events.append(IncidentTimelineEvent(
            sequence=seq,
            event=f"Retry Attempt #{retry.get('attempt', '?')}",
            agent="RetryEngine",
            status="FAILURE" if retry.get("outcome") == "FAILED" else "SUCCESS",
            detail=retry.get("reason", ""),
            icon="refresh-cw",
        ))

    # Verification
    if execution_record.verification_result:
        seq += 1
        vstat = execution_record.verification_result.get("verification_status", "PENDING")
        events.append(IncidentTimelineEvent(
            sequence=seq,
            event="Workflow Verification Completed",
            agent="WorkflowVerificationAgent",
            status="SUCCESS" if vstat == "SUCCESS" else "FAILURE",
            detail=execution_record.verification_result.get("reasoning", ""),
            icon="check-square",
        ))

    # Rollback
    if execution_record.rollback_performed and execution_record.rollback_record:
        seq += 1
        events.append(IncidentTimelineEvent(
            sequence=seq,
            event="Rollback Performed",
            agent="RollbackEngine",
            status="SUCCESS",
            detail=execution_record.rollback_record.get("reason", ""),
            icon="rotate-ccw",
        ))

    # Escalation
    if execution_record.escalation_performed and execution_record.escalation_record:
        seq += 1
        events.append(IncidentTimelineEvent(
            sequence=seq,
            event=f"Auto-Escalated: Level {execution_record.escalation_record.get('level','')}",
            agent="EscalationAgent",
            status="SUCCESS",
            detail="; ".join(execution_record.escalation_record.get("reasons", [])[:2]),
            icon="trending-up",
        ))

    # Notifications
    for n in notifications:
        seq += 1
        events.append(IncidentTimelineEvent(
            sequence=seq,
            event=f"Notification Sent to {n.recipient_type.title()}",
            agent="NotificationAgent",
            status="SUCCESS" if n.status == "SENT" else "FAILURE",
            detail=f"Channel: {n.channel} | Subject: {n.subject[:60]}",
            icon="bell",
        ))

    # Final event
    seq += 1
    final_status = execution_record.final_status or execution_record.status
    if final_status == "COMPLETED":
        events.append(IncidentTimelineEvent(
            sequence=seq, event="Case Closed", agent="System",
            status="SUCCESS", detail="Complaint fully resolved by autonomous workflow.", icon="check",
        ))
    elif final_status == "ESCALATED":
        events.append(IncidentTimelineEvent(
            sequence=seq, event="Case Escalated — Awaiting Human Review", agent="System",
            status="PENDING", detail="Routed to appropriate team queue.", icon="users",
        ))
    else:
        events.append(IncidentTimelineEvent(
            sequence=seq, event="Case Requires Attention", agent="System",
            status="FAILURE", detail="Manual intervention recommended.", icon="alert-circle",
        ))

    return [e.model_dump() for e in events]


# ─────────────────────────────────────────────────────────────────────────────
# Feature 11: Adaptive Learning Data Collection
# ─────────────────────────────────────────────────────────────────────────────

async def _record_learning_signal(
    execution_record: ExecutionRecord,
    analysis: dict[str, Any],
) -> None:
    """Feature 11: Store execution outcome for future analytics and model tuning."""
    try:
        signal = {
            "id": new_id(),
            "execution_id": execution_record.id,
            "complaint_id": execution_record.complaint_id,
            "timestamp": utcnow_iso(),
            "action": execution_record.action,
            "action_type": execution_record.action_type,
            "intent": analysis.get("intent", ""),
            "domain": analysis.get("department", ""),
            "severity": analysis.get("severity", ""),
            "risk_score": analysis.get("risk_score", 0),
            "risk_category": analysis.get("risk_category", ""),
            "recommendation_confidence": analysis.get("recommendation_confidence", 0),
            "final_status": execution_record.final_status,
            "retry_count": execution_record.retry_count,
            "verification_status": execution_record.verification_status,
            "escalation_performed": execution_record.escalation_performed,
            "rollback_performed": execution_record.rollback_performed,
            "duration_ms": execution_record.duration_ms,
            "outcome_signal": execution_record.outcome_signal,
            "outcome_tags": execution_record.outcome_tags,
            # Tags for analytics grouping
            "tags": {
                "was_auto_resolved": execution_record.final_status == "COMPLETED"
                    and not execution_record.escalation_performed,
                "needed_retry": execution_record.retry_count > 0,
                "needed_escalation": execution_record.escalation_performed,
                "needed_rollback": execution_record.rollback_performed,
                "verification_failed": execution_record.verification_status == "FAILED",
            },
        }
        db = get_db()
        await db.learning_signals.insert_one(signal)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist learning signal: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Main Self-Healing Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def run_self_healing(
    complaint_id: str,
    analysis: dict[str, Any],
    complaint_doc: dict[str, Any],
    simulator_mode: bool = True,
) -> ExecutionRecord:
    """Entry point: run the full autonomous self-healing pipeline.

    Called as a background task after AI analysis completes.
    Never raises — all errors are captured in the ExecutionRecord.

    Args:
        complaint_id: MongoDB complaint document ID.
        analysis: The ComplaintAnalysis dict from agent_workflow.
        complaint_doc: Full complaint MongoDB document.
        simulator_mode: If True, use mock APIs only.

    Returns:
        ExecutionRecord with complete history.
    """
    exec_cfg = get_execution_cfg()
    t_total = time.time()

    # Resolve action
    action = analysis.get("recommendation_action") or "Escalation"
    intent = analysis.get("intent") or ""
    action_type = resolve_action_type(action, intent)
    exec_id = new_id()

    # Prepare execution context
    context: dict[str, Any] = {
        "complaint_id": complaint_id,
        "action": action,
        "action_type": action_type,
        "intent": intent,
        "entities": analysis.get("entities") or [],
        "severity": analysis.get("severity") or "medium",
        "priority": analysis.get("priority") or "medium",
        "risk_score": analysis.get("risk_score") or 0,
        "risk_category": analysis.get("risk_category") or "Low",
        "customer_name": complaint_doc.get("customer_name"),
    }

    # Create execution record
    record = ExecutionRecord(
        id=exec_id,
        complaint_id=complaint_id,
        action=action,
        action_type=action_type,
        status="NEW",
        simulator_mode=simulator_mode,
    )

    audit_entries: list[AuditEntry] = []
    notifications: list[NotificationRecord] = []
    agent_trace = analysis.get("agent_trace") or []

    def _audit(
        agent: str,
        step: str,
        state_before: str,
        state_after: str,
        decision: str = "",
        output: dict | None = None,
        status_val: str = "SUCCESS",
        error: str | None = None,
        confidence: float | None = None,
        retry_count: int = 0,
    ) -> AuditEntry:
        entry = AuditEntry(
            execution_id=exec_id,
            complaint_id=complaint_id,
            agent=agent,
            step=step,
            state_before=state_before,
            state_after=state_after,
            output_summary=output or {},
            decision=decision,
            confidence=confidence,
            execution_time_ms=_ms(t_total),
            status=status_val,
            retry_count=retry_count,
            error=error,
        )
        audit_entries.append(entry)
        return entry

    # ── Check: should we auto-execute? ──────────────────────────────────────
    auto_execute = exec_cfg.auto_execute
    escalation_reasons: list[str] = []

    # Collect pre-existing escalation reasons from analysis
    if analysis.get("escalation_required"):
        escalation_reasons.append(analysis.get("escalation_reason") or "AI analysis recommends escalation")
    if analysis.get("human_review_required"):
        escalation_reasons.append("Human review required (low confidence)")

    # Risk threshold check
    risk_score = int(analysis.get("risk_score") or 0)
    if risk_score >= exec_cfg.escalation_risk_threshold:
        escalation_reasons.append(f"Risk score {risk_score}/100 ≥ threshold {exec_cfg.escalation_risk_threshold}")

    # Confidence check
    rec_conf = float(analysis.get("recommendation_confidence") or 0.7)
    if rec_conf < exec_cfg.escalation_confidence_threshold:
        escalation_reasons.append(
            f"Recommendation confidence {int(rec_conf*100)}% < threshold {int(exec_cfg.escalation_confidence_threshold*100)}%"
        )

    # ── State: PROCESSING ────────────────────────────────────────────────────
    record.status = "PROCESSING"
    await _persist_execution(record)
    _audit("SelfHealingOrchestrator", "Initialise", "NEW", "PROCESSING",
           decision=f"action={action} type={action_type} auto_execute={auto_execute}")

    # ── Immediate escalation if warranted ────────────────────────────────────
    if escalation_reasons and not auto_execute:
        record.status = "ESCALATED"
        esc = await _auto_escalate(complaint_id, exec_id, escalation_reasons, analysis, exec_cfg)
        record.escalation_performed = True
        record.escalation_record = esc.model_dump()
        _audit("EscalationAgent", "Auto-escalate (pre-execution)", "PROCESSING", "ESCALATED",
               decision=f"Level {esc.level}", output={"reasons": escalation_reasons})
        record.final_status = "ESCALATED"
        record.outcome_signal = "ESCALATED"
        record.outcome_tags = ["pre_execution_escalation"]
        notifications = await _notify_all(
            exec_id, complaint_id, action, {}, "ESCALATED", analysis, complaint_doc, exec_cfg
        )
        record.notifications_sent = [n.model_dump() for n in notifications]
        record.completed_at = _now()
        record.duration_ms = _ms(t_total)
        record.timeline = _build_timeline(agent_trace, record, notifications)
        await _persist_execution(record)
        for e in audit_entries:
            await _persist_audit(e)
        await _record_learning_signal(record, analysis)
        await _update_complaint_execution_ref(complaint_id, record)
        return record

    # ── Feature 1: Execute Action ────────────────────────────────────────────
    record.status = "EXECUTING"
    await _persist_execution(record)
    _audit("ActionExecutionAgent", "Execute action", "PROCESSING", "EXECUTING",
           decision=f"action_type={action_type}")

    t_exec = time.time()
    raw_result = await execute_action(action_type, context)
    exec_duration = _ms(t_exec)

    action_result = ActionResult(
        execution_id=exec_id,
        complaint_id=complaint_id,
        action=action,
        action_type=action_type,
        status="COMPLETED" if raw_result.get("status") == "COMPLETED" else "FAILED",
        details=raw_result,
        mock=simulator_mode,
        error=raw_result.get("error"),
    )
    record.action_result = raw_result
    _audit("ActionExecutionAgent", "Action result", "EXECUTING", "VERIFYING",
           decision=action_result.status,
           output={"status": action_result.status, "workflow": raw_result.get("workflow")},
           status_val="SUCCESS" if action_result.status == "COMPLETED" else "FAILURE",
           error=action_result.error)

    # ── Feature 2: Verify ────────────────────────────────────────────────────
    record.status = "VERIFYING"
    await _persist_execution(record)

    verification = await _verify_action(action_result, context, exec_cfg)
    record.verification_status = verification.verification_status
    record.verification_result = verification.model_dump()
    _audit("WorkflowVerificationAgent", "Verify execution", "EXECUTING", "VERIFYING",
           decision=verification.verification_status,
           output={"status": verification.verification_status, "checks": len(verification.checks)},
           verification_status=verification.verification_status)

    # ── Feature 3: Retry loop ────────────────────────────────────────────────
    retry_count = 0
    retry_history: list[dict] = []

    while (
        verification.verification_status in ("FAILED", "TIMEOUT")
        and retry_count < exec_cfg.max_retries
    ):
        retry_count += 1
        delay = exec_cfg.retry_delay_seconds * (exec_cfg.retry_backoff_factor ** (retry_count - 1))
        record.status = "RETRYING"
        await _persist_execution(record)

        retry_rec = RetryRecord(
            attempt=retry_count,
            reason=verification.reasoning,
            delay_seconds=delay,
        )

        _audit("RetryEngine", f"Retry attempt {retry_count}", "VERIFYING", "RETRYING",
               decision=f"delay={delay:.1f}s", retry_count=retry_count)

        await asyncio.sleep(delay)

        # Re-execute
        record.status = "EXECUTING"
        raw_result = await execute_action(action_type, context)
        action_result = ActionResult(
            execution_id=exec_id,
            complaint_id=complaint_id,
            action=action,
            action_type=action_type,
            status="COMPLETED" if raw_result.get("status") == "COMPLETED" else "FAILED",
            details=raw_result,
            mock=simulator_mode,
            error=raw_result.get("error"),
        )
        record.action_result = raw_result

        # Re-verify
        verification = await _verify_action(action_result, context, exec_cfg)
        record.verification_status = verification.verification_status
        record.verification_result = verification.model_dump()

        retry_rec.outcome = "SUCCEEDED" if verification.verification_status == "SUCCESS" else "FAILED"
        retry_history.append(retry_rec.model_dump())

        _audit("RetryEngine", f"Retry {retry_count} result", "RETRYING", "VERIFYING",
               decision=f"verification={verification.verification_status}",
               retry_count=retry_count,
               verification_status=verification.verification_status)

    record.retry_count = retry_count
    record.retry_history = retry_history

    # ── Feature 4: Rollback if exhausted retries ──────────────────────────
    if verification.verification_status in ("FAILED", "TIMEOUT") and retry_count >= exec_cfg.max_retries:
        rollback = await _perform_rollback(action_result, reason=verification.reasoning)
        record.rollback_performed = rollback.status == "COMPLETED"
        record.rollback_record = rollback.model_dump()
        escalation_reasons.append(f"Action failed after {retry_count} retries")
        _audit("RollbackEngine", "Perform rollback", "RETRYING", "ESCALATED",
               decision=rollback.rollback_action,
               output={"status": rollback.status, "reason": rollback.reason},
               rollback_status=rollback.status)

    # ── Feature 5: Escalation decision ───────────────────────────────────────
    final_verification = verification.verification_status
    needs_escalation = (
        final_verification in ("FAILED", "TIMEOUT")
        or bool(escalation_reasons)
    )

    if needs_escalation:
        if final_verification in ("FAILED", "TIMEOUT"):
            escalation_reasons.append(f"Verification {final_verification} after {retry_count} retries")
        record.status = "ESCALATED"
        esc = await _auto_escalate(complaint_id, exec_id, escalation_reasons, analysis, exec_cfg)
        record.escalation_performed = True
        record.escalation_record = esc.model_dump()
        record.final_status = "ESCALATED"
        record.outcome_signal = "ESCALATED"
        record.outcome_tags = ["post_execution_escalation"]
        _audit("EscalationAgent", "Post-execution escalation", "VERIFYING", "ESCALATED",
               decision=f"Level {esc.level}", output={"reasons": escalation_reasons})
    else:
        record.status = "COMPLETED"
        record.final_status = "COMPLETED"
        record.outcome_signal = "SUCCESS"
        record.outcome_tags = (
            ["auto_resolved"] +
            (["with_retry"] if retry_count > 0 else []) +
            (["first_attempt"] if retry_count == 0 else [])
        )
        _audit("SelfHealingOrchestrator", "Complete", "VERIFYING", "COMPLETED",
               decision="Auto-resolved", verification_status="SUCCESS")

    # ── Feature 6: Notifications ────────────────────────────────────────────
    notifications = await _notify_all(
        exec_id, complaint_id, action, raw_result,
        final_verification, analysis, complaint_doc, exec_cfg
    )
    record.notifications_sent = [n.model_dump() for n in notifications]
    _audit("NotificationAgent", "Send notifications", record.status, record.status,
           decision=f"Sent {len(notifications)} notifications",
           output={"count": len(notifications)})

    # ── Finalise ────────────────────────────────────────────────────────────
    record.completed_at = _now()
    record.duration_ms = _ms(t_total)
    record.audit_trail = [e.model_dump() for e in audit_entries]

    # Feature 8: Build incident timeline
    record.timeline = _build_timeline(agent_trace, record, notifications)

    await _persist_execution(record)
    for e in audit_entries:
        await _persist_audit(e)

    # Feature 11: Learning signal
    await _record_learning_signal(record, analysis)

    # Update complaint with execution reference
    await _update_complaint_execution_ref(complaint_id, record)

    logger.info(
        "Self-healing complete: complaint=%s action=%s status=%s retries=%d duration=%dms",
        complaint_id, action, record.final_status, retry_count, record.duration_ms,
    )
    return record


async def _update_complaint_execution_ref(complaint_id: str, record: ExecutionRecord) -> None:
    """Store a reference to the execution in the complaint document."""
    try:
        db = get_db()
        await db.complaints.update_one(
            {"id": complaint_id},
            {"$set": {
                "execution_id": record.id,
                "execution_status": record.final_status or record.status,
                "updated_at": utcnow_iso(),
            },
             "$push": {"history": {
                 "at": utcnow_iso(),
                 "status": f"execution_{(record.final_status or record.status).lower()}",
                 "note": (
                     f"Self-healing [{record.action}]: "
                     f"{record.final_status or record.status} "
                     f"(retries: {record.retry_count})"
                 ),
             }}},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to update complaint execution ref: %s", exc)
