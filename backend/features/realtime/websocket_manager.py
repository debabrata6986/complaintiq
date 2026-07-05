"""Connection manager for WebSocket sessions."""
from __future__ import annotations

import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger("complaintiq.realtime.websocket_manager")

class ConnectionManager:
    def __init__(self):
        # {session_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("WebSocket connected for session %s", session_id)

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info("WebSocket disconnected for session %s", session_id)

    async def send_to_session(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
            except Exception as e:
                logger.error("Error sending to session %s: %s", session_id, e)

    async def broadcast(self, message: dict):
        for session_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error("Error broadcasting to session %s: %s", session_id, e)

manager = ConnectionManager()
