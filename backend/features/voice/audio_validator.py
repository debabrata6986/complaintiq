"""Audio file validation for the voice complaint pipeline.

Checks MIME type, file size, and basic sanity before handing off to transcription.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("complaintiq.voice.validator")

ALLOWED_MIME_TYPES: set[str] = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/x-wav",
    "audio/x-m4a",
}

MAX_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

MIME_TO_EXTENSION: dict[str, str] = {
    "audio/wav":   "wav",
    "audio/x-wav": "wav",
    "audio/mpeg":  "mp3",
    "audio/mp3":   "mp3",
    "audio/webm":  "webm",
    "audio/ogg":   "ogg",
    "audio/mp4":   "mp4",
    "audio/x-m4a": "m4a",
}


def validate_audio_file(content_type: str, size_bytes: int, filename: str = "") -> dict:
    """Validate an audio file upload before transcription.

    Args:
        content_type: MIME type of the uploaded file.
        size_bytes:   File size in bytes.
        filename:     Original filename (used for extension-based fallback).

    Returns a dict with keys:
        valid     — True if the file is acceptable (bool)
        error     — human-readable error message if not valid (str | None)
        file_type — normalised MIME type (str)
        extension — file extension to use when writing tempfile (str)
        size_bytes— as provided (int)
    """
    # Normalise content_type (strip parameters like "; codecs=opus")
    base_mime = content_type.split(";")[0].strip().lower() if content_type else ""

    # Extension-based fallback when browser sends generic octet-stream
    if base_mime in ("application/octet-stream", "") and filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        ext_map = {"wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg",
                   "webm": "audio/webm", "mp4": "audio/mp4", "m4a": "audio/x-m4a"}
        base_mime = ext_map.get(ext, base_mime)

    if base_mime not in ALLOWED_MIME_TYPES:
        logger.warning("Rejected audio upload: unsupported MIME type %r", base_mime)
        return {
            "valid": False,
            "error": f"Unsupported audio format '{base_mime}'. Accepted: wav, mp3, webm, ogg, mp4.",
            "file_type": base_mime,
            "extension": "",
            "size_bytes": size_bytes,
        }

    if size_bytes > MAX_SIZE_BYTES:
        logger.warning("Rejected audio upload: file too large (%d bytes)", size_bytes)
        return {
            "valid": False,
            "error": f"File too large ({size_bytes // (1024*1024)} MB). Maximum is 25 MB.",
            "file_type": base_mime,
            "extension": MIME_TO_EXTENSION.get(base_mime, "bin"),
            "size_bytes": size_bytes,
        }

    extension = MIME_TO_EXTENSION.get(base_mime, "bin")
    logger.info("Audio file validated: type=%s ext=%s size=%d bytes", base_mime, extension, size_bytes)
    return {
        "valid": True,
        "error": None,
        "file_type": base_mime,
        "extension": extension,
        "size_bytes": size_bytes,
    }
