import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from urllib.parse import urlparse

# Import routers once we create them
# from backend.routers import auth, config, calls, crm, logs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-api")

app = FastAPI(title="RapidX AI Dashboard API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
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

# Provide some placeholder routes from old ui_server logic during transition
# Allow running this file directly (`python backend/main.py`) and as module.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.config_manager import read_config, write_config
from fastapi import Request, Header


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


def _apply_config_env() -> None:
    config = read_config()
    if config.get("supabase_url"):
        os.environ["SUPABASE_URL"] = config.get("supabase_url", "")
    if config.get("supabase_key"):
        os.environ["SUPABASE_KEY"] = config.get("supabase_key", "")
        os.environ.setdefault("SUPABASE_ANON_KEY", config.get("supabase_key", ""))
    if config.get("supabase_service_role_key"):
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = config.get("supabase_service_role_key", "")


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

@app.get("/api/stats")
async def api_get_stats(user: dict = Depends(_require_auth)):
    _apply_config_env()
    try:
        return db.fetch_stats(user_id=None, access_token=user.get("_access_token"))
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {"total_calls": 0, "total_bookings": 0, "avg_duration": 0, "booking_rate": 0}

@app.get("/api/contacts")
async def api_get_contacts(user: dict = Depends(_require_auth)):
    _apply_config_env()
    try:
        return db.fetch_contacts(user_id=None, access_token=user.get("_access_token"))
    except Exception as e:
        logger.error(f"Error fetching contacts: {e}")
        return []

@app.post("/api/call/single")
async def api_call_single(request: Request, user: dict = Depends(_require_auth)):
    data = await request.json()
    phone = (data.get("phone") or "").strip()
    if not phone.startswith("+"):
        return {"status": "error", "message": "Phone number must start with + and country code"}
    config = read_config()
    try:
        import random, json as _json
        from livekit import api as lkapi
        lk = lkapi.LiveKitAPI(url=config.get("livekit_url") or os.environ.get("LIVEKIT_URL",""), api_key=config.get("livekit_api_key") or os.environ.get("LIVEKIT_API_KEY",""), api_secret=config.get("livekit_api_secret") or os.environ.get("LIVEKIT_API_SECRET",""))
        room_name = f"call-{phone.replace('+','')}-{random.randint(1000,9999)}"
        dispatch_meta = {
            "phone_number": phone,
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "workspace_id": user.get("_workspace_id"),
        }
        dispatch = await lk.agent_dispatch.create_dispatch(lkapi.CreateAgentDispatchRequest(
            agent_name="outbound-caller",
            room=room_name,
            metadata=_json.dumps({k: v for k, v in dispatch_meta.items() if v is not None}),
        ))
        await lk.aclose()
        return {"status": "ok", "dispatch_id": dispatch.id, "room": room_name, "phone": phone}
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
