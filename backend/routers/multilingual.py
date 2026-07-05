"""Multilingual API router — Phase 1 of ComplaintIQ v4.0.

Endpoints:
    GET  /multilingual/languages   — list all supported languages
    POST /multilingual/detect      — detect language of a text snippet
    POST /multilingual/translate   — translate between two languages
    POST /multilingual/analyze     — full multilingual pipeline
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth_utils import get_current_user
from models import UserPublic
from features.multilingual.supported_languages import SUPPORTED_LANGUAGES
from features.multilingual.language_detector import detect_language
from features.multilingual.translator import translate_text
from features.multilingual.multilingual_agent import run_multilingual_pipeline

logger = logging.getLogger("complaintiq.routers.multilingual")

router = APIRouter(prefix="/multilingual", tags=["multilingual"])


# ── Request / Response models ────────────────────────────────────────────────

class DetectRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to detect language for")


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source_lang: str = Field(..., description="ISO 639-1 source code, e.g. 'hi'")
    target_lang: str = Field(..., description="ISO 639-1 target code, e.g. 'en'")


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    preferred_lang: str = Field(default="en", description="ISO 639-1 preferred response language")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/languages")
async def list_languages(_user: UserPublic = Depends(get_current_user)):
    """Return all supported languages as a list of objects."""
    return [
        {"code": code, **meta}
        for code, meta in SUPPORTED_LANGUAGES.items()
    ]


@router.post("/detect")
async def detect(
    body: DetectRequest,
    _user: UserPublic = Depends(get_current_user),
):
    """Detect the language of the provided text."""
    result = detect_language(body.text)
    logger.info("detect/ called by user=%s, result code=%s", _user.id, result.get("code"))
    return result


@router.post("/translate")
async def translate(
    body: TranslateRequest,
    _user: UserPublic = Depends(get_current_user),
):
    """Translate text from source_lang to target_lang."""
    result = translate_text(body.text, body.source_lang, body.target_lang)
    logger.info(
        "translate/ called by user=%s: %s→%s, success=%s",
        _user.id, body.source_lang, body.target_lang, result["success"],
    )
    return result


@router.post("/analyze")
async def analyze(
    body: AnalyzeRequest,
    _user: UserPublic = Depends(get_current_user),
):
    """Run the full multilingual pipeline: detect + translate + enrich."""
    result = await run_multilingual_pipeline(body.text, body.preferred_lang)
    logger.info(
        "analyze/ called by user=%s, detected=%s, translation_applied=%s",
        _user.id,
        result["detected_language"].get("code"),
        result["translation_applied"],
    )
    return result
