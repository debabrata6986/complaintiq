"""Voice complaint processing pipeline.

Orchestrates: validate → transcribe → detect language.
Returns a unified result dict ready for the router.
"""
from __future__ import annotations

import logging

from features.voice.audio_validator import validate_audio_file
from features.voice.transcriber import transcribe_audio
from features.multilingual.language_detector import detect_language

logger = logging.getLogger("complaintiq.voice.pipeline")


async def process_voice_complaint(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    user_id: str,
) -> dict:
    """End-to-end voice processing pipeline.

    Args:
        audio_bytes:  Raw audio bytes from the UploadFile.
        filename:     Original filename from the upload.
        content_type: MIME type of the file.
        user_id:      ID of the authenticated user.

    Returns a dict with keys:
        transcribed_text  — final text output (str)
        detected_language — language detection result dict
        confidence        — language detection confidence (float)
        ready_to_submit   — True if there is usable text (bool)
        audio_validation  — validation result dict
        transcription     — raw transcription result dict
        error             — top-level error message, if any (str | None)
    """
    logger.info("Processing voice complaint from user=%s, file=%s", user_id, filename)

    # ── Step 1: Validate ────────────────────────────────────────────────────
    size_bytes = len(audio_bytes)
    validation = validate_audio_file(content_type, size_bytes, filename)

    if not validation["valid"]:
        logger.warning("Audio validation failed: %s", validation["error"])
        return {
            "transcribed_text": "",
            "detected_language": {},
            "confidence": 0.0,
            "ready_to_submit": False,
            "audio_validation": validation,
            "transcription": {},
            "error": validation["error"],
        }

    # ── Step 2: Transcribe ──────────────────────────────────────────────────
    extension = validation.get("extension", "webm")
    transcription = await transcribe_audio(audio_bytes, extension)

    if not transcription["success"] or not transcription["text"]:
        logger.warning("Transcription failed or empty: %s", transcription.get("error"))
        return {
            "transcribed_text": "",
            "detected_language": {},
            "confidence": 0.0,
            "ready_to_submit": False,
            "audio_validation": validation,
            "transcription": transcription,
            "error": transcription.get("error") or "Transcription returned empty text",
        }

    transcribed_text: str = transcription["text"]

    # ── Step 3: Detect language of transcription ────────────────────────────
    lang_result = detect_language(transcribed_text)
    confidence: float = lang_result.get("confidence", 0.0)

    logger.info(
        "Voice pipeline complete: %d chars, lang=%s (%.0f%%)",
        len(transcribed_text), lang_result.get("code"), confidence * 100,
    )

    return {
        "transcribed_text": transcribed_text,
        "detected_language": lang_result,
        "confidence": confidence,
        "ready_to_submit": True,
        "audio_validation": validation,
        "transcription": transcription,
        "error": None,
    }
