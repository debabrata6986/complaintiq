"""Image analyzer — uses Groq's vision model to analyze complaint-related images.

Accepts raw image bytes, encodes as base64, and sends to the Groq chat
completion endpoint with a vision model. Returns structured analysis including:
    - Complaint relevance assessment
    - Text extracted from the image (OCR via LLM)
    - Description of what the image shows
    - Suggested complaint category

Uses EMERGENT_LLM_KEY (same as the rest of the backend).
Never raises — wraps all errors in a structured return dict.
"""
from __future__ import annotations

import base64
import logging
import os

logger = logging.getLogger("complaintiq.multimodal.image")

# Best available vision model on Groq
_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

_SYSTEM_PROMPT = """You are an expert complaint analysis assistant.
The user has uploaded an image as evidence for their complaint.
Analyze the image and provide:
1. A clear description of what the image shows
2. Any text visible in the image (receipts, invoices, order numbers, etc.)
3. Whether this image is relevant to a consumer complaint
4. What type of complaint this image most likely supports (e.g. damaged product, wrong item, billing dispute, etc.)

Be concise, factual, and structured in your response."""


async def analyze_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    user_context: str = "",
) -> dict:
    """Analyze an image using Groq's vision model.

    Args:
        image_bytes:  Raw image bytes.
        mime_type:    MIME type, e.g. "image/jpeg", "image/png".
        user_context: Optional text context from the user about the complaint.

    Returns:
        {
            success:           bool
            description:       str  — what the image shows
            extracted_text:    str  — any text visible in the image
            complaint_type:    str  — inferred complaint category
            is_relevant:       bool — whether image is complaint-relevant
            full_analysis:     str  — full LLM response
            model_used:        str
            error:             str | None
        }
    """
    if not image_bytes:
        return _error_result("No image data provided")

    try:
        from groq import AsyncGroq  # type: ignore[import]

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise ValueError("EMERGENT_LLM_KEY environment variable is not set")

        # Encode image to base64 data URL
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        data_url  = f"data:{mime_type};base64,{b64_image}"

        # Build user message
        user_text = "Please analyze this image in the context of a customer complaint."
        if user_context:
            user_text += f"\n\nUser's complaint context: {user_context}"

        client = AsyncGroq(api_key=api_key)

        logger.info("Sending image (%d bytes, %s) to Groq vision model", len(image_bytes), _VISION_MODEL)

        response = await client.chat.completions.create(
            model=_VISION_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text",      "text": user_text},
                    ],
                },
            ],
            max_tokens=1024,
            temperature=0.1,
        )

        full_text = response.choices[0].message.content or ""

        # Parse structured fields from the free-text response
        parsed = _parse_analysis(full_text)

        logger.info("Image analysis complete: relevant=%s type=%s", parsed["is_relevant"], parsed["complaint_type"])

        return {
            "success":        True,
            "description":    parsed["description"],
            "extracted_text": parsed["extracted_text"],
            "complaint_type": parsed["complaint_type"],
            "is_relevant":    parsed["is_relevant"],
            "full_analysis":  full_text,
            "model_used":     _VISION_MODEL,
            "error":          None,
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("Image analysis failed: %s", exc)
        return _error_result(str(exc))


def _parse_analysis(text: str) -> dict:
    """Extract structured fields from the LLM free-text response."""
    text_lower = text.lower()

    # Determine relevance
    is_relevant = any(kw in text_lower for kw in [
        "complaint", "defect", "damage", "wrong", "invoice", "receipt",
        "order", "bill", "broken", "missing", "fraud", "error", "dispute",
    ])

    # Infer complaint type
    complaint_type = "General"
    type_map = {
        "damaged": "Damaged Product",
        "defect":  "Defective Product",
        "wrong item": "Wrong Item",
        "invoice":    "Billing Dispute",
        "receipt":    "Billing Dispute",
        "bill":       "Billing Dispute",
        "delivery":   "Delivery Issue",
        "packaging":  "Packaging Issue",
        "fraud":      "Fraud",
        "missing":    "Missing Item",
    }
    for keyword, ctype in type_map.items():
        if keyword in text_lower:
            complaint_type = ctype
            break

    # ── Strip all markdown from full text — used as fallback description ────────
    def strip_md(t: str) -> str:
        return (
            t.replace("**", "")
             .replace("## ", "")
             .replace("# ", "")
             .strip()
        )

    lines = text.splitlines()
    stripped_lines = [strip_md(l) for l in lines]

    # ── Build description: first PARAGRAPH of real content (skip title lines) ──
    # A "title line" is short (<= 70 chars), has no period, comma, or digit,
    # and is the very first non-blank line — i.e. the document heading.
    def looks_like_title(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        if len(s) > 80:
            return False            # long lines are content, not titles
        if any(c in s for c in ".,:"):
            return False            # titles rarely have sentence punctuation
        words = s.split()
        if len(words) < 2:
            return False
        # Title-case heuristic: most words capitalised, no lowercase start
        cap_words = sum(1 for w in words if w and w[0].isupper())
        return cap_words / len(words) >= 0.6

    # Collect first real paragraph (stop at first blank line after content starts)
    desc_lines = []
    collecting = False
    for sline in stripped_lines:
        s = sline.strip()
        if not s:
            if collecting:
                break       # end of first paragraph
            continue
        # Skip document-level title only if it's the very first non-blank line
        if not collecting and looks_like_title(s):
            continue        # skip the heading
        if len(s) > 10:
            desc_lines.append(s)
            collecting = True

    description = " ".join(desc_lines).strip()
    if not description:
        # Last-resort: use full stripped text truncated
        description = strip_md(text)[:400]

    # ── Collected extracted_text: lines from section "2." / "Text visible" onwards ──
    extracted_lines = []
    in_text_section = False
    for line in stripped_lines:
        s = line.strip().lstrip("0123456789.-) ").strip()
        ll = line.lower()
        if any(kw in ll for kw in ["visible text", "text visible", "2.", "extracted text", "reads:"]):
            in_text_section = True
        if in_text_section and s and len(s) > 3:
            extracted_lines.append(s)
        # Stop when we hit section 3
        if in_text_section and any(kw in ll for kw in ["3.", "relevance", "complaint type", "4."]):
            break

    extracted_text = "\n".join(extracted_lines[:10]).strip()

    return {
        "description":    description[:500],
        "extracted_text": extracted_text,
        "complaint_type": complaint_type,
        "is_relevant":    is_relevant,
    }



def _error_result(error: str) -> dict:
    return {
        "success":        False,
        "description":    "",
        "extracted_text": "",
        "complaint_type": "",
        "is_relevant":    False,
        "full_analysis":  "",
        "model_used":     _VISION_MODEL,
        "error":          error,
    }
