"""LLM client wrapper using Groq (free tier)."""
from __future__ import annotations

import json
import os
import re
from typing import Any

from groq import AsyncGroq

_client = AsyncGroq(api_key=os.environ["EMERGENT_LLM_KEY"])
_MODEL = "llama-3.3-70b-versatile"


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


async def llm_json(system: str, user: str, max_tokens: int = 1500) -> dict[str, Any]:
    response = await _client.chat.completions.create(
        model=_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    text = _strip_code_fence(response.choices[0].message.content)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"_raw": text, "_error": "json_parse"}


async def llm_text(system: str, user: str, max_tokens: int = 800) -> str:
    response = await _client.chat.completions.create(
        model=_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content.strip()