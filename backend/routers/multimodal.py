"""Multimodal Complaint Analysis API router — Phase 5 of ComplaintIQ v4.0.

Endpoints:
    POST /multimodal/analyze        — upload a file and get analysis
    GET  /multimodal/supported-types — list accepted file types
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from auth_utils import get_current_user
from models import UserPublic
from features.multimodal.multimodal_pipeline import (
    process_multimodal_file,
    PDF_TYPES,
    IMAGE_TYPES,
    TEXT_TYPES,
)

logger = logging.getLogger("complaintiq.routers.multimodal")

router = APIRouter(prefix="/multimodal", tags=["multimodal"])


@router.get("/supported-types")
async def supported_types(_user: UserPublic = Depends(get_current_user)):
    """Return the accepted MIME types grouped by category."""
    return {
        "pdf":    sorted(PDF_TYPES),
        "images": sorted(IMAGE_TYPES),
        "text":   sorted(TEXT_TYPES),
        "max_size_mb": 20,
    }


@router.post("/analyze")
async def analyze_file(
    file:    UploadFile = File(...),
    context: str        = Form(""),
    user:    UserPublic = Depends(get_current_user),
):
    """Upload a file (PDF, image, or text) and receive AI-powered analysis.

    The file is analyzed and a structured result is returned including:
    - Extracted text (from PDF/image)
    - AI description and complaint type (for images)
    - Whether the content is complaint-relevant

    The analysis result can be used to pre-fill a complaint description.
    """
    if not file.filename and not file.content_type:
        raise HTTPException(status_code=400, detail="No file provided")

    logger.info(
        "Multimodal analyze: user=%s file=%s type=%s",
        user.id, file.filename, file.content_type,
    )

    try:
        file_bytes = await file.read()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}") from exc

    result = await process_multimodal_file(
        file_bytes   = file_bytes,
        filename     = file.filename or "upload",
        mime_type    = file.content_type or "application/octet-stream",
        user_context = context.strip(),
    )

    if not result["success"] and result["file_type"] == "unsupported":
        raise HTTPException(status_code=415, detail=result["error"])

    logger.info(
        "Multimodal analysis complete: user=%s type=%s success=%s chars=%d",
        user.id, result["file_type"], result["success"],
        len(result.get("extracted_text", "")),
    )
    return result
