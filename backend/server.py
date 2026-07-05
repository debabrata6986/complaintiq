"""ComplaintIQ FastAPI server entrypoint."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
sys.path.insert(0, str(ROOT_DIR))

from db import close_client, get_db  # noqa: E402
from routers.auth import router as auth_router  # noqa: E402
from routers.complaints import router as complaints_router  # noqa: E402
from routers.actions import router as actions_router  # noqa: E402
from routers.knowledge import router as knowledge_router  # noqa: E402
from routers.analytics import router as analytics_router  # noqa: E402
from routers.self_healing import router as self_healing_router  # noqa: E402  v3.0

# ── v4.0 Phase 1: Multilingual ────────────────────────────────────────────
from routers.multilingual import router as multilingual_router  # noqa: E402

# ── v4.0 Phase 2: Voice ───────────────────────────────────────────────────
from routers.voice import router as voice_router  # noqa: E402

# ── v4.0 Phase 3: Enterprise Gateway ─────────────────────────────────────
from routers.enterprise import router as enterprise_router  # noqa: E402

# ── v4.0 Phase 4: Continual Learning ─────────────────────────────────────
from routers.learning import router as learning_router  # noqa: E402

# ── v4.0 Phase 5: Multi-Modal Analysis ───────────────────────────────────
from routers.multimodal import router as multimodal_router  # noqa: E402

# ── v4.0 Phase 6: Real-Time Customer Assistance ──────────────────────────
from routers.realtime import router as realtime_router  # noqa: E402

# ── v4.0 Phase 6: WebSocket imports ──────────────────────────────────────
from features.realtime.websocket_manager import manager  # noqa: E402
from features.realtime.session_store import create_session, delete_session  # noqa: E402
from features.realtime.typing_assistant import get_typing_hints  # noqa: E402
from features.realtime.complaint_previewer import preview_complaint  # noqa: E402
from features.realtime.realtime_models import MessageType  # noqa: E402

import seed as seed_module  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("complaintiq")

app = FastAPI(title="ComplaintIQ API", version="4.0.0")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"app": "ComplaintIQ", "status": "online", "version": "4.0.0"}


@api_router.get("/health")
async def health():
    try:
        await get_db().command("ping")
        return {"status": "ok"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "error": str(e)}


# ── Register ALL routers BEFORE app.include_router(api_router) ────────────
# v3.0 original routers
api_router.include_router(auth_router)
api_router.include_router(complaints_router)
api_router.include_router(actions_router)
api_router.include_router(knowledge_router)
api_router.include_router(analytics_router)
api_router.include_router(self_healing_router)

# v4.0 new routers
api_router.include_router(multilingual_router)
api_router.include_router(voice_router)
api_router.include_router(enterprise_router)
api_router.include_router(learning_router)
api_router.include_router(multimodal_router)
api_router.include_router(realtime_router)

# ── This MUST come after all api_router.include_router() calls ────────────
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _background_index():
    """Background task: index all existing KB docs and complaints into ChromaDB."""
    _log = logging.getLogger("complaintiq.startup_index")
    try:
        from vector_db import index_kb_batch, index_complaints_batch
        db = get_db()

        kb_docs = await db.kb_documents.find({}, {"_id": 0}).to_list(length=5000)
        if kb_docs:
            n = index_kb_batch(kb_docs)
            _log.info("Background indexed %d KB documents into ChromaDB", n)

        complaints = await db.complaints.find(
            {"description": {"$exists": True}},
            {"_id": 0, "id": 1, "description": 1, "domain": 1, "status": 1, "analysis": 1},
        ).to_list(length=5000)
        if complaints:
            n = index_complaints_batch(complaints)
            _log.info("Background indexed %d complaints into ChromaDB", n)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Background vector indexing failed (non-fatal): %s", exc)


@app.on_event("startup")
async def on_startup():
    try:
        result = await seed_module.run_all()
        logger.info("Seed result: %s", result)
    except Exception as e:  # noqa: BLE001
        logger.exception("Seeding failed: %s", e)

    asyncio.create_task(_background_index())


@app.on_event("shutdown")
async def on_shutdown():
    await close_client()


# ── v4.0 Phase 6 WebSocket ────────────────────────────────────────────────
@app.websocket("/api/realtime/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    await create_session(session_id, user_id="anonymous")

    await manager.send_to_session(session_id, {
        "type": MessageType.CONNECTED.value,
        "payload": {"status": "connected"},
        "session_id": session_id,
        "timestamp": time.time()
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "TYPING":
                    text = msg.get("text", "")

                    hints = await get_typing_hints(text, session_id)
                    preview = await preview_complaint(text)
                    hints.similar_complaint_count = preview.get("similar_complaints_count", 0)

                    if not hints.category_suggestion:
                        hints.category_suggestion = preview.get("likely_intent", "")

                    await manager.send_to_session(session_id, {
                        "type": MessageType.HINT.value,
                        "payload": hints.model_dump(),
                        "session_id": session_id,
                        "timestamp": time.time()
                    })
            except json.JSONDecodeError:
                continue
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        await delete_session(session_id)