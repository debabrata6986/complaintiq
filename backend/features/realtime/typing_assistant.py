"""Provides real-time typing hints for the WebSocket assistant."""
from __future__ import annotations

import logging
from typing import Dict, Any
from .realtime_models import HintResponse
from llm_client import llm_json
from .session_store import get_session, update_session

logger = logging.getLogger("complaintiq.realtime.typing_assistant")

async def get_typing_hints(partial_text: str, session_id: str) -> HintResponse:
    """Generate hints based on the partial complaint text."""
    # Minimum 15 chars before calling LLM
    if len(partial_text.strip()) < 15:
        return HintResponse()
        
    session = await get_session(session_id)
    if session:
        # Simple cache: if text hasn't changed much or exactly the same, maybe return cached.
        # But actually, the prompt says: "if text hasn't changed since last call, return cached response"
        # Since it's typing, we get called on debounce, text usually changes.
        cached_hints = session.get("hint_cache")
        if cached_hints and session.get("last_text") == partial_text:
            return HintResponse(**cached_hints)
            
    system = "You are a customer support AI assistant. Respond ONLY in valid JSON."
    user = f"""Given this partial complaint: '{partial_text}', return JSON:
{{
    "sentiment": "positive" | "negative" | "neutral",
    "category_suggestion": "<string>",
    "hints": ["<up to 3 actionable next steps the customer might need>"]
}}"""

    try:
        out = await llm_json(system, user, max_tokens=250)
        
        # Build response
        sentiment = out.get("sentiment", "neutral").lower()
        if sentiment not in ["positive", "negative", "neutral"]:
            sentiment = "neutral"
            
        response = HintResponse(
            hints=out.get("hints", [])[:3],
            sentiment=sentiment,
            category_suggestion=out.get("category_suggestion", ""),
            similar_complaint_count=0  # Handled by previewer if needed, or we can fetch here
        )
        
        if session:
            await update_session(session_id, partial_text)
            session["hint_cache"] = response.model_dump()
            
        return response
    except Exception as e:
        logger.error("Error generating typing hints: %s", e)
        return HintResponse()
