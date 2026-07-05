"""PDF text extractor — uses PyMuPDF (fitz) to extract text from PDF files.

Falls back to a structured error dict if the library is unavailable or the
file is corrupt. Never raises.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("complaintiq.multimodal.pdf")

# Max pages to extract (prevent huge PDFs from stalling the server)
_MAX_PAGES = 20


def extract_pdf_text(pdf_bytes: bytes) -> dict:
    """Extract all text from a PDF byte string.

    Returns:
        {
            success:      bool
            text:         str   — full concatenated text across pages
            page_count:   int
            pages:        list[{page: int, text: str}]
            char_count:   int
            error:        str | None
        }
    """
    if not pdf_bytes:
        return {"success": False, "text": "", "page_count": 0, "pages": [], "char_count": 0, "error": "No PDF data provided"}

    try:
        import fitz  # type: ignore[import]   # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = min(len(doc), _MAX_PAGES)
        pages_out  = []
        full_text  = []

        for i in range(page_count):
            page = doc[i]
            text = page.get_text("text").strip()
            pages_out.append({"page": i + 1, "text": text})
            if text:
                full_text.append(text)

        doc.close()
        combined = "\n\n".join(full_text)

        logger.info("PDF extracted: %d pages, %d chars", page_count, len(combined))
        return {
            "success":    True,
            "text":       combined,
            "page_count": page_count,
            "pages":      pages_out,
            "char_count": len(combined),
            "error":      None,
        }

    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed — PDF extraction unavailable")
        return {
            "success":    False,
            "text":       "",
            "page_count": 0,
            "pages":      [],
            "char_count": 0,
            "error":      "PDF extraction requires PyMuPDF. Install with: pip install pymupdf",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("PDF extraction failed: %s", exc)
        return {
            "success":    False,
            "text":       "",
            "page_count": 0,
            "pages":      [],
            "char_count": 0,
            "error":      f"PDF extraction error: {exc}",
        }
