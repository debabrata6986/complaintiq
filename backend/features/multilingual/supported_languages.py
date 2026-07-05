"""Supported languages for ComplaintIQ multilingual feature.

Maps ISO 639-1 language codes to metadata including display name,
native name, and writing script. Covers major Indian languages + English.
"""
from __future__ import annotations

SUPPORTED_LANGUAGES: dict[str, dict] = {
    "en": {"name": "English",    "native_name": "English",    "script": "Latin"},
    "hi": {"name": "Hindi",      "native_name": "हिन्दी",      "script": "Devanagari"},
    "bn": {"name": "Bengali",    "native_name": "বাংলা",       "script": "Bengali"},
    "ta": {"name": "Tamil",      "native_name": "தமிழ்",       "script": "Tamil"},
    "te": {"name": "Telugu",     "native_name": "తెలుగు",      "script": "Telugu"},
    "mr": {"name": "Marathi",    "native_name": "मराठी",       "script": "Devanagari"},
    "gu": {"name": "Gujarati",   "native_name": "ગુજરાતી",     "script": "Gujarati"},
    "kn": {"name": "Kannada",    "native_name": "ಕನ್ನಡ",       "script": "Kannada"},
    "ml": {"name": "Malayalam",  "native_name": "മലയാളം",      "script": "Malayalam"},
    "pa": {"name": "Punjabi",    "native_name": "ਪੰਜਾਬੀ",      "script": "Gurmukhi"},
    "ur": {"name": "Urdu",       "native_name": "اردو",        "script": "Nastaliq"},
}


def get_language_name(code: str) -> str:
    """Return the English display name for an ISO 639-1 code.

    Falls back to the code itself if not found.
    """
    entry = SUPPORTED_LANGUAGES.get(code)
    return entry["name"] if entry else code


def is_supported(code: str) -> bool:
    """Return True if the language code is in the supported set."""
    return code in SUPPORTED_LANGUAGES
