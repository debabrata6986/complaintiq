"""Real-time models for WebSocket customer assistance."""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    TYPING = "TYPING"
    HINT = "HINT"
    SENTIMENT = "SENTIMENT"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"


class WSMessage(BaseModel):
    type: MessageType
    payload: dict
    session_id: str
    timestamp: float


class HintResponse(BaseModel):
    hints: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"
    category_suggestion: str = ""
    similar_complaint_count: int = 0
