"""ComplaintIQ FastAPI server entrypoint."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter
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
import seed as seed_module  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("complaintiq")

app = FastAPI(title="ComplaintIQ API", version="3.0.0")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"app": "ComplaintIQ", "status": "online", "version": "3.0.0"}


@api_router.get("/health")
async def health():
    try:
        await get_db().command("ping")
        return {"status": "ok"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "error": str(e)}


api_router.include_router(auth_router)
api_router.include_router(complaints_router)
api_router.include_router(actions_router)
api_router.include_router(knowledge_router)
api_router.include_router(analytics_router)
api_router.include_router(self_healing_router)  # v3.0

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _background_index():
    """Background task: index all existing KB docs and complaints into ChromaDB.

    Feature 10: Background indexing so the server starts fast.
    """
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

    # Feature 10: Background indexing — non-blocking
    asyncio.create_task(_background_index())


@app.on_event("shutdown")
async def on_shutdown():
    await close_client()
