"""Groq OpenAI-compatible chat completions for structured JSON (orchestration packs only)."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger("outbound-agent.orchestration.groq")

GROQ_BASE = os.getenv("GROQ_OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
GROQ_CHAT_URL = f"{GROQ_BASE}/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"


def resolve_groq_model() -> str:
    """Prefer GROQ_MODEL env (e.g. llama-3.1-8b-instant); fallback to default."""
    return (os.getenv("GROQ_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # Last resort: first {...} block
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


async def groq_json_completion(
    *,
    system: str,
    user: str,
    model: str | None = None,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """
    Returns parsed JSON object from Groq chat completion, or {} on failure.
    Uses GROQ_API_KEY only (no OpenAI).
    """
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not key:
        logger.warning("[ORCHESTRATOR] groq_json_completion skipped: GROQ_API_KEY unset")
        return {}

    resolved_model = (model or resolve_groq_model()).strip() or resolve_groq_model()

    payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    # Groq supports response_format json_object for compatible models
    payload["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(GROQ_CHAT_URL, headers=headers, json=payload)
            if resp.status_code == 400 and "response_format" in resp.text.lower():
                payload.pop("response_format", None)
                resp = await client.post(GROQ_CHAT_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("[ORCHESTRATOR] groq_json_http_error: %s", e)
        return {}

    try:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
    except Exception:
        logger.warning("[ORCHESTRATOR] groq_json_parse_failed: malformed response shape")
        return {}

    parsed = _extract_json_object(content)
    if not parsed:
        logger.warning("[ORCHESTRATOR] groq_json_parse_failed: content not JSON")
        return {}
    return parsed
