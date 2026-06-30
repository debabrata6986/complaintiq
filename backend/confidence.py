"""Decision Confidence utilities for ComplaintIQ.

Wraps raw LLM-emitted confidence scores with:
  - Normalisation to 0–1
  - Confidence label (High / Medium / Low)
  - Human-in-the-Loop (HITL) recommendation when below threshold
  - Per-agent confidence records

Usage:
    from confidence import ConfidenceRecord, make_confidence, hitl_needed

    rec = make_confidence(score=0.65, agent="IntentClassification", decision="Refund")
    if hitl_needed(rec):
        # flag for human review
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from config import cfg, confidence_label


@dataclass
class ConfidenceRecord:
    """Structured confidence result for a single AI decision."""
    agent: str
    decision: str
    score: float          # 0.0 – 1.0
    score_pct: int        # 0 – 100
    label: str            # High | Medium | Low
    human_review: bool    # True if below HITL threshold
    reason: str           # short rationale

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_confidence(
    score: float,
    agent: str,
    decision: str,
    reason: str = "",
) -> ConfidenceRecord:
    """Build a ConfidenceRecord from a raw 0-1 score."""
    score = float(score or 0.0)
    score = max(0.0, min(1.0, score))  # clamp
    label = confidence_label(score)
    human_review = score < cfg.confidence.human_review_threshold

    if not reason:
        if human_review:
            reason = (
                f"Confidence is {label} ({int(score * 100)}%). "
                f"Human review recommended (threshold: {int(cfg.confidence.human_review_threshold * 100)}%)."
            )
        else:
            reason = f"Confidence is {label} ({int(score * 100)}%). Automated processing is appropriate."

    return ConfidenceRecord(
        agent=agent,
        decision=decision,
        score=round(score, 4),
        score_pct=int(score * 100),
        label=label,
        human_review=human_review,
        reason=reason,
    )


def hitl_needed(record: ConfidenceRecord) -> bool:
    """Return True if the confidence record recommends human review."""
    return record.human_review


def aggregate_confidence(records: list[ConfidenceRecord]) -> dict[str, Any]:
    """Compute aggregate confidence across all agent decisions.

    Returns:
        {
          overall_score: float,
          overall_label: str,
          overall_human_review: bool,
          records: list[dict],
          lowest_agent: str,
          lowest_score: float,
        }
    """
    if not records:
        return {
            "overall_score": 0.5,
            "overall_label": "Medium",
            "overall_human_review": False,
            "records": [],
            "lowest_agent": None,
            "lowest_score": None,
        }

    scores = [r.score for r in records]
    overall = sum(scores) / len(scores)
    lowest = min(records, key=lambda r: r.score)

    return {
        "overall_score": round(overall, 4),
        "overall_score_pct": int(overall * 100),
        "overall_label": confidence_label(overall),
        "overall_human_review": any(r.human_review for r in records),
        "records": [r.to_dict() for r in records],
        "lowest_agent": lowest.agent,
        "lowest_score": lowest.score,
    }


def enrich_explanation_with_confidence(
    explanation: dict[str, Any],
    confidence_records: list[ConfidenceRecord],
) -> dict[str, Any]:
    """Merge confidence information into the existing explanation dict."""
    agg = aggregate_confidence(confidence_records)
    return {
        **explanation,
        "confidence_breakdown": agg,
        "human_review_required": agg["overall_human_review"],
        "hitl_reason": (
            f"Lowest confidence: {agg['lowest_agent']} at {int((agg['lowest_score'] or 0)*100)}%"
            if agg["overall_human_review"] else None
        ),
    }
