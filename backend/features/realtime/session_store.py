"""In-memory session store for active WebSocket connections."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger("complaintiq.realtime.session_store")

# {session_id: {user_id: str, connected_at: float, last_text: str, hint_cache: dict}}
_sessions: Dict[str, Dict[str, Any]] = {}
_lock = asyncio.Lock()


async def create_session(session_id: str, user_id: str) -> None:
    """Initialize a new session in the store."""
    import time
    async with _lock:
        _sessions[session_id] = {
            "user_id": user_id,
            "connected_at": time.time(),
            "last_text": "",
            "hint_cache": None,
        }
    logger.info("Session %s created for user %s", session_id, user_id)


async def update_session(session_id: str, text: str) -> None:
    """Update the latest text for a session."""
    async with _lock:
        if session_id in _sessions:
            _sessions[session_id]["last_text"] = text


async def get_session(session_id: str) -> Dict[str, Any] | None:
    """Retrieve session data."""
    async with _lock:
        return _sessions.get(session_id)


async def delete_session(session_id: str) -> None:
    """Remove a session from the store."""
    async with _lock:
        if session_id in _sessions:
            del _sessions[session_id]
    logger.info("Session %s deleted", session_id)
