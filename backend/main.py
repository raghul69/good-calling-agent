import os
import sys
import io
import logging
import json
import re
import uuid
import asyncio
import secrets
import hashlib
import threading
import time
from contextlib import asynccontextmanager
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from fastapi import FastAPI, HTTPException, Depends, Request, Header, Query
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from urllib.parse import urlparse

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.config_manager import read_config, write_config
import backend.db as db

# Import routers once we create them
# from backend.routers import auth, config, calls, crm, logs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-api")


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    retry_task: asyncio.Task | None = None
    if os.environ.get("DISABLE_CALL_RETRY_SCHEDULER", "").lower() in {"1", "true", "yes"}:
        logger.info("Call retry scheduler disabled by env")
    else:
        retry_task = asyncio.create_task(_retry_scheduler_loop())

    await _log_deployment_integration()

    try:
        yield
    finally:
        if retry_task is not None:
            retry_task.cancel()
            try:
                await retry_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="RapidX AI Dashboard API", version="2.0.0", lifespan=_app_lifespan)

_RL_LOCK = threading.Lock()
_RL_STORE: defaultdict[str, list[float]] = defaultdict(list)


def _rate_limit_allow(key: str, limit_per_minute: int) -> bool:
    if limit_per_minute <= 0:
        return True
    window = 60.0
    now = time.monotonic()
    with _RL_LOCK:
        bucket = _RL_STORE[key]
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= limit_per_minute:
            return False
        bucket.append(now)
        return True


def _client_ip_prefix(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def _debug_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10] if value else ""


