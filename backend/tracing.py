"""Safe LangSmith tracing helpers for the voice runtime."""

from __future__ import annotations

import functools
import logging
import os
import re
from collections.abc import Callable
from typing import Any, TypeVar, overload

logger = logging.getLogger("outbound-agent.langsmith")

_F = TypeVar("_F", bound=Callable[..., Any])
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "authorization",
    "password",
    "service_role",
    "supabase_service_role",
    "livekit_api_secret",
)
_LOGGED_STATUS = False


def langsmith_enabled() -> bool:
    return bool((os.getenv("LANGCHAIN_API_KEY") or "").strip())


def configure_langsmith_env() -> bool:
    enabled = langsmith_enabled()
    if enabled:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", "good-calling-agent")
        os.environ.setdefault("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    return enabled


def log_langsmith_status_once() -> bool:
    global _LOGGED_STATUS
    enabled = configure_langsmith_env()
    if not _LOGGED_STATUS:
        logger.info("[LANGSMITH] enabled=%s", str(enabled).lower())
        _LOGGED_STATUS = True
    return enabled


def mask_phone_number(value: Any) -> Any:
    text = str(value or "")
    digits = re.sub(r"\D", "", text)
    if len(digits) < 8:
        return text
    prefix_len = 5 if text.strip().startswith("+") else 4
    prefix = text.strip()[:prefix_len]
    return f"{prefix}****{digits[-4:]}"


def _mask_phone_matches(value: str) -> str:
    return _PHONE_RE.sub(lambda m: str(mask_phone_number(m.group(0))), value)


def sanitize_for_trace(value: Any, *, max_text: int = 500) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            key_l = key_s.lower()
            if any(part in key_l for part in _SECRET_KEY_PARTS):
                continue
            safe[key_s] = sanitize_for_trace(item, max_text=max_text)
        return safe
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_trace(item, max_text=max_text) for item in list(value)[:25]]
    if isinstance(value, str):
        masked = _mask_phone_matches(value)
        if len(masked) > max_text:
            return masked[:max_text] + "...[truncated]"
        return masked
    return value


def _fallback_traceable(*dargs: Any, **_dkwargs: Any) -> Callable[[_F], _F] | _F:
    if dargs and callable(dargs[0]) and len(dargs) == 1:
        return dargs[0]

    def decorator(fn: _F) -> _F:
        return fn

    return decorator


try:
    from langsmith import traceable as _langsmith_traceable
except Exception:
    _langsmith_traceable = None


@overload
def traceable(fn: _F) -> _F: ...


@overload
def traceable(*args: Any, **kwargs: Any) -> Callable[[_F], _F]: ...


def traceable(*args: Any, **kwargs: Any) -> Callable[[_F], _F] | _F:
    if not langsmith_enabled() or _langsmith_traceable is None:
        return _fallback_traceable(*args, **kwargs)
    try:
        return _langsmith_traceable(*args, **kwargs)
    except Exception:
        return _fallback_traceable(*args, **kwargs)


@traceable(name="voice_trace_event", run_type="chain")
def _emit_trace_event(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"event": name, **payload}


def trace_event(name: str, **payload: Any) -> None:
    safe_payload = sanitize_for_trace(payload)
    try:
        log_langsmith_status_once()
        if langsmith_enabled():
            _emit_trace_event(name, safe_payload if isinstance(safe_payload, dict) else {"payload": safe_payload})
    except Exception as exc:
        logger.debug("[LANGSMITH] trace_event skipped name=%s error=%s", name, type(exc).__name__)


def log_tts_filter_blocked(*, source: str, text: str = "", reason: str = "no_speakable_text") -> None:
    safe = sanitize_for_trace({"source": source, "reason": reason, "text": text})
    logger.info("[TRACE] tts_filter_blocked source=%s reason=%s", safe.get("source"), safe.get("reason"))
    trace_event("tts_filter_blocked", **safe)
