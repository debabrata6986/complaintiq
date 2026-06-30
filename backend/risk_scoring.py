"""Complaint Risk Scoring engine for ComplaintIQ.

Computes a composite Risk Score (0–100) from multiple signals and assigns
a Risk Category (Low / Medium / High / Critical).

Scoring components (weights configurable via config.py):
  - Severity         (25 %) — critical=100, high=75, medium=50, low=25
  - Priority         (20 %) — same mapping as severity
  - Sentiment        (15 %) — Negative=80, Neutral=40, Positive=10
  - Emotion          (10 %) — Angry=100, Urgent=90, Frustrated=70, Concerned=40, Happy=10
  - Urgency keywords (10 %) — binary: presence of urgency terms → 100
  - Duplicate freq   (10 %) — duplicate_score × 100
  - Customer history (10 %) — based on reopen_count & complaint history

Each component is scored 0–100 before weighting.
"""
from __future__ import annotations

import re
from typing import Any

from config import cfg, risk_category

# ---------------------------------------------------------------------------
# Urgency keyword patterns
# ---------------------------------------------------------------------------

_URGENCY_PATTERNS = re.compile(
    r"\b(urgent|immediately|emergency|asap|as soon as possible|critical|lawsuit|"
    r"legal action|court|police|fraud|stolen|scam|unacceptable|outrageous|furious|"
    r"disgusting|threatening|threatening|fed up|enough|last chance|final warning)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Component scoring helpers
# ---------------------------------------------------------------------------

_SEVERITY_SCORES = {"critical": 100, "high": 75, "medium": 50, "low": 25}
_PRIORITY_SCORES = {"critical": 100, "high": 75, "medium": 50, "low": 25}
_SENTIMENT_SCORES = {"negative": 80, "neutral": 40, "positive": 10}
_EMOTION_SCORES = {
    "angry": 100,
    "urgent": 90,
    "frustrated": 70,
    "concerned": 40,
    "happy": 10,
}


def _severity_score(severity: str) -> int:
    return _SEVERITY_SCORES.get((severity or "medium").lower(), 50)


def _priority_score(priority: str) -> int:
    return _PRIORITY_SCORES.get((priority or "medium").lower(), 50)


def _sentiment_score(sentiment: str) -> int:
    return _SENTIMENT_SCORES.get((sentiment or "negative").lower(), 40)


def _emotion_score(emotion: str) -> int:
    return _EMOTION_SCORES.get((emotion or "concerned").lower(), 40)


def _urgency_score(description: str) -> int:
    if _URGENCY_PATTERNS.search(description or ""):
        return 100
    return 0


def _duplicate_score(duplicate_score: float) -> int:
    """Convert 0-1 similarity score to 0-100 risk contribution."""
    return int(min(100, max(0, float(duplicate_score or 0.0) * 100)))


def _history_score(reopen_count: int, history: list[dict[str, Any]]) -> int:
    """Score based on customer complaint history.

    More reopens and escalations → higher risk.
    """
    score = 0
    score += min(60, (reopen_count or 0) * 20)  # up to 60 for 3+ reopens
    escalation_events = sum(
        1 for h in (history or []) if (h.get("status") or "") in ("escalated", "reopened")
    )
    score += min(40, escalation_events * 15)
    return min(100, score)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def compute_risk_score(
    *,
    severity: str,
    priority: str,
    sentiment: str,
    emotion: str,
    description: str,
    duplicate_score: float = 0.0,
    reopen_count: int = 0,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute composite risk score and return full breakdown.

    Returns:
        {
          "risk_score": int (0-100),
          "risk_category": str ("Low"|"Medium"|"High"|"Critical"),
          "components": { component_name: { raw_score, weight, weighted_score } },
          "explanation": str,
        }
    """
    history = history or []
    rc = cfg.risk  # RiskConfig weights

    components: dict[str, dict[str, Any]] = {
        "severity": {
            "raw_score": _severity_score(severity),
            "weight": rc.weight_severity,
            "label": severity,
        },
        "priority": {
            "raw_score": _priority_score(priority),
            "weight": rc.weight_priority,
            "label": priority,
        },
        "sentiment": {
            "raw_score": _sentiment_score(sentiment),
            "weight": rc.weight_sentiment,
            "label": sentiment,
        },
        "emotion": {
            "raw_score": _emotion_score(emotion),
            "weight": rc.weight_emotion,
            "label": emotion,
        },
        "urgency_keywords": {
            "raw_score": _urgency_score(description),
            "weight": rc.weight_urgency,
            "label": "detected" if _urgency_score(description) else "none",
        },
        "duplicate_frequency": {
            "raw_score": _duplicate_score(duplicate_score),
            "weight": rc.weight_duplicate,
            "label": f"{duplicate_score:.2f} similarity",
        },
        "customer_history": {
            "raw_score": _history_score(reopen_count, history),
            "weight": rc.weight_history,
            "label": f"{reopen_count} reopens, {len(history)} events",
        },
    }

    # Weighted composite
    total = sum(
        c["raw_score"] * c["weight"] for c in components.values()
    )
    risk_score = int(round(min(100, max(0, total))))
    category = risk_category(risk_score)

    # Compute per-component weighted scores for display
    for c in components.values():
        c["weighted_score"] = round(c["raw_score"] * c["weight"], 1)

    # Human-readable explanation
    top_drivers = sorted(components.items(), key=lambda x: x[1]["weighted_score"], reverse=True)[:3]
    driver_parts = [
        f"{name.replace('_', ' ').title()} ({c['label']}, +{c['weighted_score']:.0f} pts)"
        for name, c in top_drivers
    ]
    explanation = (
        f"Risk Score: {risk_score}/100 ({category}). "
        f"Top drivers: {'; '.join(driver_parts)}."
    )

    return {
        "risk_score": risk_score,
        "risk_category": category,
        "components": components,
        "explanation": explanation,
    }
