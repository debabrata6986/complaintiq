"""Multilingual agent — orchestrates detection + translation into a single pipeline.

Detects the input language, translates to English when needed, and returns a
structured context dict that downstream NLP agents can consume directly.
"""
from __future__ import annotations

import logging

from features.multilingual.language_detector import detect_language
from features.multilingual.translator import translate_text

logger = logging.getLogger("complaintiq.multilingual.agent")


async def run_multilingual_pipeline(
    text: str,
    preferred_response_lang: str = "en",
) -> dict:
    """Run the full multilingual pre-processing pipeline.

    Args:
        text:                   The raw complaint text (any language).
        preferred_response_lang: ISO 639-1 code for the language the customer
                                 prefers for responses. Defaults to "en".

    Returns a dict with keys:
        original_text        — unchanged input (str)
        english_text         — English translation (or original if already English) (str)
        detected_language    — full detection result dict (dict)
        will_respond_in      — preferred_response_lang code (str)
        translation_applied  — True if translation was performed (bool)
        translation_error    — error message if translation failed, else None (str | None)
    """
    logger.info("Running multilingual pipeline on %d-char text", len(text))

    # Step 1 — Detect language
    detected = detect_language(text)
    detected_code: str = detected.get("code", "en")

    # Step 2 — Translate to English when not already English
    translation_applied = False
    translation_error = None
    english_text = text

    if detected_code not in ("en", "unknown") and not detected.get("fallback", False):
        src = detected_code if detected_code else "auto"
        result = translate_text(text, source_lang=src, target_lang="en")
        if result["success"]:
            english_text = result["translated_text"]
            translation_applied = True
            logger.info("Translation applied: %s → en", detected_code)
        else:
            translation_error = result["error"]
            logger.warning("Translation failed, using original text: %s", translation_error)
    elif detected_code == "unknown":
        # Try auto-detect via deep_translator
        result = translate_text(text, source_lang="auto", target_lang="en")
        if result["success"]:
            english_text = result["translated_text"]
            translation_applied = True

    return {
        "original_text": text,
        "english_text": english_text,
        "detected_language": detected,
        "will_respond_in": preferred_response_lang,
        "translation_applied": translation_applied,
        "translation_error": translation_error,
    }