def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        entry = {
            "sessionId": "6b88e2",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        with open("debug-6b88e2.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
        logger.info("[DEBUG-6b88e2] %s %s", message, json.dumps(data, ensure_ascii=True))
    except Exception:
        pass


def _api_error(message: str, code: str = "api_error", request_id: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def _required_env_status(keys: list[str]) -> dict:
    return {key: bool((os.environ.get(key) or "").strip()) for key in keys}


def _voice_llm_configured() -> bool:
    """Outbound/agent LLM: Groq or OpenAI key (matches runtime prompt/voice paths)."""
    g = (os.environ.get("GROQ_API_KEY") or "").strip()
    o = (os.environ.get("OPENAI_API_KEY") or "").strip()
    return bool(g or o)


def _livekit_operator_missing(lk: dict[str, Any]) -> list[str]:
    """Human/ops-oriented LiveKit gaps for health.missing and startup warnings."""
    codes: list[str] = []
    if not lk.get("url_present"):
        codes.append("livekit:url_missing")
    elif not lk.get("url_valid"):
        codes.append("livekit:url_invalid")
    if not lk.get("key_present"):
        codes.append("livekit:api_key_missing")
    if not lk.get("secret_present"):
        codes.append("livekit:api_secret_missing")
    return codes


def _health_missing_list(
    mvp_env: dict[str, bool],
    supabase_status: dict[str, Any],
    livekit_status: dict[str, Any],
) -> list[str]:
    missing = {k for k, v in mvp_env.items() if not v}
    if not supabase_status.get("configured"):
        if not supabase_status.get("url_present"):
            missing.add("supabase:url_missing")
        elif not supabase_status.get("url_valid"):
            missing.add("supabase:url_invalid")
        if not supabase_status.get("key_present"):
            missing.add("supabase:key_missing")
    if not (livekit_status.get("configured") and livekit_status.get("url_valid")):
        missing.update(_livekit_operator_missing(livekit_status))
    return sorted(missing)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    detail = str(exc.detail) if exc.detail is not None else ""
    if exc.status_code == 401:
        logger.warning(
            "[AUTH] unauthorized path=%s request_id=%s detail=%s",
            request.url.path,
            request_id,
            detail[:200],
        )
    else:
        logger.warning(
            "[API] HTTP %s %s request_id=%s detail=%s",
            exc.status_code,
            request.url.path,
            request_id,
            detail[:200],
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=_api_error(str(exc.detail), "http_error", request_id),
        headers={"x-request-id": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    logger.warning("Validation error %s request_id=%s errors=%s", request.url.path, request_id, exc.errors())
    return JSONResponse(
        status_code=422,
        content=_api_error("Invalid request payload", "validation_error", request_id),
        headers={"x-request-id": request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    logger.exception("Unhandled API error %s request_id=%s", request.url.path, request_id)
    return JSONResponse(
        status_code=500,
        content=_api_error("Internal server error", "internal_error", request_id),
        headers={"x-request-id": request_id},
    )


def _cors_origins() -> list[str]:
    configured = os.environ.get("CORS_ORIGIN") or os.environ.get("CORS_ORIGINS") or ""
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    defaults = [
        "https://good-calling-agent.vercel.app",
        "https://good-calling-agent-jettones-projects.vercel.app",
        "https://good-calling-agent-git-main-jettones-projects.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    return list(dict.fromkeys([*origins, *defaults]))


def _cors_allow_origin_regex() -> str | None:
    """
    Optional regex for Vercel preview hosts. Set CORS_ORIGIN_REGEX=disabled to turn off.
    Set to a custom regex string to match your Vercel project pattern.
    """
    raw = os.environ.get("CORS_ORIGIN_REGEX", "").strip()
    if raw.lower() == "disabled":
        return None
    if raw:
        return raw
    return r"^https://good-calling-agent(?:-[a-z0-9-]+)?\.vercel\.app$"


_cors_mw_kwargs: dict[str, Any] = {
    "allow_origins": _cors_origins(),
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
_cors_rx = _cors_allow_origin_regex()
if _cors_rx:
    _cors_mw_kwargs["allow_origin_regex"] = _cors_rx

app.add_middleware(CORSMiddleware, **_cors_mw_kwargs)


@app.middleware("http")
async def api_rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        lim = int(os.getenv("RATE_LIMIT_PER_MINUTE", "300") or 300)
        auth_lim = int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "60") or 60)
        key = _client_ip_prefix(request)
        auth_key = f"rl:auth:{key}"
        generic_key = f"rl:{key}"
        if request.url.path.startswith("/api/auth/"):
            if not _rate_limit_allow(auth_key, auth_lim):
                return JSONResponse(
                    status_code=429,
                    content=_api_error("Rate limit exceeded — try again soon.", "rate_limited"),
                )
        elif not _rate_limit_allow(generic_key, lim):
            return JSONResponse(
                status_code=429,
                content=_api_error("Rate limit exceeded — try again soon.", "rate_limited"),
            )
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), payment=()")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

# We will include routers later after creating them
# app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
# app.include_router(config.router, prefix="/api/config", tags=["config"])
# app.include_router(calls.router, prefix="/api/call", tags=["calls"])
# app.include_router(crm.router, prefix="/api/crm", tags=["crm"])
# app.include_router(logs.router, prefix="/api/logs", tags=["logs"])

@app.get("/api/health")
def health_check():
    import datetime

    _apply_config_env()
    supabase_status = db.get_supabase_config_status()
    agent_publish_schema = db.check_agent_publish_uuid_schema()
    livekit_status = _livekit_config_status()
    mvp_keys = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "SARVAM_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "CORS_ORIGIN",
        "DEFAULT_TRANSFER_NUMBER",
    ]
    mvp_env = _required_env_status(mvp_keys)
    mvp_env["GROQ_OR_OPENAI_API_KEY"] = _voice_llm_configured()
    mvp_ready = all(mvp_env.values())
    sip_present = bool(_sip_trunk_id())
    lk_ok = bool(livekit_status.get("configured") and livekit_status.get("url_valid"))
    groq_present = bool(os.environ.get("GROQ_API_KEY", "").strip())
    openai_present = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    providers = {
        "livekit": lk_ok,
        "sarvam": bool(os.environ.get("SARVAM_API_KEY", "").strip()),
        "groq": groq_present,
        "openai": openai_present,
        "llm": groq_present or openai_present,
        "supabase": bool(supabase_status.get("configured")),
        "sip": sip_present,
    }
    missing = _health_missing_list(mvp_env, supabase_status, livekit_status)
    payload = {
        "ok": True,
        "mvp_env_ready": mvp_ready,
        "providers": providers,
        "voice_pipeline": os.environ.get("VOICE_PIPELINE", "livekit_agents"),
        "missing": missing,
        "status": "ok",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "service": "rapidx-ai-voice-agent-api",
        # Keep these top-level flags for easier deployment checks.
        "supabase_configured": supabase_status.get("configured", False),
        "service_role_key_present": supabase_status.get("service_role_key_present", False),
        "livekit_configured": livekit_status.get("configured", False),
        "sip_trunk_configured": sip_present,
        "groq_or_openai_configured": groq_present or openai_present,
        "integrations": {
            "supabase": supabase_status,
            "livekit": livekit_status,
        },
        "agent_publish_schema": agent_publish_schema,
        "mvp_env": {
            "required": mvp_env,
            "ready": mvp_ready,
        },
    }
    return payload


@app.get("/health")
def health_check_root():
    return health_check()


@app.get("/api/public/client-config")
def public_client_config():
    """Public browser bootstrap: Supabase URL + anon key (same as NEXT_PUBLIC_* on Vercel). Never returns service_role."""
    _apply_config_env()
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    anon = (os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    return {
        "supabase_url": url,
        "supabase_anon_key": anon,
        "configured": bool(url and anon),
    }


@app.get("/api/livekit/health")
async def api_livekit_health():
    """Public probe: LiveKit env completeness and optional list_rooms reachability (no secrets in response)."""
    _apply_config_env()
    config = read_config()
    livekit_url = (config.get("livekit_url") or os.environ.get("LIVEKIT_URL", "")).strip()
    api_key = (config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY", "")).strip()
    # region agent log
    _debug_log(
        "livekit-auth",
        "H1,H2",
        "backend/main.py:api_livekit_health",
        "LiveKit health using sanitized credential source",
        {
            "url_host": urlparse(livekit_url).netloc,
            "url_from_config": bool(config.get("livekit_url")),
            "key_from_config": bool(config.get("livekit_api_key")),
            "secret_from_config": bool(config.get("livekit_api_secret")),
            "key_fingerprint": _debug_fingerprint(api_key),
        },
    )
    # endregion
    status = _livekit_config_status()
    if not status.get("configured") or not status.get("url_valid"):
        return {
            "ok": False,
            "livekit": status,
            "room_count": None,
            "api_reachable": False,
        }
    try:
        from livekit import api as lkapi

        lk = lkapi.LiveKitAPI(
            url=livekit_url,
            api_key=config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY", ""),
            api_secret=config.get("livekit_api_secret") or os.environ.get("LIVEKIT_API_SECRET", ""),
        )
        rooms = await lk.room.list_rooms(lkapi.ListRoomsRequest())
        await lk.aclose()
        return {
            "ok": True,
            "livekit": status,
            "room_count": len(rooms.rooms),
            "api_reachable": True,
        }
    except Exception as e:
        # region agent log
        _debug_log(
            "livekit-auth",
            "H1,H2",
            "backend/main.py:api_livekit_health",
            "LiveKit health failed",
            {"error_type": type(e).__name__, "error": str(e)[:240]},
        )
        # endregion
        return {
            "ok": False,
            "livekit": status,
            "room_count": None,
            "api_reachable": False,
            "error": _friendly_livekit_error("LiveKit API health", e, livekit_url),
        }


@app.get("/api/debug/internal-test-config")
def api_debug_internal_test_config():
    enabled_raw = os.environ.get("ENABLE_INTERNAL_TEST_CALLS")
    enabled_normalized = (enabled_raw or "").strip().lower()
    route_registered = any(
        route.path == "/api/calls/outbound-test" and "POST" in (route.methods or set())
        for route in app.routes
    )
    return {
        "enabled_present": enabled_raw is not None,
        "enabled_value_is_true": enabled_normalized == "true",
        "secret_present": bool((os.environ.get("INTERNAL_TEST_CALL_SECRET") or "").strip()),
        "route_registered": route_registered,
    }


@app.get("/api/sip/health")
def api_sip_health():
    """Public probe: trunk id present and LiveKit URL/keys configured (trunk id is a resource id, not a secret)."""
    _apply_config_env()
    lk = _livekit_config_status()
    trunk = _sip_trunk_id()
    trunk_configured = bool(trunk)
    livekit_ok = bool(lk.get("configured") and lk.get("url_valid"))
    return {
        "ok": trunk_configured and livekit_ok,
        "trunk_configured": trunk_configured,
        "livekit_configured": livekit_ok,
        "sip_trunk_id": trunk or None,
        "livekit": lk,
    }


# Provide some placeholder routes from old ui_server logic during transition
# Allow running this file directly (`python backend/main.py`) and as module.

class AuthPayload(BaseModel):
    email: str
    password: str


class PasswordResetPayload(BaseModel):
    email: str


class EmailOtpPayload(BaseModel):
    email: str


class EmailOtpVerifyPayload(BaseModel):
    email: str
    token: str
    type: str = "email"


class CallPayload(BaseModel):
    phone_number: str
    agent_id: str | None = None
    published_agent_uuid: str | None = None
    first_line: str | None = None


class LiveKitTokenPayload(BaseModel):
    room_name: str | None = None
    participant_identity: str | None = None
    participant_name: str | None = None
    agent_id: str | None = None


class BrowserTestPayload(BaseModel):
    agent_id: str | None = None
    published_agent_uuid: str | None = None


class OutboundCallPayload(BaseModel):
    phone_number: str
    agent_id: str | None = None
    published_agent_uuid: str | None = None
    first_line: str | None = None


class SipTestCallPayload(BaseModel):
    phone_number: str
    agent_id: str | None = "test-agent"
    published_agent_uuid: str | None = None


class CheckoutPayload(BaseModel):
    price_id: str | None = None


class AgentVersionPatch(BaseModel):
    welcome_message: str | None = None
    system_prompt: str | None = None
    multilingual_prompts: dict[str, str] | None = None
    prompt_variables: list[dict[str, Any]] | None = None
    llm_config: dict[str, Any] | None = None
    audio_config: dict[str, Any] | None = None
    engine_config: dict[str, Any] | None = None
    call_config: dict[str, Any] | None = None
    tools_config: list[dict[str, Any]] | None = None
    analytics_config: dict[str, Any] | None = None
    status: str | None = None


class AgentCreate(AgentVersionPatch):
    name: str = Field(default="Voice Agent", min_length=1, max_length=120)
    description: str | None = ""
    status: str | None = "draft"
    visibility: str | None = "private"
    default_language: str | None = "multilingual"
    config: dict[str, Any] | None = None
    template: str | None = None
    agent_state: str | None = None


class AgentPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    status: str | None = None
    visibility: str | None = None
    default_language: str | None = None
    config: dict[str, Any] | None = None
    agent_state: str | None = None


class WorkspaceSwitchPayload(BaseModel):
    workspace_id: str


class ProfilePayload(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None


class CampaignPayload(BaseModel):
    name: str = Field(default="Campaign", max_length=200)
    agent_id: str | None = None


class ContactsImportPayload(BaseModel):
    lines: list[str] = Field(default_factory=list)


class DispositionPayload(BaseModel):
    disposition: str


class AgentExport(BaseModel):
    schema_version: int = 1
    exported_at: str | None = None
    agent: dict[str, Any]
    versions: list[dict[str, Any]] = Field(default_factory=list)


_PROMPT_ASSIST_ACTIONS = frozenset({
    "improve",
    "shorten",
    "rewrite_professional",
    "optimize_sales",
    "optimize_support",
    "optimize_real_estate",
})


class PromptAssistPayload(BaseModel):
    current_prompt: str = Field(default="", max_length=120_000)
    action: str = Field(default="improve")
    language_profile: str | None = Field(default=None, max_length=80)
    language_profile_label: str | None = Field(default=None, max_length=200)
    tone: str | None = Field(default=None, max_length=500)
    business_type: str | None = Field(default=None, max_length=500)


class ProviderRoute(BaseModel):
    id: str | None = None
    workspace_id: str | None = None
    name: str
    route_type: str
    primary_provider: str
    fallback_providers: list[str] = Field(default_factory=list)
    cost_limit_usd: float | None = None
    latency_limit_ms: int | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ProviderUsageEvent(BaseModel):
    workspace_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    agent_version_id: str | None = None
    provider_type: str
    provider_name: str
    model: str | None = ""
    metric: str
    quantity: float = 0
    estimated_cost_usd: float = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


PHONE_RE = re.compile(r"^\+[1-9]\d{7,15}$")


def _validate_phone_number(phone_number: str) -> str:
    phone = re.sub(r"[\s().-]+", "", (phone_number or "").strip())
    if not PHONE_RE.match(phone):
        raise HTTPException(
            status_code=400,
            detail="Phone number must be E.164 format, for example +919876543210",
        )
    return phone


def _usable_llm_key(key: str | None) -> bool:
    if not key or not str(key).strip():
        return False
    k = str(key).strip()
    low = k.lower()
    if low.startswith("your_") or low in ("sk-xxx", "changeme", "replace_me"):
        return False
    if len(k) < 12:
        return False
    return True


def _strip_prompt_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


def _prompt_assist_action_instruction(action: str) -> str:
    return {
        "improve": (
            "Improve clarity, structure, and completeness. Keep multilingual content in the same languages as the draft. "
            "Do not invent brand facts the user did not imply."
        ),
        "shorten": (
            "Make the prompt significantly shorter while preserving intent, guardrails, and critical behaviors. "
            "Preserve the same primary language(s) as the draft."
        ),
        "rewrite_professional": (
            "Rewrite in a polished, professional telephone voice suitable for B2B or premium consumer brands. "
            "Keep the same languages as the draft; be concise."
        ),
        "optimize_sales": (
            "Optimize for inbound sales: qualify need, handle objections briefly, move to a clear next step (book/meeting). "
            "Respect the draft languages and domain."
        ),
        "optimize_support": (
            "Optimize for support: empathy, triage, step-by-step help, and clear escalation/transfer language."
        ),
        "optimize_real_estate": (
            "Optimize for real estate inbound: qualify budget/location, property type, site visits, and compliance-friendly, helpful tone."
        ),
    }.get(action, "Improve the draft while preserving the user's languages and intent.")


def _prompt_assist_system_message(action: str) -> str:
    task = _prompt_assist_action_instruction(action)
    return (
        "You are an expert editor of voice-agent system prompts for real-time phone calls.\n"
        "Output ONLY the final system prompt text — no title, preamble, or markdown unless the prompt itself needs bullets.\n"
        "Be concise and production-ready.\n"
        f"Task: {task}"
    )


def _prompt_assist_user_message(payload: PromptAssistPayload) -> str:
    blocks: list[str] = []
    lp = (payload.language_profile or "").strip()
    if lp:
        label = (payload.language_profile_label or "").strip()
        blocks.append(
            f"Language profile id: {lp}" + (f" ({label})" if label else ""),
        )
    if payload.tone and str(payload.tone).strip():
        blocks.append(f"Desired agent tone: {str(payload.tone).strip()}")
    if payload.business_type and str(payload.business_type).strip():
        blocks.append(f"Business type / vertical: {str(payload.business_type).strip()}")
    blocks.append("---\nDraft system prompt:\n")
    blocks.append((payload.current_prompt or "").strip() or "(empty — write a complete prompt suitable for a voice AI on phone calls.)")
    blocks.append("\n---\nReturn the single revised system prompt only.")
    return "\n".join(blocks)


async def _run_prompt_assist_llm(payload: PromptAssistPayload) -> tuple[str, str, str]:
    groq_k = (os.environ.get("GROQ_API_KEY") or "").strip()
    openai_k = (os.environ.get("OPENAI_API_KEY") or "").strip()

    if _usable_llm_key(groq_k):
        provider, base, key = "groq", "https://api.groq.com/openai/v1", groq_k
        model = (os.environ.get("GROQ_PROMPT_ASSIST_MODEL") or "llama-3.3-70b-versatile").strip()
    elif _usable_llm_key(openai_k):
        provider, base, key = "openai", None, openai_k
        model = (os.environ.get("OPENAI_PROMPT_ASSIST_MODEL") or "gpt-4o-mini").strip()
    else:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured. Set GROQ_API_KEY or OPENAI_API_KEY on the server.",
        )

    client = AsyncOpenAI(api_key=key, base_url=base) if base else AsyncOpenAI(api_key=key)
    sys_msg = _prompt_assist_system_message(payload.action)
    user_msg = _prompt_assist_user_message(payload)
    logger.info(
        "[AI_EDIT] prompt generation started action=%s provider=%s model=%s",
        payload.action,
        provider,
        model,
    )
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.35,
            max_tokens=2048,
        )
    except Exception as e:
        logger.warning("[AI_EDIT] prompt generation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM request failed: {e!s}") from e

    raw = (resp.choices[0].message.content or "").strip()
    text = _strip_prompt_fence(raw)
    if not text:
        raise HTTPException(status_code=502, detail="LLM returned empty text.")
    logger.info(
        "[AI_EDIT] prompt generation completed provider=%s model=%s chars=%s",
        provider,
        model,
        len(text),
    )
    return text, provider, model


def _apply_config_env() -> None:
    config = read_config()
    if config.get("supabase_url"):
        os.environ["SUPABASE_URL"] = config.get("supabase_url", "")
    if config.get("supabase_key"):
        os.environ["SUPABASE_KEY"] = config.get("supabase_key", "")
        os.environ.setdefault("SUPABASE_ANON_KEY", config.get("supabase_key", ""))
    if config.get("supabase_service_role_key"):
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = config.get("supabase_service_role_key", "")
    lk_sip_trunk = (os.environ.get("LIVEKIT_SIP_TRUNK_ID") or "").strip()
    if lk_sip_trunk:
        os.environ.setdefault("OUTBOUND_TRUNK_ID", lk_sip_trunk)
        os.environ.setdefault("SIP_TRUNK_ID", lk_sip_trunk)
    if config.get("sip_trunk_id"):
        os.environ.setdefault("OUTBOUND_TRUNK_ID", config.get("sip_trunk_id", ""))
        os.environ.setdefault("SIP_TRUNK_ID", config.get("sip_trunk_id", ""))


def _sip_trunk_id() -> str:
    """Resolved outbound SIP trunk id (non-secret resource id)."""
    _apply_config_env()
    config = read_config()
    for candidate in (
        (os.environ.get("OUTBOUND_TRUNK_ID") or "").strip(),
        (os.environ.get("LIVEKIT_SIP_TRUNK_ID") or "").strip(),
        (os.environ.get("SIP_TRUNK_ID") or "").strip(),
        (config.get("sip_trunk_id") or "").strip(),
    ):
        if candidate:
            return candidate
    return ""


def _mask_phone_e164(phone: str) -> str:
    clean = re.sub(r"[\s().-]+", "", (phone or "").strip())
    if len(clean) < 5:
        return "****"
    return f"…{clean[-4:]}"


def _sip_failure_reason(exc: Exception) -> str:
    failure_text = str(exc).lower()
    if "busy" in failure_text:
        return "busy"
    if "timeout" in failure_text or "timed out" in failure_text:
        return "timeout"
    if "no answer" in failure_text or "no_answer" in failure_text:
        return "no_answer"
    return "sip_failure"


def _livekit_config_status() -> dict:
    config = read_config()
    livekit_url = (config.get("livekit_url") or os.environ.get("LIVEKIT_URL", "")).strip()
    parsed = urlparse(livekit_url)
    return {
        "configured": bool(
            livekit_url
            and (config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY"))
            and (config.get("livekit_api_secret") or os.environ.get("LIVEKIT_API_SECRET"))
        ),
        "url_present": bool(livekit_url),
        "key_present": bool(config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY")),
        "secret_present": bool(config.get("livekit_api_secret") or os.environ.get("LIVEKIT_API_SECRET")),
        "url_valid": bool(parsed.scheme in {"wss", "ws", "https", "http"} and parsed.netloc),
    }


def _friendly_livekit_error(action: str, error: Exception, livekit_url: str) -> str:
    host = urlparse(livekit_url).netloc or "unknown"
    message = str(error)
    if "[Errno 11001]" in message or "getaddrinfo failed" in message:
        return (
            f"{action} failed: DNS lookup failed for LiveKit host '{host}'. "
            "Check LIVEKIT_URL, internet/DNS access, and Railway environment variables."
        )
    return message


def _livekit_credentials() -> tuple[str, str, str]:
    _apply_config_env()
    config = read_config()
    livekit_url = (config.get("livekit_url") or os.environ.get("LIVEKIT_URL", "")).strip()
    api_key = (config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY", "")).strip()
    api_secret = (config.get("livekit_api_secret") or os.environ.get("LIVEKIT_API_SECRET", "")).strip()
    if not (livekit_url and api_key and api_secret):
        raise HTTPException(status_code=500, detail="LiveKit is not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET.")
    return livekit_url, api_key, api_secret


def _agent_name() -> str:
    return os.environ.get("LIVEKIT_AGENT_NAME", "outbound-caller")


def _env_present(*names: str) -> bool:
    return any(bool((os.environ.get(name) or "").strip()) for name in names)


def _public_app_url() -> str:
    configured = (
        os.environ.get("PUBLIC_APP_URL")
        or os.environ.get("FRONTEND_URL")
        or os.environ.get("NEXT_PUBLIC_APP_URL")
        or os.environ.get("CORS_ORIGIN")
        or ""
    ).strip()
    if "," in configured:
        configured = configured.split(",", 1)[0].strip()
    return configured.rstrip("/") or "http://localhost:3000"


def _stripe_client():
    secret_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not secret_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured. Set STRIPE_SECRET_KEY.")
    try:
        import stripe
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe SDK import failed: {e}")
    stripe.api_key = secret_key
    return stripe


def _stripe_price_id(price_id: str | None = None) -> str:
    resolved = (price_id or os.environ.get("STRIPE_PRICE_ID") or os.environ.get("BILLING_STRIPE_PRICE_ID") or "").strip()
    if not resolved:
        raise HTTPException(status_code=500, detail="Stripe price is not configured. Set STRIPE_PRICE_ID.")
    return resolved


def _billing_settings(user: dict) -> dict:
    return db.get_workspace_settings(user.get("_workspace_id")).get("billing") or {}


def _update_billing_settings(workspace_id: str | None, **fields: object) -> None:
    if not workspace_id:
        return
    current = db.get_workspace_settings(workspace_id)
    billing = dict(current.get("billing") or {})
    billing.update({k: v for k, v in fields.items() if v is not None})
    db.update_workspace_settings(workspace_id, {"billing": billing})


def _subscription_status_from_stripe(subscription: object) -> dict:
    def value(name: str):
        if isinstance(subscription, dict):
            return subscription.get(name)
        return getattr(subscription, name, None)

    return {
        "stripe_subscription_id": value("id"),
        "stripe_customer_id": value("customer"),
        "status": value("status"),
        "current_period_end": value("current_period_end"),
        "cancel_at_period_end": value("cancel_at_period_end"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _ops_item(key: str, label: str, ready: bool, detail: str, action: str = "") -> dict:
    return {
        "key": key,
        "label": label,
        "ready": bool(ready),
        "detail": detail,
        "action": action,
    }


def _ops_readiness_payload() -> dict:
    _apply_config_env()
    supabase_status = db.get_supabase_config_status()
    livekit_status = _livekit_config_status()
    sip_trunk = _sip_trunk_id()
    frontend_origin = (os.environ.get("CORS_ORIGIN") or os.environ.get("CORS_ORIGINS") or "").strip()
    stripe_ready = (
        _env_present("STRIPE_SECRET_KEY")
        and _env_present("STRIPE_WEBHOOK_SECRET")
        and _env_present("STRIPE_PRICE_ID", "BILLING_STRIPE_PRICE_ID")
    )
    sentry_ready = _env_present("SENTRY_DSN")
    internal_test_ready = _internal_outbound_test_enabled() and _env_present("INTERNAL_TEST_CALL_SECRET")
    items = [
        _ops_item(
            "production_deploy",
            "Railway/Vercel production deploy",
            bool(livekit_status.get("configured") and supabase_status.get("configured") and frontend_origin),
            "Backend env, LiveKit, Supabase, and frontend CORS are detectable.",
            "Set Railway backend env and Vercel NEXT_PUBLIC_API_URL/CORS_ORIGIN.",
        ),
        _ops_item(
            "billing",
            "Billing/subscriptions",
            stripe_ready,
            "Stripe checkout, price, and webhook variables are present." if stripe_ready else "Billing currently uses usage estimates only.",
            "Add STRIPE_SECRET_KEY, STRIPE_PRICE_ID, and STRIPE_WEBHOOK_SECRET.",
        ),
        _ops_item(
            "tenant_isolation",
            "Workspace tenant isolation",
            bool(supabase_status.get("service_role_key_present")),
            "Workspace creation and RLS-backed user reads are available when SaaS migrations are applied.",
            "Run Supabase workspace/RLS migrations in production.",
        ),
        _ops_item(
            "admin_panel",
            "Admin panel",
            True,
            "Admin/workspace screen and admin-only config endpoints exist.",
            "Expand role management, invites, audit logs, and support impersonation later.",
        ),
        _ops_item(
            "onboarding",
            "User onboarding",
            bool(livekit_status.get("configured") and supabase_status.get("configured")),
            "Dashboard launch checklist can reflect core integration readiness.",
            "Add guided setup for phone numbers, SIP trunks, and first agent publishing.",
        ),
        _ops_item(
            "analytics",
            "Call analytics",
            True,
            "Call stats, booking rate, estimated cost, contacts, and call logs are exposed.",
            "Add time-series charts, cohort filters, and campaign attribution.",
        ),
        _ops_item(
            "monitoring",
            "Monitoring/logs/error tracking",
            sentry_ready,
            "Sentry is configured." if sentry_ready else "Structured API errors exist; Sentry DSN is not configured.",
            "Set SENTRY_DSN and connect Railway log drains/alerts.",
        ),
        _ops_item(
            "security",
            "Security hardening",
            bool(supabase_status.get("configured")),
            "Auth, admin checks, CORS controls, and security headers are enabled.",
            "Complete rate limits, audit logs, secret rotation, and abuse monitoring.",
        ),
        _ops_item(
            "inbound_proof",
            "Inbound call production proof",
            bool(sip_trunk and livekit_status.get("configured")),
            "LiveKit and SIP trunk config are detectable.",
            "Run answered-call proof and store the room/call log evidence.",
        ),
        _ops_item(
            "qa",
            "Real QA with many calls",
            internal_test_ready,
            "Internal test-call route is enabled and protected." if internal_test_ready else "Internal test-call route is disabled or missing its secret.",
            "Enable test route temporarily, run call matrix, then disable it.",
        ),
        _ops_item(
            "docs_support",
            "Docs/support flow",
            True,
            "Production and deployment docs exist in the repo.",
            "Publish customer-facing docs, support intake, and incident runbooks.",
        ),
    ]
    ready_count = sum(1 for item in items if item["ready"])
    return {
        "status": "ready" if ready_count == len(items) else "needs_attention",
        "ready_count": ready_count,
        "total_count": len(items),
        "score": round((ready_count / len(items)) * 100),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }


def _new_room_name(prefix: str, value: str = "") -> str:
    suffix = re.sub(r"[^a-zA-Z0-9]+", "", value or "")[:18].lower()
    return "-".join(part for part in [prefix, suffix, str(uuid.uuid4())[:8]] if part)


def _participant_token(
    livekit_url: str,
    api_key: str,
    api_secret: str,
    room_name: str,
    identity: str,
    name: str,
    metadata: dict | None = None,
) -> dict:
    from livekit.api import AccessToken, VideoGrants

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_metadata(json.dumps(metadata or {}))
        .with_grants(VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
        .with_ttl(timedelta(seconds=3600))
        .to_jwt()
    )
    return {"roomName": room_name, "room": room_name, "token": token, "url": livekit_url}


async def _create_livekit_room(lk: any, lkapi: any, livekit_url: str, room_name: str) -> None:
    try:
        await lk.room.create_room(lkapi.CreateRoomRequest(name=room_name))
    except Exception as e:
        message = str(e).lower()
        if "already" not in message and "exists" not in message:
            raise HTTPException(status_code=502, detail=_friendly_livekit_error("LiveKit room create", e, livekit_url))


async def _dispatch_agent_to_room(lk: any, lkapi: any, livekit_url: str, room_name: str, metadata: dict) -> any:
    try:
        return await lk.agent_dispatch.create_dispatch(
            lkapi.CreateAgentDispatchRequest(
                agent_name=_agent_name(),
                room=room_name,
                metadata=json.dumps({k: v for k, v in metadata.items() if v is not None}),
            )
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=_friendly_livekit_error("LiveKit agent dispatch", e, livekit_url))


def _require_auth(
    authorization: str = Header(default=""),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> dict:
    _apply_config_env()
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    result = db.auth_get_user(token)
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("message", "Invalid token"))
    result["_access_token"] = token
    user_id = result.get("user_id") or ""
    header_raw = (x_workspace_id or "").strip()
    preferred = header_raw if header_raw else None
    wid, wrole = db.resolve_active_workspace_id(user_id, preferred)
    if header_raw:
        if not _is_uuid(header_raw):
            raise HTTPException(status_code=400, detail="X-Workspace-Id must be a valid UUID")
        if wid != header_raw:
            raise HTTPException(
                status_code=403,
                detail="You are not a member of the workspace requested by X-Workspace-Id.",
            )
    result["_workspace_id"] = wid
    result["_workspace_role"] = wrole or "viewer"
    return result


def _require_workspace_role(*roles: str) -> Callable[[dict], dict]:
    allowed = frozenset(roles)

    def _checker(user: dict = Depends(_require_auth)) -> dict:
        r = db.normalize_workspace_role(user.get("_workspace_role"))
        if r not in allowed:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action in the current workspace.",
            )
        return user

    return _checker


require_agent_editor = _require_workspace_role("owner", "admin", "agent_manager")
require_workspace_admin = _require_workspace_role("owner", "admin")


def _platform_ops_user_ids() -> set[str]:
    return {x.strip() for x in (os.getenv("OPS_ADMIN_IDS") or "").split(",") if x.strip()}


def _require_platform_admin(user: dict = Depends(_require_auth)) -> dict:
    meta = user.get("app_metadata") or {}
    if str(meta.get("platform_role") or "").lower() == "ops":
        return user
    uid = str(user.get("user_id") or "")
    if uid and uid in _platform_ops_user_ids():
        return user
    raise HTTPException(status_code=403, detail="Platform operations access required")


def _require_admin(user: dict = Depends(_require_auth)) -> dict:
    role = (user.get("role") or "").lower()
    roles = [str(r).lower() for r in (user.get("roles") or [])]
    if role == "admin" or "admin" in roles:
        return user
    raise HTTPException(status_code=403, detail="Admin access required")


def _require_workspace_id(user: dict) -> str:
    workspace_id = user.get("_workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Workspace is required. Sign in again so a workspace can be created.")
    return workspace_id


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def _provider_options_payload() -> dict:
    return {
        "language_profiles": [
            {
                "id": "english",
                "label": "English",
                "tts_language": "en-IN",
                "tts_voice": "dev",
                "instruction": "Speak in clear Indian English with a warm, professional tone.",
            },
            {
                "id": "hindi",
                "label": "Hindi",
                "tts_language": "hi-IN",
                "tts_voice": "ritu",
                "instruction": "Speak in polite Hindi. Keep sentences short and easy to understand.",
            },
            {
                "id": "tamil",
                "label": "Tamil",
                "tts_language": "ta-IN",
                "tts_voice": "priya",
                "instruction": "Speak in polite spoken Tamil for a professional context.",
            },
            {
                "id": "tamil_tanglish",
                "label": "Tamil / Tanglish",
                "tts_language": "ta-IN",
                "tts_voice": "priya",
                "instruction": "Speak in natural Tanglish with Tamil sentence flow and common English business words.",
            },
            {
                "id": "multilingual",
                "label": "Multilingual Auto",
                "tts_language": "hi-IN",
                "tts_voice": "kavya",
                "instruction": "Detect the caller's language and reply in the same language.",
            },
        ],
        "llm_providers": [
            {"id": "openai", "label": "OpenAI", "models": ["gpt-4o-mini", "gpt-4o"]},
            {"id": "groq", "label": "Groq", "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]},
            {"id": "claude", "label": "Claude", "models": ["claude-haiku-3-5-latest", "claude-sonnet-4-5"]},
            {"id": "gemini", "label": "Gemini", "models": ["gemini-2.0-flash", "gemini-1.5-flash"]},
        ],
        "tts_providers": [
            {"id": "sarvam", "label": "Sarvam AI", "voices": ["kavya", "ritu", "priya", "dev", "rohan"]},
            {"id": "elevenlabs", "label": "ElevenLabs", "voices": ["21m00Tcm4TlvDq8ikWAM"]},
        ],
        "stt_providers": [
            {"id": "sarvam", "label": "Sarvam Saaras v3", "languages": ["unknown", "hi-IN", "en-IN", "ta-IN"]},
            {"id": "deepgram", "label": "Deepgram Nova", "languages": ["multi"]},
        ],
        "tts_models": {
            "sarvam": ["bulbul:v3"],
            "elevenlabs": ["eleven_turbo_v2_5"],
        },
        "stt_models": {
            "sarvam": ["saaras:v3"],
            "deepgram": ["nova-2-general", "nova-3-general"],
        },
        "deepgram_configured": bool(os.getenv("DEEPGRAM_API_KEY", "").strip()),
        "engine_defaults": {
            "stt_min_endpointing_delay": 0.25,
            "max_turns": 8,
            "silence_timeout_seconds": 6,
            "response_latency_mode": "fast",
        },
    }


def _resolve_agent_runtime_for_call(agent_id: str | None, workspace_id: str | None, strict: bool = True) -> dict | None:
    if not agent_id:
        return None
    if not _is_uuid(agent_id):
        logger.info("Skipping DB agent resolution for legacy agent_id=%s", agent_id)
        return None
    resolved = db.resolve_agent_runtime_config(agent_id, workspace_id)
    if not resolved.get("success"):
        if strict:
            message = resolved.get("message", "Agent not found")
            mlow = message.lower()
            status_code = 404
            if "published version" in mlow or "no published" in mlow:
                status_code = 400
            elif "paused" in mlow or "inactive" in mlow:
                status_code = 409
            raise HTTPException(status_code=status_code, detail=message)
        logger.warning("Agent config resolution failed for %s: %s", agent_id, resolved.get("message"))
        return None
    return resolved


def _published_uuid_for_call(payload: object) -> str:
    value = str(getattr(payload, "published_agent_uuid", None) or "").strip()
    if value:
        return value
    fallback = str(getattr(payload, "agent_id", None) or "").strip()
    if fallback:
        logger.info("[TEST_CALL_BLOCKED_NO_PUBLISHED_UUID] draft_or_agent_id=%s", fallback)
    else:
        logger.info("[TEST_CALL_BLOCKED_NO_PUBLISHED_UUID] missing payload uuid")
    raise HTTPException(status_code=400, detail="Please Save and Publish the agent before testing.")


def _resolve_published_agent_runtime_for_call(payload: object, workspace_id: str | None) -> dict:
    published_uuid = _published_uuid_for_call(payload)
    try:
        resolved = _resolve_agent_runtime_for_call(published_uuid, workspace_id, strict=True)
    except HTTPException as exc:
        if exc.status_code in {400, 404}:
            logger.info("[TEST_CALL_BLOCKED_NO_PUBLISHED_UUID] published_agent_uuid=%s detail=%s", published_uuid, exc.detail)
            raise HTTPException(status_code=400, detail="Published agent UUID was not found. Please Save and Publish the agent before testing.") from exc
        raise
    if not resolved:
        logger.info("[TEST_CALL_BLOCKED_NO_PUBLISHED_UUID] published_agent_uuid=%s", published_uuid)
        raise HTTPException(status_code=400, detail="Published agent UUID was not found. Please Save and Publish the agent before testing.")
    logger.info("[TEST_CALL_VALID_UUID] published_agent_uuid=%s version_id=%s", published_uuid, resolved.get("agent_version_id"))
    return resolved


def _metadata_with_agent_runtime(metadata: dict, resolved_agent: dict | None) -> dict:
    if not resolved_agent:
        return metadata
    return {
        **metadata,
        "agent_id": resolved_agent.get("agent_id") or metadata.get("agent_id"),
        "agent_version_id": resolved_agent.get("agent_version_id"),
        "published_agent_uuid": resolved_agent.get("agent_id"),
        "agent_name": resolved_agent.get("agent_name"),
        "agent_config": resolved_agent.get("config") or {},
    }


@app.post("/api/auth/signup")
async def api_auth_signup(payload: AuthPayload):
    _apply_config_env()
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    result = db.auth_sign_up(payload.email, payload.password)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Signup failed"))
    return result


@app.post("/api/auth/login")
async def api_auth_login(payload: AuthPayload):
    _apply_config_env()
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email")
    result = db.auth_sign_in(payload.email, payload.password)
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("message", "Login failed"))
    return result


@app.post("/api/auth/forgot-password")
async def api_auth_forgot_password(payload: PasswordResetPayload):
    _apply_config_env()
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email")
    result = db.auth_reset_password(payload.email)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Password reset failed"))
    return {"success": True, "message": "Password reset email sent if account exists"}


@app.post("/api/auth/otp/send")
async def api_auth_otp_send(payload: EmailOtpPayload):
    _apply_config_env()
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email")
    result = db.auth_send_email_otp(payload.email)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "OTP send failed"))
    return result


@app.post("/api/auth/otp/verify")
async def api_auth_otp_verify(payload: EmailOtpVerifyPayload):
    _apply_config_env()
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email")
    if not payload.token.strip():
        raise HTTPException(status_code=400, detail="OTP token is required")
    result = db.auth_verify_email_otp(payload.email, payload.token.strip(), payload.type)
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("message", "OTP verification failed"))
    if not result.get("access_token"):
        raise HTTPException(status_code=401, detail="OTP verified, but Supabase did not return a session")
    return result


@app.get("/api/auth/me")
async def api_auth_me(authorization: str = Header(default="")):
    _apply_config_env()
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    result = db.auth_get_user(token)
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("message", "Invalid token"))
    uid = result.get("user_id") or ""
    result["workspaces"] = db.list_user_workspace_memberships(uid)
    result["profile"] = db.fetch_profile_row(uid)
    wid, wr = db.resolve_active_workspace_id(uid, None)
    result["workspace_id"] = wid
    result["workspace_role"] = wr or "viewer"
    return result


@app.get("/api/workspace")
async def api_workspace(user: dict = Depends(_require_auth)):
    return db.fetch_workspace_summary(user)


@app.get("/api/me")
async def api_me(user: dict = Depends(_require_auth)):
    return {
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "role": user.get("role"),
        "workspace_id": user.get("_workspace_id"),
        "workspace_role": user.get("_workspace_role"),
        "workspaces": db.list_user_workspace_memberships(user.get("user_id") or ""),
        "profile": db.fetch_profile_row(user.get("user_id")),
    }


@app.post("/api/workspace/switch")
async def api_workspace_switch(_payload: WorkspaceSwitchPayload):
    """Client should store workspace_id locally and send `X-Workspace-Id` on subsequent calls."""
    return {"success": True, "workspace_id": _payload.workspace_id.strip(), "hint": "Send this id as the X-Workspace-Id header."}


@app.patch("/api/me/profile")
async def api_me_profile(payload: ProfilePayload, user: dict = Depends(_require_auth)):
    res = db.upsert_profile_row(
        user.get("user_id"),
        display_name=payload.display_name,
        avatar_url=payload.avatar_url,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Profile update failed"))
    return {"success": True, "profile": res.get("profile")}


@app.get("/api/plans")
async def api_plans(_user: dict = Depends(_require_auth)):
    sb = db.get_supabase(service_role=True)
    if not sb:
        return []
    try:
        res = sb.table("plans").select("*").execute()
        return res.data or []
    except Exception:
        return []


@app.post("/api/livekit/token")
async def api_livekit_token(payload: LiveKitTokenPayload, user: dict = Depends(_require_auth)):
    livekit_url, api_key, api_secret = _livekit_credentials()
    resolved_agent = _resolve_agent_runtime_for_call(payload.agent_id, user.get("_workspace_id"))
    room_name = payload.room_name or _new_room_name("browser", payload.agent_id or user.get("user_id") or "user")
    identity = payload.participant_identity or f"browser-{user.get('user_id') or uuid.uuid4()}"
    metadata = {
        "agent_id": payload.agent_id,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "workspace_id": user.get("_workspace_id"),
        "is_browser_test": True,
    }
    metadata = _metadata_with_agent_runtime(metadata, resolved_agent)
    return _participant_token(
        livekit_url,
        api_key,
        api_secret,
        room_name,
        identity,
        payload.participant_name or "Browser Tester",
        metadata,
    )


@app.post("/api/calls/browser-test")
async def api_calls_browser_test(payload: BrowserTestPayload, user: dict = Depends(_require_auth)):
    livekit_url, api_key, api_secret = _livekit_credentials()
    from livekit import api as lkapi

    resolved_agent = _resolve_published_agent_runtime_for_call(payload, user.get("_workspace_id"))
    published_uuid = str(payload.published_agent_uuid or "").strip()
    room_name = _new_room_name("browser", published_uuid or user.get("user_id") or "agent")
    started_at = datetime.now(timezone.utc).isoformat()
    call_log = db.save_call_log(
        phone="browser",
        duration=0,
        transcript="",
        summary="Browser LiveKit test started",
        recording_url="",
        caller_name=user.get("email") or "Browser Tester",
        sentiment="pending",
        owner_user_id=user.get("user_id"),
        workspace_id=user.get("_workspace_id"),
        status="dispatching",
        room_name=room_name,
        agent_id=published_uuid,
        agent_version_id=(resolved_agent or {}).get("agent_version_id"),
        published_agent_uuid=(resolved_agent or {}).get("agent_id"),
        started_at=started_at,
    )
    db_call_id = call_log.get("id")
    metadata = {
        "phone_number": "demo",
        "is_demo": True,
        "is_browser_test": True,
        "agent_id": published_uuid,
        "db_call_id": db_call_id,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "workspace_id": user.get("_workspace_id"),
    }
    metadata = _metadata_with_agent_runtime(metadata, resolved_agent)

    lk = lkapi.LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
    try:
        await _create_livekit_room(lk, lkapi, livekit_url, room_name)
        dispatch = await _dispatch_agent_to_room(lk, lkapi, livekit_url, room_name, metadata)
    finally:
        await lk.aclose()

    if db_call_id:
        db.update_call_log(db_call_id, status="dispatched", summary="Browser LiveKit test dispatched")

    token_payload = _participant_token(
        livekit_url,
        api_key,
        api_secret,
        room_name,
        f"browser-{user.get('user_id') or uuid.uuid4()}",
        "Browser Tester",
        metadata,
    )
    return {
        **token_payload,
        "call_id": db_call_id,
        "dispatch_id": getattr(dispatch, "id", None),
        "status": "dispatched",
        "agent_id": published_uuid,
        "agent_version_id": (resolved_agent or {}).get("agent_version_id"),
        "published_agent_uuid": (resolved_agent or {}).get("agent_id"),
        "started_at": started_at,
    }


@app.post("/api/calls/outbound")
async def api_calls_outbound(payload: OutboundCallPayload, user: dict = Depends(_require_auth)):
    _apply_config_env()
    resolved_agent = _resolve_published_agent_runtime_for_call(payload, user.get("_workspace_id"))
    published_uuid = str(payload.published_agent_uuid or "").strip()
    if not _sip_trunk_id():
        phone = _validate_phone_number(payload.phone_number)
        started_at = datetime.now(timezone.utc).isoformat()
        db.save_call_log(
            phone=phone,
            duration=0,
            transcript="",
            summary="Outbound call failed: SIP trunk not configured",
            recording_url="",
            caller_name="",
            sentiment="failed",
            owner_user_id=user.get("user_id"),
            workspace_id=user.get("_workspace_id"),
            status="failed",
            failure_reason="sip_failure",
            room_name="",
            agent_id=published_uuid,
            agent_version_id=(resolved_agent or {}).get("agent_version_id"),
            published_agent_uuid=(resolved_agent or {}).get("agent_id"),
            started_at=started_at,
        )
        raise HTTPException(
            status_code=500,
            detail="SIP trunk not configured. Set LIVEKIT_SIP_TRUNK_ID or OUTBOUND_TRUNK_ID.",
        )
    return await _dispatch_outbound_call(
            CallPayload(
                phone_number=payload.phone_number,
                agent_id=published_uuid,
                published_agent_uuid=published_uuid,
                first_line=payload.first_line,
            ),
            user,
            resolved_agent=resolved_agent,
    )


def _internal_outbound_test_enabled() -> bool:
    v = (os.environ.get("ENABLE_INTERNAL_TEST_CALLS") or "").strip().lower()
    return v in {"1", "true", "yes"}


def _verify_internal_test_secret(header_value: str | None) -> None:
    # Intentionally return 404 when disabled/misconfigured to avoid advertising this route.
    enabled = _internal_outbound_test_enabled()
    if not enabled:
        raise HTTPException(status_code=404, detail="Not found")
    expected = (os.environ.get("INTERNAL_TEST_CALL_SECRET") or "").strip()
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    provided = (header_value or "").strip()
    secret_match = secrets.compare_digest(expected, provided)
    if not secret_match:
        raise HTTPException(status_code=401, detail="Invalid internal test secret")


@app.post("/api/calls/outbound-test")
async def api_calls_outbound_test(
    payload: OutboundCallPayload,
    x_internal_test_secret: str | None = Header(default=None, alias="X-Internal-Test-Secret"),
):
    _apply_config_env()
    _verify_internal_test_secret(x_internal_test_secret)
    if not _sip_trunk_id():
        phone = _validate_phone_number(payload.phone_number)
        started_at = datetime.now(timezone.utc).isoformat()
        db.save_call_log(
            phone=phone,
            duration=0,
            transcript="",
            summary="Outbound test call failed: SIP trunk not configured",
            recording_url="",
            caller_name="",
            sentiment="failed",
            owner_user_id=None,
            workspace_id=None,
            status="failed",
            failure_reason="sip_failure",
            room_name="",
            agent_id=payload.agent_id,
            started_at=started_at,
        )
        raise HTTPException(
            status_code=500,
            detail="SIP trunk not configured. Set LIVEKIT_SIP_TRUNK_ID or OUTBOUND_TRUNK_ID.",
        )
    test_user = {
        "user_id": None,
        "email": "",
        "_workspace_id": None,
    }
    return await _dispatch_outbound_call(
        CallPayload(
            phone_number=payload.phone_number,
            agent_id=payload.agent_id,
            first_line=payload.first_line,
        ),
        test_user,
    )


@app.post("/api/sip/test-call")
async def api_sip_test_call(payload: SipTestCallPayload, user: dict = Depends(_require_auth)):
    """Create room, place outbound SIP via LiveKit API (sync errors), then dispatch agent with skip_sip_dial."""
    _apply_config_env()
    trunk_id = _sip_trunk_id()
    if not trunk_id:
        raise HTTPException(
            status_code=400,
            detail="SIP trunk not configured. Set LIVEKIT_SIP_TRUNK_ID or OUTBOUND_TRUNK_ID.",
        )
    phone = _validate_phone_number(payload.phone_number)
    resolved_agent = _resolve_published_agent_runtime_for_call(payload, user.get("_workspace_id"))
    published_uuid = str(payload.published_agent_uuid or "").strip()
    livekit_url, api_key, api_secret = _livekit_credentials()
    try:
        from livekit import api as lkapi
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LiveKit SDK import failed: {e}")

    dispatch_id = str(uuid.uuid4())
    room_name = f"sip-test-{phone.replace('+', '')}-{dispatch_id[:8]}"
    started_at = datetime.now(timezone.utc).isoformat()
    call_log = db.save_call_log(
        phone=phone,
        duration=0,
        transcript="",
        summary="SIP test call dispatching",
        recording_url="",
        caller_name="",
        sentiment="pending",
        owner_user_id=user.get("user_id"),
        workspace_id=user.get("_workspace_id"),
        status="dispatching",
        retry_count=0,
        max_retries=db.MAX_CALL_RETRIES,
        room_name=room_name,
        agent_id=published_uuid,
        agent_version_id=(resolved_agent or {}).get("agent_version_id"),
        published_agent_uuid=(resolved_agent or {}).get("agent_id"),
        started_at=started_at,
    )
    db_call_id = call_log.get("id")
    sip_identity = f"sip_{phone.replace('+', '')}"
    metadata = {
        "phone_number": phone,
        "agent_id": published_uuid,
        "call_id": dispatch_id,
        "db_call_id": db_call_id,
        "retry_count": 0,
        "max_retries": db.MAX_CALL_RETRIES,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "workspace_id": user.get("_workspace_id"),
        "skip_sip_dial": True,
    }
    metadata = _metadata_with_agent_runtime(metadata, resolved_agent)
    metadata = {k: v for k, v in metadata.items() if v is not None}

    lk = lkapi.LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
    try:
        await _create_livekit_room(lk, lkapi, livekit_url, room_name)
        try:
            await lk.sip.create_sip_participant(
                lkapi.CreateSIPParticipantRequest(
                    sip_trunk_id=trunk_id,
                    sip_call_to=phone,
                    room_name=room_name,
                    participant_identity=sip_identity,
                    participant_name=phone,
                    wait_until_answered=True,
                )
            )
        except Exception as e:
            reason = _sip_failure_reason(e)
            if db_call_id:
                db.mark_call_failed(db_call_id, reason, retry_count=0, max_retries=db.MAX_CALL_RETRIES)
            logger.warning(
                "SIP test dial failed room=%s trunk_id=%s dest=%s reason=%s error=%s",
                room_name,
                trunk_id,
                _mask_phone_e164(phone),
                reason,
                str(e)[:500],
            )
            raise HTTPException(
                status_code=502,
                detail=_friendly_livekit_error("SIP outbound dial", e, livekit_url),
            )
        if db_call_id:
            db.mark_call_answered(db_call_id, room_name=room_name)
        dispatch = await _dispatch_agent_to_room(lk, lkapi, livekit_url, room_name, metadata)
    finally:
        await lk.aclose()

    if db_call_id:
        db.update_call_log(db_call_id, status="dispatched", summary="SIP test call dispatched")

    logger.info(
        "SIP test call ok room=%s trunk_id=%s dest=%s dispatch_id=%s",
        room_name,
        trunk_id,
        _mask_phone_e164(phone),
        getattr(dispatch, "id", None),
    )
    return {
        "status": "ok",
        "room_name": room_name,
        "phone_number_masked": _mask_phone_e164(phone),
        "sip_status": "answered",
        "dispatch_id": getattr(dispatch, "id", None),
        "call_id": db_call_id or dispatch_id,
        "agent_id": published_uuid,
        "agent_version_id": (resolved_agent or {}).get("agent_version_id"),
        "published_agent_uuid": (resolved_agent or {}).get("agent_id"),
        "started_at": started_at,
    }


async def _dispatch_outbound_call(
    payload: CallPayload,
    user: dict,
    retry_row: dict | None = None,
    resolved_agent: dict | None = None,
) -> dict:
    _apply_config_env()
    phone = _validate_phone_number(payload.phone_number)
    if resolved_agent is None:
        call_uuid = payload.published_agent_uuid or payload.agent_id
        resolved_agent = _resolve_agent_runtime_for_call(call_uuid, user.get("_workspace_id"))
    chk = db.soft_limit_blocked(str(user.get("_workspace_id") or ""), "dispatch")
    if chk.get("blocked"):
        raise HTTPException(status_code=428, detail=chk)
    config = read_config()
    livekit_url = config.get("livekit_url") or os.environ.get("LIVEKIT_URL", "")
    api_key = config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY", "")
    api_secret = config.get("livekit_api_secret") or os.environ.get("LIVEKIT_API_SECRET", "")
    if not (livekit_url and api_key and api_secret):
        raise HTTPException(status_code=500, detail="LiveKit is not configured")

    try:
        from livekit import api as lkapi
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LiveKit SDK import failed: {e}")

    dispatch_id = str(uuid.uuid4())
    retry_count = int((retry_row or {}).get("retry_count") or 0) + (1 if retry_row else 0)
    max_retries = int((retry_row or {}).get("max_retries") or db.MAX_CALL_RETRIES)
    room_name = f"call-{phone.replace('+', '')}-{dispatch_id[:8]}"
    started_at = datetime.now(timezone.utc).isoformat()
    db_call_id = (retry_row or {}).get("id")
    if db_call_id:
        db.update_call_log(
            db_call_id,
            status="dispatching",
            failure_reason="",
            room_name=room_name,
            agent_id=payload.agent_id,
            agent_version_id=(resolved_agent or {}).get("agent_version_id"),
            published_agent_uuid=(resolved_agent or {}).get("agent_id"),
            retry_count=retry_count,
            started_at=started_at,
        )
    else:
        call_log = db.save_call_log(
            phone=phone,
            duration=0,
            transcript="",
            summary="Outbound call dispatching",
            recording_url="",
            caller_name="",
            sentiment="pending",
            owner_user_id=user.get("user_id"),
            workspace_id=user.get("_workspace_id"),
            status="dispatching",
            retry_count=0,
            max_retries=max_retries,
            room_name=room_name,
            agent_id=payload.agent_id,
            agent_version_id=(resolved_agent or {}).get("agent_version_id"),
            published_agent_uuid=(resolved_agent or {}).get("agent_id"),
            started_at=started_at,
        )
        db_call_id = call_log.get("id")

    metadata = {
        "phone_number": phone,
        "agent_id": payload.agent_id,
        "first_line": payload.first_line,
        "agent_version_id": (resolved_agent or {}).get("agent_version_id"),
        "published_agent_uuid": (resolved_agent or {}).get("agent_id"),
        "call_id": dispatch_id,
        "db_call_id": db_call_id,
        "retry_count": retry_count,
        "max_retries": max_retries,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "workspace_id": user.get("_workspace_id"),
    }
    metadata = _metadata_with_agent_runtime(metadata, resolved_agent)
    metadata = {k: v for k, v in metadata.items() if v is not None}

    lk = lkapi.LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
    try:
        await _create_livekit_room(lk, lkapi, livekit_url, room_name)
        dispatch = await _dispatch_agent_to_room(lk, lkapi, livekit_url, room_name, metadata)
    except Exception as e:
        if db_call_id:
            db.mark_call_failed(db_call_id, "sip_failure", retry_count=retry_count, max_retries=max_retries)
        raise HTTPException(status_code=502, detail=_friendly_livekit_error("Outbound call dispatch", e, livekit_url))
    finally:
        await lk.aclose()

    if db_call_id:
        db.update_call_log(db_call_id, status="dispatched", summary="Outbound call dispatched")

    return {
        "call_id": db_call_id or dispatch_id,
        "dispatch_id": getattr(dispatch, "id", None),
        "room_name": room_name,
        "status": "dispatched",
        "retry_count": retry_count,
        "max_retries": max_retries,
        "phone_number": phone,
        "agent_id": payload.agent_id,
        "agent_version_id": (resolved_agent or {}).get("agent_version_id"),
        "published_agent_uuid": (resolved_agent or {}).get("agent_id"),
        "started_at": started_at,
    }


@app.post("/call")
async def api_call(payload: CallPayload, user: dict = Depends(_require_auth)):
    return await _dispatch_outbound_call(payload, user)


@app.post("/api/call")
async def api_call_prefixed(payload: CallPayload, user: dict = Depends(_require_auth)):
    return await _dispatch_outbound_call(payload, user)


async def _retry_due_calls_once() -> int:
    _apply_config_env()
    rows = db.claim_due_call_retries(limit=int(os.environ.get("CALL_RETRY_BATCH_SIZE", "5") or 5))
    for row in rows:
        user = {
            "user_id": row.get("user_id"),
            "email": "",
            "_workspace_id": row.get("workspace_id"),
        }
        try:
            await _dispatch_outbound_call(
                CallPayload(phone_number=row.get("phone") or "", agent_id=row.get("agent_id")),
                user,
                retry_row=row,
            )
            logger.info("Retried call id=%s phone=%s retry_count=%s", row.get("id"), row.get("phone"), row.get("retry_count"))
        except Exception as e:
            logger.warning("Retry dispatch failed id=%s: %s", row.get("id"), e)
    return len(rows)


async def _retry_scheduler_loop() -> None:
    interval = int(os.environ.get("CALL_RETRY_POLL_SECONDS", "60") or 60)
    while True:
        try:
            await _retry_due_calls_once()
        except Exception:
            logger.exception("Retry scheduler loop failed")
        await asyncio.sleep(interval)


async def start_retry_scheduler() -> None:
    if os.environ.get("DISABLE_CALL_RETRY_SCHEDULER", "").lower() in {"1", "true", "yes"}:
        logger.info("Call retry scheduler disabled by env")
        return
    asyncio.create_task(_retry_scheduler_loop())


@app.post("/api/call/retry-due")
async def api_retry_due_calls(_user: dict = Depends(_require_admin)):
    count = await _retry_due_calls_once()
    return {"success": True, "claimed": count}

@app.get("/api/config")
async def api_get_config(_user: dict = Depends(_require_admin)):
    return read_config()

@app.post("/api/config")
async def api_post_config(request: Request, _user: dict = Depends(_require_admin)):
    data = await request.json()
    write_config(data)
    logger.info("Configuration updated via UI.")
    return {"status": "success"}


async def _log_deployment_integration() -> None:
    """One-shot integration probe for Railway/Vercel/Supabase — safe values only."""
    _apply_config_env()
    try:
        sb = db.get_supabase_config_status()
        lk = _livekit_config_status()
        groq = bool(os.environ.get("GROQ_API_KEY", "").strip())
        openai_present = bool(os.environ.get("OPENAI_API_KEY", "").strip())
        sarvam = bool(os.environ.get("SARVAM_API_KEY", "").strip())
        logger.info("[API] bootstrap=complete service=rapidx-ai-voice-agent-api")
        logger.info(
            "[CORS] explicit_origin_count=%s preview_regex=%s",
            len(_cors_origins()),
            "on" if bool(_cors_allow_origin_regex()) else "off",
        )
        logger.info(
            "[SUPABASE] configured=%s service_role_present=%s",
            sb.get("configured"),
            sb.get("service_role_key_present"),
        )
        logger.info(
            "[LIVEKIT] configured=%s url_valid=%s",
            lk.get("configured"),
            lk.get("url_valid"),
        )
        if not (lk.get("configured") and lk.get("url_valid")):
            detail = _livekit_operator_missing(lk)
            logger.warning("[LIVEKIT] incomplete_env missing=%s", detail)
        logger.info("[ORCHESTRATOR] groq_key_present=%s openai_key_present=%s sarvam_key_present=%s", groq, openai_present, sarvam)
        schema = db.check_agent_publish_uuid_schema()
        if schema.get("ok"):
            logger.info("[DB_MIGRATION_OK] agent_publish_uuid_contract duplicate_count=%s", schema.get("duplicate_count", 0))
        else:
            logger.warning("[DB_MIGRATION_MISSING] agent_publish_uuid_contract detail=%s", schema.get("message", schema))
        if not (groq or openai_present):
            logger.warning("[ERROR] No LLM API key — set GROQ_API_KEY and/or OPENAI_API_KEY for voice/agent models")
        if not sarvam:
            logger.warning("[ERROR] SARVAM_API_KEY missing — Sarvam STT/TTS will fail when provider is Sarvam")
    except Exception as e:
        logger.warning("[API] deployment_bootstrap_log_failed err=%s", e)



async def _api_list_call_logs(
    user: dict,
    *,
    limit: int,
    offset: int,
    created_at_gte: str | None,
    created_at_lte: str | None,
    status: str | None,
    agent_id: str | None,
    phone_search: str | None,
    failed_only: bool,
    transferred_only: bool,
    disposition: str | None,
) -> dict:
    _apply_config_env()
    try:
        return db.fetch_call_logs_v2(
            limit=limit,
            offset=offset,
            user_id=None,
            access_token=user.get("_access_token"),
            workspace_id=None,
            created_at_gte=created_at_gte,
            created_at_lte=created_at_lte,
            status=status,
            agent_id=agent_id,
            phone_search=phone_search,
            failed_only=failed_only,
            transferred_only=transferred_only,
            disposition=disposition,
        )
    except Exception as e:
        logger.error(f"Error fetching call logs: {e}")
        return {"items": [], "limit": limit, "offset": offset, "has_more": False}


@app.get("/api/logs")
async def api_get_logs(
    user: dict = Depends(_require_auth),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    created_at_gte: str | None = Query(None),
    created_at_lte: str | None = Query(None),
    status: str | None = Query(None),
    agent_id: str | None = Query(None),
    phone_search: str | None = Query(None),
    failed_only: bool = Query(False),
    transferred_only: bool = Query(False),
    disposition: str | None = Query(None),
):
    return await _api_list_call_logs(
        user,
        limit=limit,
        offset=offset,
        created_at_gte=created_at_gte,
        created_at_lte=created_at_lte,
        status=status,
        agent_id=agent_id,
        phone_search=phone_search,
        failed_only=failed_only,
        transferred_only=transferred_only,
        disposition=disposition,
    )


@app.get("/api/calls")
async def api_get_calls(
    user: dict = Depends(_require_auth),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    created_at_gte: str | None = Query(None),
    created_at_lte: str | None = Query(None),
    status: str | None = Query(None),
    agent_id: str | None = Query(None),
    phone_search: str | None = Query(None),
    failed_only: bool = Query(False),
    transferred_only: bool = Query(False),
    disposition: str | None = Query(None),
):
    return await _api_list_call_logs(
        user,
        limit=limit,
        offset=offset,
        created_at_gte=created_at_gte,
        created_at_lte=created_at_lte,
        status=status,
        agent_id=agent_id,
        phone_search=phone_search,
        failed_only=failed_only,
        transferred_only=transferred_only,
        disposition=disposition,
    )


@app.get("/api/calls/{call_log_id}")
@app.get("/api/logs/{call_log_id}")
async def api_get_call_log_detail(call_log_id: str, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    row = db.fetch_call_log_detail(call_log_id, workspace_id)
    if not row:
        raise HTTPException(status_code=404, detail="Call log not found")
    return row


@app.get("/api/stats")
async def api_get_stats(user: dict = Depends(_require_auth)):
    _apply_config_env()
    try:
        return db.fetch_stats(user_id=None, access_token=user.get("_access_token"))
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {"total_calls": 0, "answered_calls": 0, "failed_calls": 0, "total_bookings": 0, "avg_duration": 0, "average_duration": 0, "total_minutes": 0, "estimated_ai_cost": 0, "booking_rate": 0}


@app.get("/api/analytics")
async def api_get_analytics(user: dict = Depends(_require_auth)):
    return await api_get_stats(user)

@app.get("/api/contacts")
async def api_get_contacts(user: dict = Depends(_require_auth)):
    _apply_config_env()
    try:
        return db.fetch_contacts(user_id=None, access_token=user.get("_access_token"))
    except Exception as e:
        logger.error(f"Error fetching contacts: {e}")
        return []


@app.get("/api/agents")
async def api_get_agents(user: dict = Depends(_require_auth)):
    _apply_config_env()
    return db.fetch_agents(workspace_id=user.get("_workspace_id"), access_token=user.get("_access_token"))


@app.post("/api/agents")
async def api_create_agent(payload: AgentCreate, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.create_agent(
        workspace_id=workspace_id,
        user_id=user.get("user_id"),
        data=payload.model_dump(exclude_none=True),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Agent create failed"))
    return result["agent"]


@app.post("/api/agents/prompt-assist")
async def api_agents_prompt_assist(payload: PromptAssistPayload, user: dict = Depends(_require_auth)):
    """Rewrite or refine the agent system prompt using Groq (preferred) or OpenAI."""
    _ = user
    action = (payload.action or "improve").strip()
    if action not in _PROMPT_ASSIST_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid prompt assist action.")
    body = payload.model_copy(update={"action": action})
    prompt, provider, model = await _run_prompt_assist_llm(body)
    return {"prompt": prompt, "provider": provider, "model": model}


@app.get("/api/providers/options")
async def api_provider_options(_user: dict = Depends(_require_auth)):
    return _provider_options_payload()


@app.post("/api/agents/import")
async def api_import_agent(payload: AgentExport, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.import_agent(
        workspace_id=workspace_id,
        user_id=user.get("user_id"),
        export_data=payload.model_dump(exclude_none=True),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Agent import failed"))
    return result["agent"]


@app.get("/api/agents/{agent_id}")
async def api_get_agent(agent_id: str, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    agent = db.get_agent(agent_id, workspace_id, include_versions=True)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.patch("/api/agents/{agent_id}")
async def api_patch_agent(agent_id: str, payload: AgentPatch, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.update_agent(
        agent_id=agent_id,
        workspace_id=workspace_id,
        user_id=user.get("user_id"),
        data=payload.model_dump(exclude_none=True),
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Agent update failed"))
    return result["agent"]


@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.delete_agent(agent_id=agent_id, workspace_id=workspace_id, user_id=user.get("user_id"))
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Agent delete failed"))
    return {"success": True}


@app.post("/api/agents/{agent_id}/duplicate")
async def api_duplicate_agent(agent_id: str, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.duplicate_agent(agent_id=agent_id, workspace_id=workspace_id, user_id=user.get("user_id"))
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Agent duplicate failed"))
    return result["agent"]


@app.get("/api/agents/{agent_id}/export")
async def api_export_agent(agent_id: str, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.export_agent(agent_id=agent_id, workspace_id=workspace_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Agent export failed"))
    return result["export"]


@app.post("/api/agents/{agent_id}/versions")
async def api_create_agent_version(agent_id: str, payload: AgentVersionPatch, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.create_agent_version(
        agent_id=agent_id,
        workspace_id=workspace_id,
        user_id=user.get("user_id"),
        data=payload.model_dump(exclude_none=True),
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Agent version create failed"))
    return result["version"]


@app.patch("/api/agents/{agent_id}/versions/{version_id}")
async def api_patch_agent_version(agent_id: str, version_id: str, payload: AgentVersionPatch, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.update_agent_version(
        agent_id=agent_id,
        version_id=version_id,
        workspace_id=workspace_id,
        user_id=user.get("user_id"),
        data=payload.model_dump(exclude_none=True),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Agent version update failed"))
    return result["version"]


@app.post("/api/agents/{agent_id}/versions/{version_id}/publish")
async def api_publish_agent_version(agent_id: str, version_id: str, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = _require_workspace_id(user)
    result = db.publish_agent_version(
        agent_id=agent_id,
        version_id=version_id,
        workspace_id=workspace_id,
        user_id=user.get("user_id"),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Agent version publish failed"))
    return result


@app.get("/api/campaigns")
async def api_get_campaigns(user: dict = Depends(_require_auth)):
    _apply_config_env()
    return db.fetch_campaigns(access_token=user.get("_access_token"))


@app.get("/api/usage")
async def api_get_usage(user: dict = Depends(_require_auth)):
    _apply_config_env()
    return db.fetch_usage(access_token=user.get("_access_token"))


@app.get("/api/billing")
async def api_get_billing(user: dict = Depends(_require_auth)):
    _apply_config_env()
    summary = db.fetch_billing_summary(access_token=user.get("_access_token"))
    billing = _billing_settings(user)
    if billing:
        summary.update({
            "status": billing.get("status") or summary.get("status"),
            "stripe_customer_id": billing.get("stripe_customer_id"),
            "stripe_subscription_id": billing.get("stripe_subscription_id"),
            "current_period_end": billing.get("current_period_end"),
            "cancel_at_period_end": billing.get("cancel_at_period_end"),
        })
    summary["stripe_configured"] = _env_present("STRIPE_SECRET_KEY") and _env_present("STRIPE_PRICE_ID", "BILLING_STRIPE_PRICE_ID")
    return summary


@app.post("/api/billing/checkout")
async def api_billing_checkout(payload: CheckoutPayload, user: dict = Depends(_require_auth)):
    _apply_config_env()
    workspace_id = user.get("_workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Workspace is required before checkout.")
    stripe = _stripe_client()
    price_id = _stripe_price_id(payload.price_id)
    billing = _billing_settings(user)
    customer_id = billing.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.get("email"),
            metadata={
                "user_id": user.get("user_id") or "",
                "workspace_id": workspace_id,
            },
        )
        customer_id = customer.id
        _update_billing_settings(workspace_id, stripe_customer_id=customer_id)

    app_url = _public_app_url()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{app_url}/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{app_url}/billing?checkout=cancelled",
        client_reference_id=workspace_id,
        metadata={
            "user_id": user.get("user_id") or "",
            "workspace_id": workspace_id,
        },
        subscription_data={
            "metadata": {
                "user_id": user.get("user_id") or "",
                "workspace_id": workspace_id,
            }
        },
    )
    return {"url": session.url, "id": session.id}


@app.post("/api/billing/portal")
async def api_billing_portal(user: dict = Depends(_require_auth)):
    _apply_config_env()
    stripe = _stripe_client()
    billing = _billing_settings(user)
    customer_id = billing.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found for this workspace.")
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{_public_app_url()}/billing",
    )
    return {"url": session.url}


@app.post("/api/stripe/webhook")
async def api_stripe_webhook(request: Request):
    stripe = _stripe_client()
    webhook_secret = (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Stripe webhook secret is not configured.")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook signature: {e}")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object")
    if event_type == "checkout.session.completed":
        workspace_id = (data_object.get("metadata") or {}).get("workspace_id") or data_object.get("client_reference_id")
        _update_billing_settings(
            workspace_id,
            stripe_customer_id=data_object.get("customer"),
            stripe_subscription_id=data_object.get("subscription"),
            status="active",
            checkout_session_id=data_object.get("id"),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        metadata = data_object.get("metadata") or {}
        workspace_id = metadata.get("workspace_id")
        if workspace_id:
            _update_billing_settings(
                workspace_id,
                **_subscription_status_from_stripe(data_object),
            )
    elif event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
        subscription_id = data_object.get("subscription")
        logger.info("Stripe invoice event type=%s subscription=%s", event_type, subscription_id)

    return {"received": True, "type": event_type}


@app.get("/api/ops/readiness")
async def api_ops_readiness(_user: dict = Depends(_require_admin)):
    return _ops_readiness_payload()

@app.post("/api/call/single")
async def api_call_single(request: Request, user: dict = Depends(_require_auth)):
    data = await request.json()
    phone = data.get("phone_number") or data.get("phone") or data.get("to") or ""
    try:
        result = await _dispatch_outbound_call(
            CallPayload(phone_number=phone, agent_id=data.get("agent_id")),
            user,
        )
        return {"status": "ok", "room": result["room_name"], "phone": result["phone_number"], **result}
    except HTTPException as e:
        return {"status": "error", "message": e.detail}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/demo-token")
async def api_demo_token(user: dict = Depends(_require_auth)):
    config = read_config()
    try:
        from livekit.api import AccessToken, VideoGrants
        import random
        import json as _json
        room_name = f"demo-{random.randint(10000,99999)}"
        api_key    = config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY","")
        api_secret = config.get("livekit_api_secret") or os.environ.get("LIVEKIT_API_SECRET","")
        livekit_url = config.get("livekit_url") or os.environ.get("LIVEKIT_URL","")
        status = _livekit_config_status()
        if not status["configured"] or not status["url_valid"]:
            return {"error": "LiveKit not configured. Check LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET."}

        identity = f"demo-{user.get('user_id') or 'user'}"
        participant_meta = {
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "workspace_id": user.get("_workspace_id"),
        }
        token = (
            AccessToken(api_key, api_secret)
            .with_identity(identity)
            .with_name("Demo Caller")
            .with_metadata(_json.dumps({k: v for k, v in participant_meta.items() if v is not None}))
            .with_grants(VideoGrants(room_join=True, room=room_name))
            .with_ttl(timedelta(seconds=3600))
            .to_jwt()
        )

        from livekit import api as lkapi
        lk = lkapi.LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
        demo_dispatch = {
            "phone_number": "demo",
            "is_demo": True,
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "workspace_id": user.get("_workspace_id"),
        }
        await lk.agent_dispatch.create_dispatch(lkapi.CreateAgentDispatchRequest(
            agent_name="outbound-caller",
            room=room_name,
            metadata=_json.dumps({k: v for k, v in demo_dispatch.items() if v is not None}),
        ))
        await lk.aclose()
        return {"token": token, "room": room_name, "url": livekit_url}
    except Exception as e:
        return {"error": _friendly_livekit_error("Demo token", e, config.get("livekit_url") or os.environ.get("LIVEKIT_URL",""))}


@app.get("/api/livekit/test")
async def api_livekit_test(_user: dict = Depends(_require_auth)):
    config = read_config()
    livekit_url = config.get("livekit_url") or os.environ.get("LIVEKIT_URL", "")
    status = _livekit_config_status()
    if not status["configured"] or not status["url_valid"]:
        raise HTTPException(status_code=400, detail="LiveKit env vars are incomplete or invalid")
    try:
        from livekit import api as lkapi
        lk = lkapi.LiveKitAPI(
            url=livekit_url,
            api_key=config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY", ""),
            api_secret=config.get("livekit_api_secret") or os.environ.get("LIVEKIT_API_SECRET", ""),
        )
        rooms = await lk.room.list_rooms(lkapi.ListRoomsRequest())
        await lk.aclose()
        return {"success": True, "livekit": status, "room_count": len(rooms.rooms)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=_friendly_livekit_error("LiveKit API test", e, livekit_url))


# Serve Vite frontend
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets") if os.path.isdir(os.path.join(frontend_dist, "assets")) else None

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str, request: Request):
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        with open(index_path) as f:
            return HTMLResponse(f.read())

    app_url = _public_app_url()
    parsed_app = urlparse(app_url)
    request_host = request.url.netloc.lower()
    app_host = parsed_app.netloc.lower()
    if parsed_app.scheme in {"http", "https"} and app_host and "localhost" not in app_host and app_host != request_host:
        suffix = f"/{full_path}" if full_path else ""
        query = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"{app_url}{suffix}{query}", status_code=307)

    return HTMLResponse(
        """
        <main style="font-family: system-ui, sans-serif; max-width: 760px; margin: 48px auto; line-height: 1.5;">
          <h1>RapidX AI Voice API</h1>
          <p>The backend and LiveKit voice worker are running on Railway.</p>
          <p>Deploy the dashboard from <code>frontend/</code> on Vercel and set <code>NEXT_PUBLIC_API_URL</code> to this Railway API URL.</p>
          <ul>
            <li><a href="/health">/health</a></li>
            <li><a href="/api/health">/api/health</a></li>
            <li><a href="/api/livekit/health">/api/livekit/health</a></li>
            <li><a href="/api/sip/health">/api/sip/health</a></li>
          </ul>
        </main>
        """,
        status_code=200,
    )
