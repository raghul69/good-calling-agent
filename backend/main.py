import os
import sys
import logging
import json
import re
import uuid
import asyncio
import secrets
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from urllib.parse import urlparse

# Import routers once we create them
# from backend.routers import auth, config, calls, crm, logs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-api")

app = FastAPI(title="RapidX AI Dashboard API", version="2.0.0")


def _api_error(message: str, code: str = "api_error", request_id: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    logger.warning("HTTP %s %s request_id=%s detail=%s", exc.status_code, request.url.path, request_id, exc.detail)
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
    ]
    return list(dict.fromkeys([*origins, *defaults]))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    # Allow all Vercel deployments for this project name pattern (main, preview, branch deploys).
    allow_origin_regex=r"^https://good-calling-agent(?:-[a-z0-9-]+)?\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    livekit_status = _livekit_config_status()
    return {
        "status": "ok",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "service": "rapidx-ai-voice-agent-api",
        # Keep these top-level flags for easier deployment checks.
        "supabase_configured": supabase_status.get("configured", False),
        "service_role_key_present": supabase_status.get("service_role_key_present", False),
        "livekit_configured": livekit_status.get("configured", False),
        "integrations": {
            "supabase": supabase_status,
            "livekit": livekit_status,
        },
    }


@app.get("/health")
def health_check_root():
    return health_check()


@app.get("/api/livekit/health")
async def api_livekit_health():
    """Public probe: LiveKit env completeness and optional list_rooms reachability (no secrets in response)."""
    _apply_config_env()
    config = read_config()
    livekit_url = (config.get("livekit_url") or os.environ.get("LIVEKIT_URL", "")).strip()
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
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.config_manager import read_config, write_config


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


class LiveKitTokenPayload(BaseModel):
    room_name: str | None = None
    participant_identity: str | None = None
    participant_name: str | None = None
    agent_id: str | None = None


class BrowserTestPayload(BaseModel):
    agent_id: str | None = None


class OutboundCallPayload(BaseModel):
    phone_number: str
    agent_id: str | None = None


class SipTestCallPayload(BaseModel):
    phone_number: str
    agent_id: str | None = "test-agent"


PHONE_RE = re.compile(r"^\+[1-9]\d{7,15}$")


def _validate_phone_number(phone_number: str) -> str:
    phone = re.sub(r"[\s().-]+", "", (phone_number or "").strip())
    if not PHONE_RE.match(phone):
        raise HTTPException(
            status_code=400,
            detail="Phone number must be E.164 format, for example +919876543210",
        )
    return phone


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
            "Check LIVEKIT_URL, internet/DNS access, and Render environment variables."
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
        .with_ttl(3600)
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


def _require_auth(authorization: str = Header(default="")) -> dict:
    _apply_config_env()
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    result = db.auth_get_user(token)
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("message", "Invalid token"))
    result["_access_token"] = token
    ws = db.ensure_default_workspace(result.get("user_id") or "")
    if ws.get("success") and ws.get("workspace_id"):
        result["_workspace_id"] = ws["workspace_id"]
    else:
        result["_workspace_id"] = None
    return result


def _require_admin(user: dict = Depends(_require_auth)) -> dict:
    role = (user.get("role") or "").lower()
    roles = [str(r).lower() for r in (user.get("roles") or [])]
    if role == "admin" or "admin" in roles:
        return user
    raise HTTPException(status_code=403, detail="Admin access required")


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
    ws = db.ensure_default_workspace(result.get("user_id") or "")
    if ws.get("success"):
        result["workspace_id"] = ws.get("workspace_id")
        result["workspace_created"] = ws.get("created", False)
    return result


@app.get("/api/workspace")
async def api_workspace(user: dict = Depends(_require_auth)):
    return db.fetch_workspace_summary(user)


