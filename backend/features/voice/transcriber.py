"""Audio transcription via Groq's Whisper API.

Uses the same EMERGENT_LLM_KEY that the rest of the backend uses.
Never raises — wraps all errors in a structured return dict.
"""
from __future__ import annotations

import io
import logging
import os

logger = logging.getLogger("complaintiq.voice.transcriber")


async def transcribe_audio(
    audio_bytes: bytes,
    file_extension: str,
    language_hint: str | None = None,
) -> dict:
    """Transcribe audio bytes using Groq's Whisper large-v3 model.

    Args:
        audio_bytes:    Raw audio data.
        file_extension: File extension without dot, e.g. "webm", "mp3", "wav".
        language_hint:  Optional ISO 639-1 code to hint Whisper's language.

    Returns a dict with keys:
        text              — transcribed text (str)
        language          — detected language code from Whisper (str)
        duration_seconds  — audio duration in seconds, if available (float | None)
        success           — True on success (bool)
        error             — error message on failure (str | None)
    """
    if not audio_bytes:
        return {
            "text": "",
            "language": None,
            "duration_seconds": None,
            "success": False,
            "error": "No audio data provided",
        }

    try:
        from groq import AsyncGroq  # type: ignore[import]

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise ValueError("EMERGENT_LLM_KEY environment variable is not set")

        client = AsyncGroq(api_key=api_key)

        # Build the in-memory file tuple: (filename, bytes, mime_type)
        filename = f"audio.{file_extension or 'webm'}"
        file_tuple = (filename, io.BytesIO(audio_bytes), f"audio/{file_extension or 'webm'}")

        kwargs: dict = {
            "model": "whisper-large-v3",
            "file": file_tuple,
            "response_format": "verbose_json",
        }
        if language_hint:
            kwargs["language"] = language_hint

        logger.info("Sending %d bytes to Groq Whisper (ext=%s)", len(audio_bytes), file_extension)
        response = await client.audio.transcriptions.create(**kwargs)

        # verbose_json returns an object with .text, .language, .duration, .segments
        text: str = getattr(response, "text", "") or ""
        language: str = getattr(response, "language", None) or ""
        duration: float | None = getattr(response, "duration", None)

        logger.info(
            "Transcription complete: %d chars, lang=%s, duration=%.1fs",
            len(text), language, duration or 0,
        )
        return {
            "text": text.strip(),
            "language": language,
            "duration_seconds": float(duration) if duration is not None else None,
            "success": True,
            "error": None,
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("Transcription failed: %s", exc)
        return {
            "text": "",
            "language": None,
            "duration_seconds": None,
            "success": False,
            "error": str(exc),
        }
