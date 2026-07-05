"""Lightweight preview of a complaint for real-time analysis."""
from __future__ import annotations

import logging
from typing import Dict, Any
from llm_client import llm_json
from hybrid_retrieval import hybrid_similar_complaints

logger = logging.getLogger("complaintiq.realtime.complaint_previewer")

async def preview_complaint(partial_text: str) -> Dict[str, Any]:
    """Lightweight LLM call to preview intent and severity, plus similar complaints count."""
    if len(partial_text.strip()) < 15:
        return {
            "likely_intent": "",
            "estimated_severity": "low",
            "similar_complaints_count": 0
        }
        
    system = "You are a customer support AI analyzer. Respond ONLY in JSON."
    user = f"""Given this partial complaint: '{partial_text}', return JSON:
{{
    "likely_intent": "<string describing what the user wants>",
    "estimated_severity": "low" | "medium" | "high" | "critical"
}}"""

    try:
        out = await llm_json(system, user, max_tokens=150)
        
        similar = hybrid_similar_complaints(partial_text, top_k=3, similarity_threshold=0.7)
        similar_count = len(similar) if similar else 0
        
        return {
            "likely_intent": out.get("likely_intent", ""),
            "estimated_severity": out.get("estimated_severity", "low"),
            "similar_complaints_count": similar_count
        }
    except Exception as e:
        logger.error("Error in complaint previewer: %s", e)
        return {
            "likely_intent": "",
            "estimated_severity": "low",
            "similar_complaints_count": 0
        }
