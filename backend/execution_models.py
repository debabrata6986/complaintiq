"""Execution models for ComplaintIQ Autonomous Self-Healing (v3.0).

Covers:
  - Feature 7:  AuditEntry — per-step audit record
  - Feature 8:  IncidentTimelineEvent — ordered timeline
  - Feature 9:  ExecutionState — state machine with validated transitions
  - Feature 10: ExecutionRecord — stored history record
  - Feature 6:  NotificationRecord — stored notification
  - Feature 5:  EscalationRecord — structured escalation
  - Feature 4:  RollbackRecord — rollback log entry
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from models import new_id, utcnow_iso


# ─────────────────────────────────────────────────────────────────────────────
# Feature 9: Execution State Machine
# ─────────────────────────────────────────────────────────────────────────────

ExecutionStatus = Literal[
    "NEW", "PROCESSING", "ANALYZING", "RETRIEVING", "RECOMMENDING",
    "EXECUTING", "VERIFYING", "RETRYING", "ESCALATED",
    "COMPLETED", "FAILED", "CANCELLED",
]

# Valid state transitions — enforced by _validate_transition()
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "NEW":          {"PROCESSING", "CANCELLED"},
    "PROCESSING":   {"ANALYZING", "FAILED", "CANCELLED"},
    "ANALYZING":    {"RETRIEVING", "RECOMMENDING", "FAILED", "CANCELLED"},
    "RETRIEVING":   {"RECOMMENDING", "FAILED", "CANCELLED"},
    "RECOMMENDING": {"EXECUTING", "ESCALATED", "FAILED", "CANCELLED"},
    "EXECUTING":    {"VERIFYING", "RETRYING", "FAILED", "CANCELLED"},
    "VERIFYING":    {"COMPLETED", "RETRYING", "ESCALATED", "FAILED"},
    "RETRYING":     {"EXECUTING", "ESCALATED", "FAILED", "CANCELLED"},
    "ESCALATED":    {"COMPLETED", "FAILED", "CANCELLED"},
    "COMPLETED":    set(),   # terminal
    "FAILED":       set(),   # terminal
    "CANCELLED":    set(),   # terminal
}


def validate_transition(current: str, next_state: str) -> bool:
    """Return True if the transition current → next_state is valid."""
    return next_state in _VALID_TRANSITIONS.get(current, set())


# ─────────────────────────────────────────────────────────────────────────────
# Feature 7: Audit Trail Entry
# ─────────────────────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    """Complete audit record for a single workflow step."""
    id: str = Field(default_factory=new_id)
    execution_id: str
    complaint_id: str
    timestamp: str = Field(default_factory=utcnow_iso)
    agent: str
    step: str                         # human-readable step name
    state_before: str                 # ExecutionStatus before this step
    state_after: str                  # ExecutionStatus after this step
    input_summary: dict[str, Any] = {}
    output_summary: dict[str, Any] = {}
    decision: str = ""
    confidence: float | None = None
    execution_time_ms: int = 0
    status: Literal["SUCCESS", "FAILURE", "SKIPPED"] = "SUCCESS"
    retry_count: int = 0
    verification_status: str | None = None
    rollback_status: str | None = None
    escalation_status: str | None = None
    error: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Feature 8: Incident Timeline
# ─────────────────────────────────────────────────────────────────────────────

class IncidentTimelineEvent(BaseModel):
    """One event in the ordered incident timeline."""
    sequence: int
    timestamp: str = Field(default_factory=utcnow_iso)
    event: str              # e.g. "Complaint Submitted"
    agent: str
    status: Literal["SUCCESS", "FAILURE", "PENDING", "SKIPPED"] = "SUCCESS"
    detail: str = ""
    duration_ms: int = 0
    icon: str = "circle"    # hint for frontend rendering


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1 & 2: Action Execution and Verification
# ─────────────────────────────────────────────────────────────────────────────

VerificationStatus = Literal["SUCCESS", "FAILED", "PENDING", "TIMEOUT"]


class ActionResult(BaseModel):
    """Output of ActionExecutionAgent for one action."""
    execution_id: str = Field(default_factory=new_id)
    complaint_id: str
    action: str
    action_type: str          # refund | replacement | ticket | reset | etc.
    status: Literal["INITIATED", "COMPLETED", "FAILED"] = "INITIATED"
    timestamp: str = Field(default_factory=utcnow_iso)
    details: dict[str, Any] = {}
    mock: bool = True         # False when connected to real APIs
    error: str | None = None


class VerificationResult(BaseModel):
    """Output of WorkflowVerificationAgent."""
    execution_id: str
    complaint_id: str
    action: str
    verification_status: VerificationStatus
    timestamp: str = Field(default_factory=utcnow_iso)
    reasoning: str = ""
    checks: list[dict[str, Any]] = []
    verified_by: str = "WorkflowVerificationAgent"


# ─────────────────────────────────────────────────────────────────────────────
# Feature 3 & 4: Retry and Rollback
# ─────────────────────────────────────────────────────────────────────────────

class RetryRecord(BaseModel):
    """Record of a single retry attempt."""
    attempt: int
    timestamp: str = Field(default_factory=utcnow_iso)
    reason: str
    delay_seconds: float
    outcome: Literal["SUCCEEDED", "FAILED", "PENDING"] = "PENDING"


class RollbackRecord(BaseModel):
    """Feature 4: Rollback log entry."""
    id: str = Field(default_factory=new_id)
    execution_id: str
    complaint_id: str
    timestamp: str = Field(default_factory=utcnow_iso)
    reason: str
    action_rolled_back: str
    rollback_action: str
    status: Literal["COMPLETED", "FAILED", "NOT_APPLICABLE"] = "COMPLETED"
    details: dict[str, Any] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5: Escalation Record
# ─────────────────────────────────────────────────────────────────────────────

EscalationLevel = Literal["L1", "L2", "L3", "EXECUTIVE", "LEGAL", "FRAUD"]


class AutoEscalationRecord(BaseModel):
    """Feature 5: Structured escalation from the self-healing layer."""
    id: str = Field(default_factory=new_id)
    execution_id: str
    complaint_id: str
    timestamp: str = Field(default_factory=utcnow_iso)
    level: EscalationLevel
    department: str
    priority: str             # critical | high | medium | low
    queue: str
    reasons: list[str] = []
    auto_triggered: bool = True
    assigned_to: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Feature 6: Notification Record
# ─────────────────────────────────────────────────────────────────────────────

NotificationChannel = Literal["email", "sms", "push", "dashboard"]
NotificationRecipient = Literal["customer", "support", "manager", "admin"]


class NotificationRecord(BaseModel):
    """Feature 6: Stored notification entry."""
    id: str = Field(default_factory=new_id)
    execution_id: str
    complaint_id: str
    timestamp: str = Field(default_factory=utcnow_iso)
    recipient_type: NotificationRecipient
    recipient_id: str | None = None      # user_id if known
    channel: NotificationChannel
    subject: str
    body: str
    status: Literal["SENT", "FAILED", "QUEUED"] = "SENT"
    mock: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Feature 10: Execution History Record (stored in MongoDB)
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionRecord(BaseModel):
    """Complete execution history record persisted to `executions` collection."""
    id: str = Field(default_factory=new_id)
    complaint_id: str
    action: str
    action_type: str
    started_at: str = Field(default_factory=utcnow_iso)
    completed_at: str | None = None
    duration_ms: int = 0
    status: ExecutionStatus = "NEW"
    final_status: Literal["COMPLETED", "FAILED", "ESCALATED", "CANCELLED"] | None = None
    retry_count: int = 0
    retry_history: list[dict[str, Any]] = []
    verification_status: VerificationStatus | None = None
    rollback_performed: bool = False
    rollback_record: dict[str, Any] | None = None
    escalation_performed: bool = False
    escalation_record: dict[str, Any] | None = None
    action_result: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    notifications_sent: list[dict[str, Any]] = []
    audit_trail: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    # Feature 11: Learning signals
    outcome_signal: Literal["SUCCESS", "FAILURE", "ESCALATED", "PARTIAL"] | None = None
    outcome_tags: list[str] = []
    simulator_mode: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# API request/response models
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionTriggerIn(BaseModel):
    """Request body for manually triggering execution."""
    action: str | None = None           # override auto-detected action
    simulator: bool = True
    dry_run: bool = False               # validate only, don't execute


class SimulatorScenarioIn(BaseModel):
    """Feature 12: Simulator scenario request."""
    scenario: Literal[
        "refund", "replacement", "delivery_delay",
        "fraud_complaint", "technical_issue", "billing_issue",
        "password_reset", "wrong_product",
    ]
    domain: str = "ecommerce"
    description: str | None = None     # override description
    customer_name: str = "Simulator User"
