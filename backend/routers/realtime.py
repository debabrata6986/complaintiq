"""Real-time WebSocket router for customer assistance."""
from __future__ import annotations

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from pydantic import BaseModel
from features.realtime.websocket_manager import manager
from features.realtime.session_store import create_session, delete_session
from features.realtime.realtime_models import MessageType, WSMessage
from features.realtime.typing_assistant import get_typing_hints
from features.realtime.complaint_previewer import preview_complaint

logger = logging.getLogger("complaintiq.routers.realtime")
router = APIRouter(prefix="/realtime", tags=["realtime"])


class HintRequest(BaseModel):
    text: str
    session_id: str


@router.post("/hint")
async def get_hint(req: HintRequest):
    """HTTP fallback for browsers without WS support."""
    hints = await get_typing_hints(req.text, req.session_id)
    preview = await preview_complaint(req.text)
    
    hints.similar_complaint_count = preview.get("similar_complaints_count", 0)
    return hints.model_dump()


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get session state."""
    from features.realtime.session_store import get_session
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# Note: The WebSocket route WS /ws/{session_id} is implemented in server.py directly
# to avoid API router websocket mounting issues, as per instructions.
