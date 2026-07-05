"""Voice complaint API router — Phase 2 of ComplaintIQ v4.0.

Endpoints:
    POST /voice/transcribe        — upload audio file, returns transcription
    GET  /voice/supported-formats — list accepted audio MIME types
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth_utils import get_current_user
from models import UserPublic
from features.voice.audio_validator import ALLOWED_MIME_TYPES
from features.voice.voice_pipeline import process_voice_complaint

logger = logging.getLogger("complaintiq.routers.voice")

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/supported-formats")
async def supported_formats(_user: UserPublic = Depends(get_current_user)):
    """Return the list of accepted audio MIME types."""
    return {
        "accepted_types": sorted(ALLOWED_MIME_TYPES),
        "max_size_mb": 25,
        "hint": "Use audio/webm for browser recordings, audio/wav or audio/mpeg for uploads.",
    }


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    user: UserPublic = Depends(get_current_user),
):
    """Upload an audio file and receive a transcription.

    Accepts multipart/form-data with a single audio file field.
    Returns the full voice pipeline result including language detection.
    """
    if not file.filename and not file.content_type:
        raise HTTPException(status_code=400, detail="No file provided")

    logger.info(
        "Transcribe request: user=%s file=%s type=%s",
        user.id, file.filename, file.content_type,
    )

    try:
        audio_bytes = await file.read()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read upload: %s", exc)
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}") from exc

    result = await process_voice_complaint(
        audio_bytes=audio_bytes,
        filename=file.filename or "audio.webm",
        content_type=file.content_type or "audio/webm",
        user_id=user.id,
    )

    if not result.get("ready_to_submit") and result.get("error"):
        # Return 422 so the frontend can show a user-facing error
        raise HTTPException(status_code=422, detail=result["error"])

    logger.info(
        "Transcription complete for user=%s: %d chars, ready=%s",
        user.id, len(result.get("transcribed_text", "")), result.get("ready_to_submit"),
    )
    return result
