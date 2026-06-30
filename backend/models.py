"""Pydantic models for ComplaintIQ."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ---------- Auth ----------

Role = Literal["customer", "support", "manager", "admin"]


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: Role
    phone: str | None = None
    avatar_url: str | None = None
    created_at: str


class UserInDB(UserPublic):
    password_hash: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = None
    role: Role = "customer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------- Complaints ----------

Domain = Literal[
    "ecommerce", "banking", "telecom", "insurance",
    "healthcare", "government", "utilities"
]

Status = Literal["submitted", "analyzing", "analyzed", "assigned", "in_progress", "resolved", "rejected"]
Priority = Literal["critical", "high", "medium", "low"]


class ComplaintCreate(BaseModel):
    domain: Domain
    category: str | None = None
    description: str = Field(min_length=10, max_length=10000)
    customer_name: str | None = None
    customer_email: EmailStr | None = None
    customer_phone: str | None = None


class ComplaintEntity(BaseModel):
    type: str
    value: str


class AgentTrace(BaseModel):
    agent: str
    status: Literal["success", "failure"]
    duration_ms: int
    output: dict[str, Any] | None = None
    error: str | None = None


class ComplaintAnalysis(BaseModel):
    summary: str
    keywords: list[str] = []
    intent: str
    intent_confidence: float
    category: str
    entities: list[ComplaintEntity] = []
    sentiment: str
    sentiment_score: float
    emotion: str
    severity: Priority
    severity_reason: str
    priority: Priority
    department: str
    duplicate_score: float
    similar_complaint_ids: list[str] = []
    similar_complaints: list[dict[str, Any]] = []
    retrieved_policies: list[dict[str, Any]] = []
    # Root Cause Analysis (Feature 4)
    root_causes: list[dict[str, Any]] = []
    root_cause_summary: str = ""
    # Risk Scoring (Feature 5)
    risk_score: int = 0
    risk_category: str = "Low"
    risk_components: dict[str, Any] = {}
    risk_explanation: str = ""
    # Recommendation
    recommendation: str
    recommendation_action: str
    recommendation_confidence: float
    decision_options: list[dict[str, Any]] = []
    escalation_required: bool = False
    escalation_reason: str = ""
    routing: str = "support_review"
    manager_override: dict[str, Any] | None = None
    # Confidence + HITL (Features 6 & 7)
    confidence_records: list[dict[str, Any]] = []
    human_review_required: bool = False
    # Explainability + Responses
    explanation: dict[str, Any]
    customer_response: str
    support_notes: str
    manager_notes: str
    agent_trace: list[AgentTrace] = []


class Complaint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    domain: Domain
    category: str | None = None
    description: str
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    status: Status = "submitted"
    analysis: ComplaintAnalysis | None = None
    reopen_count: int = 0
    feedback: dict[str, Any] | None = None
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    resolved_at: str | None = None
    history: list[dict[str, Any]] = []
    # v3.0: Self-healing execution reference
    execution_id: str | None = None
    execution_status: str | None = None
    # v3.0: Simulator metadata
    simulator: bool = False
    scenario: str | None = None


class StatusUpdateIn(BaseModel):
    status: Status
    note: str | None = None


# ---------- Knowledge Base ----------

class KBDocument(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    doc_type: str  # policy, faq, sop, manual, solution
    domain: Domain | Literal["general"] = "general"
    content: str
    tags: list[str] = []
    created_at: str = Field(default_factory=utcnow_iso)


class KBDocumentCreate(BaseModel):
    title: str
    doc_type: str
    domain: Domain | Literal["general"] = "general"
    content: str
    tags: list[str] = []
