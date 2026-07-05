"""Language detection for ComplaintIQ multilingual pipeline.

Uses the langdetect library with a graceful fallback to English
if detection fails or the input text is too short.
"""
from __future__ import annotations

import logging

from features.multilingual.supported_languages import (
    SUPPORTED_LANGUAGES,
    get_language_name,
    is_supported,
)

logger = logging.getLogger("complaintiq.multilingual.detector")

_MIN_TEXT_LENGTH = 10

# Seed langdetect for deterministic results (must be done at module init)
try:
    from langdetect import DetectorFactory  # type: ignore[import]
    DetectorFactory.seed = 0
except Exception:  # noqa: BLE001
    pass


def detect_language(text: str) -> dict:
    """Detect the language of *text* and return structured metadata.

    Returns a dict with keys:
        code         — ISO 639-1 code (str)
        name         — human-readable language name (str)
        confidence   — detection confidence 0.0–1.0 (float)
        is_supported — whether the code is in SUPPORTED_LANGUAGES (bool)
        fallback     — True when detection was skipped / failed (bool)
    """
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        logger.debug("Text too short for detection (%d chars), returning unknown", len(text or ""))
        return {
            "code": "unknown",
            "name": "Unknown",
            "confidence": 0.0,
            "is_supported": False,
            "fallback": True,
        }

    try:
        from langdetect import detect_langs  # type: ignore[import]

        results = detect_langs(text)
        if not results:
            raise ValueError("langdetect returned empty results")

        top = results[0]
        code: str = top.lang
        confidence: float = round(float(top.prob), 4)

        logger.info("Detected language: %s (conf=%.2f) for text snippet: %.40r", code, confidence, text)
        return {
            "code": code,
            "name": get_language_name(code),
            "confidence": confidence,
            "is_supported": is_supported(code),
            "fallback": False,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Language detection failed: %s — falling back to English", exc)
        return {
            "code": "en",
            "name": "English",
            "confidence": 0.0,
            "is_supported": True,
            "fallback": True,
        }
