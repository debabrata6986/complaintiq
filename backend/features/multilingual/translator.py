"""Text translation using deep-translator's GoogleTranslator.

Never raises — always returns a structured dict with success/error fields.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("complaintiq.multilingual.translator")


def translate_text(text: str, source_lang: str, target_lang: str) -> dict:
    """Translate *text* from *source_lang* to *target_lang*.

    Args:
        text:        The input text to translate.
        source_lang: ISO 639-1 source language code, e.g. "hi". Use "auto" to
                     let Google detect the source language.
        target_lang: ISO 639-1 target language code, e.g. "en".

    Returns a dict with keys:
        translated_text — result string (str)
        original_text   — unchanged input (str)
        source_lang     — as provided (str)
        target_lang     — as provided (str)
        success         — True on success (bool)
        error           — error message on failure, else None (str | None)
    """
    if not text or not text.strip():
        return {
            "translated_text": text,
            "original_text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "success": False,
            "error": "Empty text provided",
        }

    # No-op if source and target are the same
    if source_lang == target_lang:
        return {
            "translated_text": text,
            "original_text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "success": True,
            "error": None,
        }

    try:
        from deep_translator import GoogleTranslator  # type: ignore[import]

        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translated = translator.translate(text)
        logger.info("Translated %d chars from %s → %s", len(text), source_lang, target_lang)
        return {
            "translated_text": translated or text,
            "original_text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "success": True,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Translation failed (%s → %s): %s", source_lang, target_lang, exc)
        return {
            "translated_text": text,  # return original on failure
            "original_text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "success": False,
            "error": str(exc),
        }
