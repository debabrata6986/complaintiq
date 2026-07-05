"""Multimodal pipeline — routes uploaded files to the correct extractor.

Accepts any file upload and dispatches to:
    - PDF  → pdf_extractor
    - Image → image_analyzer
    - Text  → direct read

Returns a unified result dict ready for the API router.
"""
from __future__ import annotations

import logging

from features.multimodal.pdf_extractor import extract_pdf_text
from features.multimodal.image_analyzer import analyze_image

logger = logging.getLogger("complaintiq.multimodal.pipeline")

# Supported MIME types grouped by handler
PDF_TYPES   = {"application/pdf"}
IMAGE_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/gif",
    "image/webp", "image/bmp", "image/tiff",
}
TEXT_TYPES  = {
    "text/plain", "text/csv", "text/html",
    "application/json", "application/xml",
}

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def get_file_type_group(mime_type: str) -> str:
    """Return 'pdf' | 'image' | 'text' | 'unsupported'."""
    mt = mime_type.lower().split(";")[0].strip()
    if mt in PDF_TYPES:
        return "pdf"
    if mt in IMAGE_TYPES:
        return "image"
    if mt in TEXT_TYPES:
        return "text"
    return "unsupported"


async def process_multimodal_file(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    user_context: str = "",
) -> dict:
    """Dispatch a file to the correct analyzer and return a unified result.

    Returns:
        {
            success:       bool
            file_type:     "pdf" | "image" | "text" | "unsupported"
            filename:      str
            mime_type:     str
            size_bytes:    int
            extracted_text: str   — best available text from the file
            analysis:      dict   — type-specific analysis result
            error:         str | None
        }
    """
    size = len(file_bytes)
    logger.info("Multimodal pipeline: file=%s type=%s size=%d", filename, mime_type, size)

    # ── Size check ──────────────────────────────────────────────────────────
    if size > MAX_FILE_SIZE_BYTES:
        return _wrap(False, "unsupported", filename, mime_type, size, {},
                     f"File too large: {size // (1024*1024)} MB. Maximum is {MAX_FILE_SIZE_MB} MB.")

    if not file_bytes:
        return _wrap(False, "unsupported", filename, mime_type, size, {}, "Empty file")

    file_group = get_file_type_group(mime_type)

    # ── PDF ─────────────────────────────────────────────────────────────────
    if file_group == "pdf":
        result = extract_pdf_text(file_bytes)
        return _wrap(
            success       = result["success"],
            file_type     = "pdf",
            filename      = filename,
            mime_type     = mime_type,
            size          = size,
            analysis      = result,
            extracted_text= result.get("text", ""),
            error         = result.get("error"),
        )

    # ── Image ────────────────────────────────────────────────────────────────
    if file_group == "image":
        result = await analyze_image(file_bytes, mime_type, user_context)

        full_raw = result.get("full_analysis", "")

        # Strip markdown then remove document-level heading + numbered section labels
        # e.g. "Image Analysis in the Context of a Customer Complaint"
        # e.g. "1. Description of the Image"  "2. Text Visible in the Image"
        import re as _re
        clean_lines = []
        for raw_line in full_raw.splitlines():
            s = raw_line.replace("**", "").replace("## ", "").replace("# ", "").strip()
            
            # Also catch "#1.", "#2." etc which Groq sometimes generates
            s = _re.sub(r'^#\d+\.\s*', '', s)

            # Skip blank lines that would be leading whitespace
            if not s:
                clean_lines.append("")
                continue

            # Skip pure title-case heading (no sentence punctuation, mostly capitalised)
            if not _re.search(r'[.!?,;:]', s):
                words_gt3 = [w for w in s.split() if len(w) > 3]
                if words_gt3:
                    cap_ratio = sum(1 for w in words_gt3 if w[0].isupper()) / len(words_gt3)
                    if cap_ratio >= 0.6:
                        continue   # skip heading line

            clean_lines.append(s)

        # Remove leading/trailing blank lines then join
        clean_full = "\n".join(clean_lines).strip()

        return _wrap(
            success        = result["success"],
            file_type      = "image",
            filename       = filename,
            mime_type      = mime_type,
            size           = size,
            analysis       = result,
            extracted_text = clean_full[:2000] if clean_full else result.get("description", ""),
            error          = result.get("error"),
        )




    # ── Plain text ───────────────────────────────────────────────────────────
    if file_group == "text":
        try:
            text = file_bytes.decode("utf-8", errors="replace").strip()
            return _wrap(True, "text", filename, mime_type, size,
                         {"char_count": len(text)}, text)
        except Exception as exc:  # noqa: BLE001
            return _wrap(False, "text", filename, mime_type, size, {}, str(exc))

    # ── Unsupported ──────────────────────────────────────────────────────────
    supported = sorted(PDF_TYPES | IMAGE_TYPES | TEXT_TYPES)
    return _wrap(False, "unsupported", filename, mime_type, size, {},
                 f"Unsupported file type '{mime_type}'. Supported: PDF, images (JPEG/PNG/WebP), plain text.")


def _wrap(
    success: bool,
    file_type: str,
    filename: str,
    mime_type: str,
    size: int,
    analysis: dict,
    extracted_text: str = "",
    error: str | None = None,
) -> dict:
    return {
        "success":        success,
        "file_type":      file_type,
        "filename":       filename,
        "mime_type":      mime_type,
        "size_bytes":     size,
        "extracted_text": extracted_text,
        "analysis":       analysis,
        "error":          error,
    }