@app.post("/api/livekit/token")
async def api_livekit_token(payload: LiveKitTokenPayload, user: dict = Depends(_require_auth)):
    livekit_url, api_key, api_secret = _livekit_credentials()
    room_name = payload.room_name or _new_room_name("browser", payload.agent_id or user.get("user_id") or "user")
    identity = payload.participant_identity or f"browser-{user.get('user_id') or uuid.uuid4()}"
    metadata = {
        "agent_id": payload.agent_id,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "workspace_id": user.get("_workspace_id"),
        "is_browser_test": True,
    }
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

    room_name = _new_room_name("browser", payload.agent_id or user.get("user_id") or "agent")
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
        agent_id=payload.agent_id,
        started_at=started_at,
    )
    db_call_id = call_log.get("id")
    metadata = {
        "phone_number": "demo",
        "is_demo": True,
        "is_browser_test": True,
        "agent_id": payload.agent_id,
        "db_call_id": db_call_id,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "workspace_id": user.get("_workspace_id"),
    }

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
        "started_at": started_at,
    }


@app.post("/api/calls/outbound")
async def api_calls_outbound(payload: OutboundCallPayload, user: dict = Depends(_require_auth)):
    _apply_config_env()
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
            agent_id=payload.agent_id,
            started_at=started_at,
        )
        raise HTTPException(
            status_code=500,
            detail="SIP trunk not configured. Set LIVEKIT_SIP_TRUNK_ID or OUTBOUND_TRUNK_ID.",
        )
    return await _dispatch_outbound_call(
        CallPayload(phone_number=payload.phone_number, agent_id=payload.agent_id),
        user,
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
        CallPayload(phone_number=payload.phone_number, agent_id=payload.agent_id),
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
        agent_id=payload.agent_id,
        started_at=started_at,
    )
    db_call_id = call_log.get("id")
    sip_identity = f"sip_{phone.replace('+', '')}"
    metadata = {
        "phone_number": phone,
        "agent_id": payload.agent_id,
        "call_id": dispatch_id,
        "db_call_id": db_call_id,
        "retry_count": 0,
        "max_retries": db.MAX_CALL_RETRIES,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "workspace_id": user.get("_workspace_id"),
        "skip_sip_dial": True,
    }
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
        "agent_id": payload.agent_id,
        "started_at": started_at,
    }


async def _dispatch_outbound_call(payload: CallPayload, user: dict, retry_row: dict | None = None) -> dict:
    _apply_config_env()
    phone = _validate_phone_number(payload.phone_number)
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
            started_at=started_at,
        )
        db_call_id = call_log.get("id")

    metadata = {
        "phone_number": phone,
        "agent_id": payload.agent_id,
        "call_id": dispatch_id,
        "db_call_id": db_call_id,
        "retry_count": retry_count,
        "max_retries": max_retries,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "workspace_id": user.get("_workspace_id"),
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}

    lk = lkapi.LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
    try:
        await _create_livekit_room(lk, lkapi, livekit_url, room_name)
        dispatch = await lk.agent_dispatch.create_dispatch(
            lkapi.CreateAgentDispatchRequest(
                agent_name=_agent_name(),
                room=room_name,
                metadata=json.dumps(metadata),
            )
        )
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


@app.on_event("startup")
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

import backend.db as db
from fastapi.responses import PlainTextResponse

@app.get("/api/logs")
async def api_get_logs(user: dict = Depends(_require_auth)):
    _apply_config_env()
    try:
        logs = db.fetch_call_logs(
            limit=50,
            user_id=None,
            access_token=user.get("_access_token"),
        )
        return logs
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return []


@app.get("/api/calls")
async def api_get_calls(user: dict = Depends(_require_auth)):
    return await api_get_logs(user)

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
    return db.fetch_agents(access_token=user.get("_access_token"))


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
    return db.fetch_billing_summary(access_token=user.get("_access_token"))

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
            .with_ttl(3600)
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
async def serve_frontend(full_path: str):
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        with open(index_path) as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Frontend not built. Run 'npm run build' in /frontend</h1>")
