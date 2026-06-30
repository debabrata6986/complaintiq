"""Central configuration for ComplaintIQ.

All tunable parameters live here so they can be overridden via environment
variables without code changes.  Import from this module everywhere instead of
hard-coding thresholds/paths inline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmbeddingConfig:
    # Sentence-transformer model (all-MiniLM-L6-v2 is ~22 MB, fast, great quality)
    model_name: str = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    # Batch size for bulk embedding generation
    batch_size: int = int(os.environ.get("EMBEDDING_BATCH_SIZE", "64"))
    # Embedding vector dimension (all-MiniLM-L6-v2 = 384)
    dimension: int = int(os.environ.get("EMBEDDING_DIM", "384"))
    # In-process LRU cache size (number of text→embedding entries)
    cache_size: int = int(os.environ.get("EMBEDDING_CACHE_SIZE", "2000"))


@dataclass(frozen=True)
class VectorDBConfig:
    # Local path for ChromaDB persistence
    persist_directory: str = os.environ.get("CHROMA_DIR", "/tmp/complaintiq_chroma")
    # Collections
    complaints_collection: str = "complaints"
    knowledge_collection: str = "knowledge_base"
    # Top-K retrieval defaults
    top_k_complaints: int = int(os.environ.get("TOPK_COMPLAINTS", "5"))
    top_k_knowledge: int = int(os.environ.get("TOPK_KNOWLEDGE", "5"))


@dataclass(frozen=True)
class HybridRetrievalConfig:
    # Weight for semantic embedding similarity  (0-1)
    semantic_weight: float = float(os.environ.get("HYBRID_SEMANTIC_WEIGHT", "0.65"))
    # Weight for TF-IDF similarity (0-1).  Must sum with semantic_weight to 1.0
    tfidf_weight: float = float(os.environ.get("HYBRID_TFIDF_WEIGHT", "0.35"))
    # Minimum combined score to include a result
    min_score_duplicate: float = float(os.environ.get("HYBRID_MIN_SCORE_DUP", "0.15"))
    min_score_knowledge: float = float(os.environ.get("HYBRID_MIN_SCORE_KB", "0.05"))


@dataclass(frozen=True)
class RiskConfig:
    # Score thresholds for risk categories (inclusive lower bound)
    low_threshold: int = int(os.environ.get("RISK_LOW", "25"))
    medium_threshold: int = int(os.environ.get("RISK_MEDIUM", "50"))
    high_threshold: int = int(os.environ.get("RISK_HIGH", "75"))
    # Critical is anything >= high_threshold+1 but we use a separate bucket
    critical_threshold: int = int(os.environ.get("RISK_CRITICAL", "85"))

    # Weights for composite risk score components (must sum to 1.0)
    weight_severity: float = float(os.environ.get("RISK_W_SEVERITY", "0.25"))
    weight_sentiment: float = float(os.environ.get("RISK_W_SENTIMENT", "0.15"))
    weight_emotion: float = float(os.environ.get("RISK_W_EMOTION", "0.10"))
    weight_priority: float = float(os.environ.get("RISK_W_PRIORITY", "0.20"))
    weight_urgency: float = float(os.environ.get("RISK_W_URGENCY", "0.10"))
    weight_duplicate: float = float(os.environ.get("RISK_W_DUPLICATE", "0.10"))
    weight_history: float = float(os.environ.get("RISK_W_HISTORY", "0.10"))


@dataclass(frozen=True)
class ConfidenceConfig:
    # Below this → Human-in-the-Loop review is recommended
    human_review_threshold: float = float(os.environ.get("CONFIDENCE_HITL_THRESHOLD", "0.70"))
    # Labels
    high_label_threshold: float = float(os.environ.get("CONFIDENCE_HIGH", "0.80"))
    medium_label_threshold: float = float(os.environ.get("CONFIDENCE_MEDIUM", "0.60"))
    # Below medium_label_threshold → "Low"


@dataclass(frozen=True)
class RootCauseConfig:
    # Minimum confidence to include a root cause in the output
    min_confidence: float = float(os.environ.get("ROOTCAUSE_MIN_CONF", "0.40"))
    # Max number of root causes to return
    max_causes: int = int(os.environ.get("ROOTCAUSE_MAX", "3"))


@dataclass(frozen=True)
class AppConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    vector_db: VectorDBConfig = field(default_factory=VectorDBConfig)
    hybrid: HybridRetrievalConfig = field(default_factory=HybridRetrievalConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    root_cause: RootCauseConfig = field(default_factory=RootCauseConfig)


# Singleton — import and use `cfg` everywhere
cfg = AppConfig(
    embedding=EmbeddingConfig(),
    vector_db=VectorDBConfig(),
    hybrid=HybridRetrievalConfig(),
    risk=RiskConfig(),
    confidence=ConfidenceConfig(),
    root_cause=RootCauseConfig(),
)


def confidence_label(score: float) -> str:
    """Convert a 0-1 confidence score to a human-readable label."""
    if score >= cfg.confidence.high_label_threshold:
        return "High"
    if score >= cfg.confidence.medium_label_threshold:
        return "Medium"
    return "Low"


def risk_category(score: int) -> str:
    """Convert a 0-100 risk score to a category string."""
    if score >= cfg.risk.critical_threshold:
        return "Critical"
    if score >= cfg.risk.high_threshold:
        return "High"
    if score >= cfg.risk.medium_threshold:
        return "Medium"
    return "Low"


# ═══════════════════════════════════════════════════════════════════════════
# v3.0 — Autonomous Self-Healing Configuration
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExecutionConfig:
    """Feature 15: Configurable execution engine parameters."""
    # Retry settings
    max_retries: int = int(os.environ.get("EXEC_MAX_RETRIES", "3"))
    retry_delay_seconds: float = float(os.environ.get("EXEC_RETRY_DELAY", "2.0"))
    retry_backoff_factor: float = float(os.environ.get("EXEC_BACKOFF_FACTOR", "2.0"))
    # Verification
    verification_timeout_seconds: float = float(os.environ.get("EXEC_VERIFY_TIMEOUT", "30.0"))
    # Escalation
    escalation_risk_threshold: int = int(os.environ.get("EXEC_ESCALATION_RISK", "70"))
    escalation_confidence_threshold: float = float(os.environ.get("EXEC_ESCALATION_CONF", "0.65"))
    # Notifications
    notify_customer: bool = os.environ.get("NOTIFY_CUSTOMER", "true").lower() == "true"
    notify_support: bool = os.environ.get("NOTIFY_SUPPORT", "true").lower() == "true"
    notify_manager: bool = os.environ.get("NOTIFY_MANAGER", "true").lower() == "true"
    # Simulator
    simulator_mode: bool = os.environ.get("SIMULATOR_MODE", "true").lower() == "true"
    # Audit
    audit_sensitive_fields: bool = os.environ.get("AUDIT_SENSITIVE", "false").lower() == "true"
    # Auto-execution: if True, ActionExecutionAgent runs automatically after analysis
    auto_execute: bool = os.environ.get("AUTO_EXECUTE", "true").lower() == "true"
    # Actions eligible for full automation (no human gate)
    auto_actions: tuple = (
        "Refund", "Replacement", "Delivery Complaint",
        "Password Reset", "Billing Issue", "Technical Issue",
        "Wrong Product",
    )


# Extend the singleton with ExecutionConfig
_exec_cfg = ExecutionConfig()


def get_execution_cfg() -> ExecutionConfig:
    return _exec_cfg
