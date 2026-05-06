import logging
import os
import csv
import copy
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from supabase import Client, ClientOptions, create_client

logger = logging.getLogger("backend-db")
_SUPABASE_HTTP_CLIENT: httpx.Client | None = None

RETRYABLE_CALL_FAILURES = {"no_answer", "busy", "sip_failure", "timeout"}
MAX_CALL_RETRIES = int(os.getenv("MAX_CALL_RETRIES", "3") or 3)
CALL_RETRY_DELAY_SECONDS = int(os.getenv("CALL_RETRY_DELAY_SECONDS", "300") or 300)

DEFAULT_WELCOME_MESSAGE = "Hello, this is your AI assistant. Can you hear me?"
FALLBACK_FIRST_LINE = "ஹலோ sir, MAXR Consultancy ல இருந்து பேசுறேன். Chennai la property பார்க்கிறீங்களா?"
DEFAULT_SYSTEM_PROMPT = (
    "You are a warm, concise AI voice assistant. Keep every response short, "
    "ask one question at a time, and help the caller complete their goal."
)
DEFAULT_MULTILINGUAL_PROMPTS = {
    "english": "Speak in clear Indian English with a warm professional tone.",
    "hindi": "Speak in polite Hindi. Keep sentences short and easy to understand.",
    "tamil": "Speak in polite spoken Tamil. Keep replies short and natural.",
    "tamil_tanglish": "Speak in natural Tanglish: Tamil sentence flow with common English business words where useful.",
}
DEFAULT_PROMPT_VARIABLES = [
    {"name": "caller_name", "description": "Caller name if known", "required": False},
    {"name": "business_name", "description": "Business or workspace name", "required": False},
]
DEFAULT_LLM_CONFIG = {
    "provider": "groq",
    "model": "llama-3.1-8b-instant",
    "temperature": 0.4,
    "max_tokens": 48,
    "fallback_providers": ["openai"],
}
DEFAULT_AUDIO_CONFIG = {
    "tts_provider": "sarvam",
    "tts_model": "bulbul:v3",
    "tts_voice": "kavya",
    "tts_language": "en-IN",
    "stt_provider": "sarvam",
    "stt_model": "saaras:v3",
    "stt_language": "unknown",
    "noise_suppression": True,
}
DEFAULT_ENGINE_CONFIG = {
    "language_profile": "multilingual",
    "stt_min_endpointing_delay": 0.25,
    "max_turns": 8,
    "silence_timeout_seconds": 6,
    "interruption_words": [],
    "response_latency_mode": "fast",
    "agent_tone": "",
    "business_type": "",
    "vertical": "",
    "language_config": {
        "language": "",
        "style": "",
        "tone": "",
        "formality": "",
    },
}
DEFAULT_CALL_CONFIG = {
    "retry_enabled": True,
    "max_retries": MAX_CALL_RETRIES,
    "warm_transfer_enabled": True,
    "final_call_message": "",
    "silence_hangup_enabled": True,
    "silence_hangup_seconds": 45,
    "total_call_timeout_seconds": 0,
    "transfer_destination_e164": "",
}
DEFAULT_ANALYTICS_CONFIG = {
    "track_call_summaries": True,
    "track_provider_usage": True,
}


def _tamil_real_estate_template_seed() -> Dict[str, Any]:
    return {
        "default_language": "tamil_tanglish",
        "engine_config": {
            "vertical": "tamil_real_estate",
            "language_profile": "tamil_tanglish",
            "business_type": "real_estate",
            "language_config": {
                "language": "ta-IN",
                "style": "Tanglish",
                "tone": "warm",
                "formality": "conversational",
            },
        },
        "welcome_message": "Vanakkam, naan unga Tamil real-estate assistant — budget, locality, timeline collect pannuven. Ungalodu pesalaama?",
        "system_prompt": (
            "Speak naturally in Tamil/Tanglish. Reply in one short sentence only. "
            "Ask one question at a time. Respond fast."
        ),
        "multilingual_prompts": {
            "tamil": "Warm spoken Tamil suited for Chennai/Coimbatore property conversations.",
            "tamil_tanglish": DEFAULT_MULTILINGUAL_PROMPTS.get("tamil_tanglish", ""),
            "english": "Clear Indian English for loan and budget discussions.",
            "hindi": DEFAULT_MULTILINGUAL_PROMPTS.get("hindi", ""),
        },
        "audio_config": {"tts_language": "ta-IN", "tts_voice": "priya"},
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_dict(values: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}


def _merge_json(defaults: Dict[str, Any], override: Any) -> Dict[str, Any]:
    merged = copy.deepcopy(defaults)
    if isinstance(override, dict):
        for key, value in override.items():
            if value is not None:
                merged[key] = value
    return merged


def _as_list(value: Any, default: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return value if isinstance(value, list) else copy.deepcopy(default)


def _supabase_settings(service_role: bool = False) -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip()
    anon_key = (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    key = service_key if service_role and service_key else anon_key or service_key
    return url, key


def _get_supabase_http_client() -> httpx.Client:
    global _SUPABASE_HTTP_CLIENT
    if _SUPABASE_HTTP_CLIENT is None:
        timeout_s = float(os.getenv("SUPABASE_HTTP_TIMEOUT_SECONDS", "120") or 120)
        _SUPABASE_HTTP_CLIENT = httpx.Client(timeout=httpx.Timeout(timeout_s))
    return _SUPABASE_HTTP_CLIENT


def _friendly_supabase_error(action: str, error: Exception) -> str:
    url, _key = _supabase_settings()
    host = urlparse(url).netloc or "unknown"
    message = str(error)
    if "[Errno 11001]" in message or "getaddrinfo failed" in message:
        return (
            f"{action} failed: DNS lookup failed for Supabase host '{host}'. "
            "Check SUPABASE_URL, internet/DNS access, and Railway environment variables."
        )
    return message


def _missing_schema_column(error: Exception, column: str) -> bool:
    msg = str(error)
    return "PGRST204" in msg and f"'{column}' column" in msg


def _retryable_supabase_error(error: Exception) -> bool:
    msg = str(error).lower()
    needles = (
        "timeout",
        "timed out",
        "connection reset",
        "connection aborted",
        "temporary",
        "503",
        "502",
        "429",
        "504",
        "econnreset",
        "remote protocol error",
        "try again",
        "overload",
        "broken pipe",
        "connection refused",
    )
    return any(n in msg for n in needles)


def get_supabase_config_status() -> Dict[str, Any]:
    url, key = _supabase_settings()
    parsed = urlparse(url)
    return {
        "configured": bool(url and key and parsed.scheme in {"http", "https"} and parsed.netloc),
        "url_present": bool(url),
        "key_present": bool(key),
        "service_role_key_present": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()),
        "url_valid": bool(parsed.scheme in {"http", "https"} and parsed.netloc),
    }


def check_agent_publish_uuid_schema() -> Dict[str, Any]:
    sb = get_supabase(service_role=True)
    if not sb:
        return {"ok": False, "message": "Supabase not configured"}
    try:
        sb.table("agents").select("id,published_agent_uuid,config_json").limit(1).execute()
        rows = (
            sb.table("agents")
            .select("published_agent_uuid")
            .not_.is_("published_agent_uuid", "null")
            .limit(1000)
            .execute()
        )
        seen: set[str] = set()
        duplicates: set[str] = set()
        for row in rows.data or []:
            value = str(row.get("published_agent_uuid") or "").strip()
            if not value:
                continue
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        return {
            "ok": not duplicates,
            "columns": {"published_agent_uuid": True, "config_json": True},
            "duplicate_count": len(duplicates),
        }
    except Exception as e:
        return {
            "ok": False,
            "message": _friendly_supabase_error("Agent publish UUID schema check", e),
            "columns": {"published_agent_uuid": False, "config_json": False},
        }


def get_supabase(access_token: str | None = None, service_role: bool = False) -> Client | None:
    url, key = _supabase_settings(service_role=service_role)
    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_KEY not set.")
        return None
    if not get_supabase_config_status()["url_valid"]:
        logger.error("SUPABASE_URL is invalid. Expected https://<project-ref>.supabase.co")
        return None
    try:
        options = ClientOptions(httpx_client=_get_supabase_http_client())
        client = create_client(url, key, options=options)
        if access_token:
            client.postgrest.auth(access_token)
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {_friendly_supabase_error('Supabase client setup', e)}")
        return None


def ensure_default_workspace(user_id: str) -> Dict[str, Any]:
    """Create a personal workspace + membership if the user has none (service role)."""
    if not user_id:
        return {"success": False, "message": "user_id required"}
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        existing = (
            sb.table("workspace_members")
            .select("workspace_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            wid = existing.data[0].get("workspace_id")
            return {"success": True, "workspace_id": wid, "created": False}
        ws = (
            sb.table("workspaces")
            .insert({"name": "Personal", "created_by": user_id})
            .execute()
        )
        row = (ws.data or [{}])[0]
        wid = row.get("id")
        if not wid:
            return {"success": False, "message": "Workspace insert returned no id"}
        sb.table("workspace_members").insert(
            {"workspace_id": wid, "user_id": user_id, "role": "owner"}
        ).execute()
        try:
            sb.table("workspace_settings").insert({"workspace_id": wid, "settings": {}}).execute()
        except Exception:
            pass
        return {"success": True, "workspace_id": wid, "created": True}
    except Exception as e:
        message = _friendly_supabase_error("ensure_default_workspace", e)
        logger.error(f"ensure_default_workspace failed: {message}")
        return {"success": False, "message": message}


def fetch_workspace_summary(user: Dict[str, Any]) -> Dict[str, Any]:
    workspace_id = user.get("_workspace_id")
    if not workspace_id:
        return {
            "id": None,
            "name": "Personal",
            "role": user.get("role") or "user",
            "member_count": 1,
            "settings": {},
        }
    sb = get_supabase(service_role=True)
    if not sb:
        return {"id": workspace_id, "name": "Personal", "role": user.get("role") or "user", "member_count": 1, "settings": {}}
    try:
        workspace = sb.table("workspaces").select("id,name").eq("id", workspace_id).limit(1).execute()
        members = sb.table("workspace_members").select("user_id,role").eq("workspace_id", workspace_id).execute()
        settings = sb.table("workspace_settings").select("settings").eq("workspace_id", workspace_id).limit(1).execute()
        member_rows = members.data or []
        raw_role = None
        for row in member_rows:
            if row.get("user_id") == user.get("user_id"):
                raw_role = row.get("role")
                break
        if raw_role is None:
            raw_role = user.get("_workspace_role")
        role = db.normalize_workspace_role(raw_role or user.get("role"))
        return {
            "id": workspace_id,
            "name": ((workspace.data or [{}])[0].get("name") or "Personal"),
            "role": role,
            "member_count": len(member_rows) or 1,
            "settings": ((settings.data or [{}])[0].get("settings") or {}),
        }
    except Exception as e:
        logger.error(f"Failed to fetch workspace summary: {_friendly_supabase_error('Fetch workspace', e)}")
        return {"id": workspace_id, "name": "Personal", "role": user.get("role") or "member", "member_count": 1, "settings": {}}


VALID_WORKSPACE_ROLES = frozenset({"owner", "admin", "agent_manager", "viewer"})
AGENT_MANAGER_ROLES = frozenset({"owner", "admin", "agent_manager"})
ADMIN_ONLY_ROLES = frozenset({"owner", "admin"})


def normalize_workspace_role(role: str | None) -> str:
    r = str(role or "viewer").lower().strip()
    if r == "member":
        return "viewer"
    if r in VALID_WORKSPACE_ROLES:
        return r
    return "viewer"


def list_user_workspace_memberships(user_id: str) -> List[Dict[str, Any]]:
    """All workspaces visible to user (service role)."""
    if not user_id:
        return []
    sb = get_supabase(service_role=True)
    if not sb:
        return []
    try:
        res = (
            sb.table("workspace_members")
            .select("workspace_id,role,workspaces(name)")
            .eq("user_id", user_id)
            .execute()
        )
        rows: List[Dict[str, Any]] = []
        for row in res.data or []:
            ws = row.get("workspaces")
            name = ws.get("name") if isinstance(ws, dict) else None
            rows.append(
                {
                    "workspace_id": row.get("workspace_id"),
                    "name": name or "Workspace",
                    "role": normalize_workspace_role(row.get("role")),
                }
            )
        return [r for r in rows if r.get("workspace_id")]
    except Exception as e:
        logger.error(f"list_user_workspace_memberships: {_friendly_supabase_error('List workspaces', e)}")
        return []


def workspace_member_role(user_id: str | None, workspace_id: str | None) -> str | None:
    if not user_id or not workspace_id:
        return None
    sb = get_supabase(service_role=True)
    if not sb:
        return None
    try:
        res = (
            sb.table("workspace_members")
            .select("role")
            .eq("workspace_id", workspace_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0]
        return normalize_workspace_role(row.get("role")) if row else None
    except Exception as e:
        logger.warning(f"workspace_member_role lookup failed: {e}")
        return None


def resolve_active_workspace_id(user_id: str, preferred_workspace_id: str | None = None) -> tuple[str | None, str | None]:
    """
    Prefer valid header workspace membership; otherwise first membership.
    Creates default workspace via ensure_default_workspace if still empty.
    Returns (workspace_id, normalized_role) or (None, None).
    """
    memberships = list_user_workspace_memberships(user_id)
    if not memberships:
        ensured = ensure_default_workspace(user_id)
        if ensured.get("success") and ensured.get("workspace_id"):
            wid = ensured.get("workspace_id")
            role = workspace_member_role(user_id, wid) or "owner"
            return str(wid), role
        return None, None
    pref = (preferred_workspace_id or "").strip()
    if pref:
        for row in memberships:
            if str(row.get("workspace_id")) == pref:
                return pref, normalize_workspace_role(row.get("role"))
        return None, None
    row0 = memberships[0]
    return str(row0.get("workspace_id")), row0.get("role") or "viewer"


def fetch_profile_row(user_id: str | None) -> Dict[str, Any] | None:
    if not user_id:
        return None
    sb = get_supabase(service_role=True)
    if not sb:
        return None
    try:
        res = sb.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        return (res.data or [None])[0]
    except Exception as e:
        logger.debug(f"profiles read skipped: {e}")
        return None


def upsert_profile_row(user_id: str | None, display_name: str | None = None, avatar_url: str | None = None) -> Dict[str, Any]:
    if not user_id:
        return {"success": False, "message": "user id required"}
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    payload: Dict[str, Any] = {"id": user_id}
    if display_name is not None:
        payload["display_name"] = display_name
    if avatar_url is not None:
        payload["avatar_url"] = avatar_url
    try:
        sb.table("profiles").upsert(payload).execute()
        return {"success": True, "profile": fetch_profile_row(user_id)}
    except Exception as e:
        msg = _friendly_supabase_error("profiles upsert", e)
        return {"success": False, "message": msg}


def _audit_workspace_event(
    workspace_id: str | None,
    user_id: str | None,
    action: str,
    entity_type: str = "",
    entity_id: str | None = None,
    payload: Dict[str, Any] | None = None,
) -> None:
    if not workspace_id:
        return
    sb = get_supabase(service_role=True)
    if not sb:
        return
    try:
        sb.table("audit_logs").insert(
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "action": action,
                "entity_type": entity_type or "workspace",
                "entity_id": entity_id or "",
                "payload": payload or {},
            }
        ).execute()
    except Exception as e:
        logger.debug(f"audit skipped: {_friendly_supabase_error('audit', e)}")


def get_workspace_settings(workspace_id: str | None) -> Dict[str, Any]:
    if not workspace_id:
        return {}
    sb = get_supabase(service_role=True)
    if not sb:
        return {}
    try:
        res = sb.table("workspace_settings").select("settings").eq("workspace_id", workspace_id).limit(1).execute()
        return ((res.data or [{}])[0].get("settings") or {})
    except Exception as e:
        logger.error(f"Failed to fetch workspace settings: {_friendly_supabase_error('Fetch workspace settings', e)}")
        return {}


def update_workspace_settings(workspace_id: str | None, updates: Dict[str, Any]) -> Dict[str, Any]:
    if not workspace_id:
        return {"success": False, "message": "workspace_id required"}
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        current = get_workspace_settings(workspace_id)
        merged = {**current, **{k: v for k, v in updates.items() if v is not None}}
        res = (
            sb.table("workspace_settings")
            .upsert({"workspace_id": workspace_id, "settings": merged, "updated_at": datetime.now(timezone.utc).isoformat()})
            .execute()
        )
        return {"success": True, "settings": ((res.data or [{}])[0].get("settings") or merged)}
    except Exception as e:
        message = _friendly_supabase_error("Update workspace settings", e)
        logger.error(f"Failed to update workspace settings: {message}")
        return {"success": False, "message": message}


def save_call_log(
    phone: str,
    duration: int,
    transcript: str,
    summary: str,
    recording_url: str,
    caller_name: str = "",
    sentiment: str = "unknown",
    estimated_cost_usd: float = 0.0,
    call_date: str = "",
    call_hour: int | None = None,
    call_day_of_week: str = "",
    was_booked: bool = False,
    interrupt_count: int = 0,
    owner_user_id: str | None = None,
    workspace_id: str | None = None,
    status: str = "completed",
    retry_count: int = 0,
    max_retries: int | None = None,
    failure_reason: str = "",
    room_name: str = "",
    agent_id: str | None = None,
    agent_version_id: str | None = None,
    published_agent_uuid: str | None = None,
    started_at: str | None = None,
) -> Dict[str, Any]:
    _db_start = time.perf_counter()
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}

    payload = {
        "phone": phone or "unknown",
        "duration": int(duration or 0),
        "transcript": transcript or "",
        "summary": summary or "",
        "recording_url": recording_url or "",
        "caller_name": caller_name or "",
        "sentiment": sentiment or "unknown",
        "estimated_cost_usd": float(estimated_cost_usd or 0.0),
        "call_date": call_date or None,
        "call_hour": call_hour,
        "call_day_of_week": call_day_of_week or "",
        "was_booked": bool(was_booked),
        "interrupt_count": int(interrupt_count or 0),
        "status": status or "completed",
        "retry_count": int(retry_count or 0),
        "max_retries": int(max_retries if max_retries is not None else MAX_CALL_RETRIES),
        "failure_reason": failure_reason or "",
        "room_name": room_name or "",
        "agent_id": agent_id,
        "agent_version_id": agent_version_id,
        "published_agent_uuid": published_agent_uuid or (agent_id if agent_id and agent_version_id else None),
        "phone_number": phone or "unknown",
        "started_at": started_at,
    }
    if owner_user_id:
        payload["user_id"] = owner_user_id
    if workspace_id:
        payload["workspace_id"] = workspace_id
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            res = sb.table("call_logs").insert(payload).execute()
            row = (res.data or [{}])[0]
            rid = row.get("id")
            logger.info("[DB_SAVE_MS] table=call_logs op=insert id=%s ms=%s", rid, int((time.perf_counter() - _db_start) * 1000))
            logger.info("[CRM] save_call_log success id=%s attempt=%s", rid, attempt + 1)
            return {"success": True, "id": rid}
        except Exception as e:
            last_exc = e
            message = _friendly_supabase_error("Save call log", e)
            log_fn = logger.warning if attempt == 0 and _retryable_supabase_error(e) else logger.error
            log_fn("[CRM] save_call_log failed attempt=%s: %s", attempt + 1, message)
            if attempt == 0 and _retryable_supabase_error(e):
                time.sleep(0.35)
                continue
            logger.error("[ERROR] save_call_log exhausted after retry: %s", message)
            return {"success": False, "message": message}
    return {
        "success": False,
        "message": _friendly_supabase_error("Save call log", last_exc) if last_exc else "Save call log failed",
    }


def update_call_log(call_id: Any, **fields: Any) -> Dict[str, Any]:
    _db_start = time.perf_counter()
    if not call_id:
        return {"success": False, "message": "call_id required"}
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    clean = dict(fields)
    if not clean:
        return {"success": True}
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            sb.table("call_logs").update(clean).eq("id", call_id).execute()
            logger.info("[DB_SAVE_MS] table=call_logs op=update id=%s ms=%s", call_id, int((time.perf_counter() - _db_start) * 1000))
            logger.info("[CRM] update_call_log success id=%s attempt=%s fields=%s", call_id, attempt + 1, list(clean.keys()))
            return {"success": True}
        except Exception as e:
            last_exc = e
            message = _friendly_supabase_error("Update call log", e)
            log_fn = logger.warning if attempt == 0 and _retryable_supabase_error(e) else logger.error
            log_fn("[CRM] update_call_log failed id=%s attempt=%s: %s", call_id, attempt + 1, message)
            if attempt == 0 and _retryable_supabase_error(e):
                time.sleep(0.35)
                continue
            logger.error("[ERROR] update_call_log exhausted id=%s: %s", call_id, message)
            return {"success": False, "message": message}
    return {
        "success": False,
        "message": _friendly_supabase_error("Update call log", last_exc) if last_exc else "Update failed",
    }


def mark_call_answered(call_id: Any, room_name: str = "") -> Dict[str, Any]:
    return update_call_log(
        call_id,
        status="answered",
        failure_reason="",
        next_retry_at=None,
        room_name=room_name,
    )


def mark_call_completed(call_id: Any, **fields: Any) -> Dict[str, Any]:
    return update_call_log(call_id, status="completed", next_retry_at=None, **fields)


def mark_call_failed(
    call_id: Any,
    reason: str,
    retry_count: int = 0,
    max_retries: int | None = None,
    retryable: bool = True,
) -> Dict[str, Any]:
    max_attempts = int(max_retries if max_retries is not None else MAX_CALL_RETRIES)
    next_count = int(retry_count or 0)
    normalized_reason = reason if reason in RETRYABLE_CALL_FAILURES else "sip_failure"
    should_retry = retryable and normalized_reason in RETRYABLE_CALL_FAILURES and next_count < max_attempts
    next_retry_at = (
        (datetime.now(timezone.utc) + timedelta(seconds=CALL_RETRY_DELAY_SECONDS)).isoformat()
        if should_retry
        else None
    )
    return update_call_log(
        call_id,
        status="retry_scheduled" if should_retry else "failed",
        failure_reason=normalized_reason,
        retry_count=next_count,
        max_retries=max_attempts,
        next_retry_at=next_retry_at,
    )


def claim_due_call_retries(limit: int = 5) -> List[Dict[str, Any]]:
    sb = get_supabase(service_role=True)
    if not sb:
        return []
    now = datetime.now(timezone.utc).isoformat()
    try:
        res = (
            sb.table("call_logs")
            .select("*")
            .eq("status", "retry_scheduled")
            .lte("next_retry_at", now)
            .order("next_retry_at", desc=False)
            .limit(limit)
            .execute()
        )
        claimed: List[Dict[str, Any]] = []
        for row in res.data or []:
            if int(row.get("retry_count") or 0) >= int(row.get("max_retries") or MAX_CALL_RETRIES):
                mark_call_failed(row.get("id"), row.get("failure_reason") or "sip_failure", row.get("retry_count") or 0, row.get("max_retries") or MAX_CALL_RETRIES, retryable=False)
                continue
            update = (
                sb.table("call_logs")
                .update({"status": "retrying", "next_retry_at": None})
                .eq("id", row.get("id"))
                .eq("status", "retry_scheduled")
                .execute()
            )
            if update.data:
                claimed.append(row)
        return claimed
    except Exception as e:
        logger.error(f"Failed to claim due retries: {_friendly_supabase_error('Claim retries', e)}")
        return []


def fetch_call_logs(
    limit: int = 50,
    user_id: str | None = None,
    access_token: str | None = None,
    workspace_id: str | None = None,
) -> List[Dict[str, Any]]:
    prefer_service = bool(workspace_id)
    sb = get_supabase(access_token=None if prefer_service else access_token, service_role=prefer_service)
    if not sb:
        return []
    try:
        query = sb.table("call_logs").select("*").order("created_at", desc=True).limit(limit)
        if workspace_id:
            query = query.eq("workspace_id", workspace_id)
        elif user_id:
            query = query.eq("user_id", user_id)
        res = query.execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch call logs: {_friendly_supabase_error('Fetch call logs', e)}")
        return []


def _safe_ilike_phone_fragment(raw: str) -> str:
    """Strip PostgREST ilike wildcards from user input (we add *…* ourselves)."""
    return re.sub(r"[*%]", "", (raw or "").strip())[:80]


def fetch_call_logs_v2(
    *,
    limit: int = 25,
    offset: int = 0,
    user_id: str | None = None,
    access_token: str | None = None,
    workspace_id: str | None = None,
    created_at_gte: str | None = None,
    created_at_lte: str | None = None,
    status: str | None = None,
    agent_id: str | None = None,
    phone_search: str | None = None,
    failed_only: bool = False,
    transferred_only: bool = False,
    disposition: str | None = None,
) -> Dict[str, Any]:
    """Paginated call logs with optional filters. Uses user JWT + RLS unless workspace_id + service path."""
    eff_limit = max(1, min(int(limit or 25), 100))
    off = max(0, int(offset or 0))
    prefer_service = bool(workspace_id)
    sb = get_supabase(access_token=None if prefer_service else access_token, service_role=prefer_service)
    if not sb:
        return {"items": [], "limit": eff_limit, "offset": off, "has_more": False}
    try:
        query = sb.table("call_logs").select("*")
        if workspace_id:
            query = query.eq("workspace_id", workspace_id)
        elif user_id:
            query = query.eq("user_id", user_id)

        if created_at_gte:
            query = query.gte("created_at", created_at_gte.strip())
        if created_at_lte:
            query = query.lte("created_at", created_at_lte.strip())

        st = (status or "").strip()
        if st:
            query = query.eq("status", st)

        aid = (agent_id or "").strip()
        if aid:
            query = query.eq("agent_id", aid)

        phone_frag = _safe_ilike_phone_fragment(phone_search or "")
        if phone_frag:
            query = query.or_(f"phone.ilike.*{phone_frag}*,phone_number.ilike.*{phone_frag}*")

        if failed_only:
            # Status failed (SIP / worker) OR a non-empty failure_reason on the row.
            query = query.or_("status.eq.failed,and(failure_reason.not.is.null,failure_reason.neq.)")

        if transferred_only:
            query = query.or_("summary.ilike.*xfer=ok*,summary.ilike.*xfer=requested*")

        disp = (disposition or "").strip().lower()
        if disp and re.match(r"^[a-z0-9_]+$", disp):
            query = query.or_(f"manual_disposition.eq.{disp},summary.ilike.*disp={disp}*")

        upper = off + eff_limit
        res = query.order("created_at", desc=True).range(off, upper).execute()
        rows = list(res.data or [])
        has_more = len(rows) > eff_limit
        items = rows[:eff_limit]
        return {"items": items, "limit": eff_limit, "offset": off, "has_more": has_more}
    except Exception as e:
        logger.error(f"Failed to fetch call logs v2: {_friendly_supabase_error('Fetch call logs', e)}")
        return {"items": [], "limit": eff_limit, "offset": off, "has_more": False}


def fetch_stats(
    user_id: str | None = None,
    access_token: str | None = None,
    workspace_id: str | None = None,
) -> Dict[str, Any]:
    logs = fetch_call_logs(limit=1000, user_id=user_id, access_token=access_token, workspace_id=workspace_id)
    if not logs:
        return {
            "total_calls": 0,
            "answered_calls": 0,
            "failed_calls": 0,
            "total_bookings": 0,
            "avg_duration": 0,
            "average_duration": 0,
            "total_minutes": 0,
            "estimated_ai_cost": 0,
            "booking_rate": 0,
        }

    total_calls = len(logs)
    answered_calls = sum(1 for r in logs if (r.get("status") in ("answered", "completed") or int(r.get("duration") or 0) > 0))
    failed_calls = sum(1 for r in logs if r.get("status") == "failed")
    total_bookings = sum(1 for r in logs if bool(r.get("was_booked")))
    total_duration = sum(int(r.get("duration") or 0) for r in logs)
    avg_duration = round(total_duration / total_calls, 2)
    total_minutes = round(total_duration / 60, 2)
    estimated_ai_cost = round(sum(float(r.get("estimated_cost_usd") or 0) for r in logs), 4)
    booking_rate = round((total_bookings / total_calls) * 100, 2)
    return {
        "total_calls": total_calls,
        "answered_calls": answered_calls,
        "failed_calls": failed_calls,
        "total_bookings": total_bookings,
        "avg_duration": avg_duration,
        "average_duration": avg_duration,
        "total_minutes": total_minutes,
        "estimated_ai_cost": estimated_ai_cost,
        "booking_rate": booking_rate,
    }


def fetch_contacts(
    user_id: str | None = None,
    access_token: str | None = None,
    workspace_id: str | None = None,
) -> List[Dict[str, Any]]:
    if workspace_id:
        sb = get_supabase(service_role=True)
        if sb:
            try:
                res = (
                    sb.table("contacts")
                    .select("id,full_name,phone_e164,tags,source,created_at")
                    .eq("workspace_id", workspace_id)
                    .order("created_at", desc=True)
                    .limit(500)
                    .execute()
                )
                tbl = res.data or []
                if tbl:
                    return tbl
            except Exception as e:
                logger.info(f"contacts table unreadable, using rollup: {e}")
        sb = get_supabase(service_role=True)
    else:
        sb = get_supabase(access_token=access_token)
    if not sb:
        return []
    try:
        query = (
            sb.table("call_logs")
            .select("phone, caller_name, summary, created_at")
            .order("created_at", desc=True)
            .limit(500)
        )
        if workspace_id:
            query = query.eq("workspace_id", workspace_id)
        elif user_id:
            query = query.eq("user_id", user_id)
        res = query.execute()
        rows = res.data or []
        contacts: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            phone = row.get("phone") or "unknown"
            if phone not in contacts:
                contacts[phone] = {
                    "phone": phone,
                    "caller_name": row.get("caller_name") or "",
                    "total_calls": 0,
                    "last_seen": row.get("created_at"),
                    "is_booked": False,
                }
            contact = contacts[phone]
            contact["total_calls"] += 1
            if not contact["caller_name"] and row.get("caller_name"):
                contact["caller_name"] = row["caller_name"]
            if row.get("summary") and "Confirmed" in row.get("summary", ""):
                contact["is_booked"] = True
        return sorted(contacts.values(), key=lambda x: x["last_seen"] or "", reverse=True)
    except Exception as e:
        logger.error(f"Failed to fetch contacts: {_friendly_supabase_error('Fetch contacts', e)}")
        return []


def _agent_version_payload(data: Dict[str, Any], agent_id: str, version_number: int, user_id: str | None, status: str = "draft") -> Dict[str, Any]:
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    llm_config = _merge_json(DEFAULT_LLM_CONFIG, data.get("llm_config") or config.get("llm_config"))
    audio_config = _merge_json(DEFAULT_AUDIO_CONFIG, data.get("audio_config") or config.get("audio_config"))
    engine_config = _merge_json(DEFAULT_ENGINE_CONFIG, data.get("engine_config") or config.get("engine_config"))
    call_config = _merge_json(DEFAULT_CALL_CONFIG, data.get("call_config") or config.get("call_config"))
    default_language = data.get("default_language") or data.get("language_profile") or engine_config.get("language_profile")
    if default_language:
        engine_config["language_profile"] = default_language

    return {
        "agent_id": agent_id,
        "version": int(version_number),
        "status": status,
        "welcome_message": (
            data.get("welcome_message")
            or data.get("first_line")
            or config.get("welcomeMessage")
            or config.get("first_line")
            or DEFAULT_WELCOME_MESSAGE
        ),
        "system_prompt": (
            data.get("system_prompt")
            or data.get("prompt")
            or config.get("prompt")
            or config.get("agent_instructions")
            or DEFAULT_SYSTEM_PROMPT
        ),
        "multilingual_prompts": _merge_json(
            DEFAULT_MULTILINGUAL_PROMPTS,
            data.get("multilingual_prompts") or config.get("multilingual_prompts"),
        ),
        "prompt_variables": _as_list(
            data.get("prompt_variables") or config.get("prompt_variables"),
            DEFAULT_PROMPT_VARIABLES,
        ),
        "llm_config": llm_config,
        "audio_config": audio_config,
        "engine_config": engine_config,
        "call_config": call_config,
        "tools_config": data.get("tools_config") if isinstance(data.get("tools_config"), list) else [],
        "analytics_config": _merge_json(
            DEFAULT_ANALYTICS_CONFIG,
            data.get("analytics_config") or config.get("analytics_config"),
        ),
        "created_by": user_id,
    }


def _legacy_agent_config(agent: Dict[str, Any], version: Dict[str, Any] | None = None) -> Dict[str, Any]:
    existing = agent.get("config") if isinstance(agent.get("config"), dict) else {}
    version = version or {}
    llm_config = version.get("llm_config") if isinstance(version.get("llm_config"), dict) else {}
    audio_config = version.get("audio_config") if isinstance(version.get("audio_config"), dict) else {}
    engine_config = version.get("engine_config") if isinstance(version.get("engine_config"), dict) else {}
    return {
        **existing,
        "name": agent.get("name"),
        "phone": existing.get("phone") or agent.get("phone") or "",
        "welcomeMessage": version.get("welcome_message") or existing.get("welcomeMessage") or DEFAULT_WELCOME_MESSAGE,
        "first_line": version.get("welcome_message") or existing.get("first_line") or DEFAULT_WELCOME_MESSAGE,
        "prompt": version.get("system_prompt") or existing.get("prompt") or DEFAULT_SYSTEM_PROMPT,
        "agent_instructions": version.get("system_prompt") or existing.get("agent_instructions") or DEFAULT_SYSTEM_PROMPT,
        "llm_provider": llm_config.get("provider"),
        "llm_model": llm_config.get("model"),
        "tts_provider": audio_config.get("tts_provider"),
        "tts_model": audio_config.get("tts_model"),
        "tts_voice": audio_config.get("tts_voice"),
        "tts_language": audio_config.get("tts_language"),
        "stt_provider": audio_config.get("stt_provider"),
        "stt_model": audio_config.get("stt_model"),
        "lang_preset": engine_config.get("language_profile") or agent.get("default_language"),
    }


def _voice_pipeline_for_runtime(agent: Dict[str, Any], engine_config: Dict[str, Any]) -> str:
    existing = agent.get("config") if isinstance(agent.get("config"), dict) else {}
    value = (
        existing.get("voice_pipeline")
        or engine_config.get("voice_pipeline")
        or os.getenv("VOICE_PIPELINE")
        or "livekit_agents"
    )
    value = str(value or "").strip()
    return value if value in {"livekit_agents", "pipecat"} else "livekit_agents"


def _build_agent_runtime_config(agent: Dict[str, Any], version: Dict[str, Any]) -> Dict[str, Any]:
    llm_config = _merge_json(DEFAULT_LLM_CONFIG, version.get("llm_config"))
    audio_config = _merge_json(DEFAULT_AUDIO_CONFIG, version.get("audio_config"))
    engine_config = _merge_json(DEFAULT_ENGINE_CONFIG, version.get("engine_config"))
    call_config = _merge_json(DEFAULT_CALL_CONFIG, version.get("call_config"))
    analytics_config = _merge_json(
        DEFAULT_ANALYTICS_CONFIG,
        version.get("analytics_config") if isinstance(version.get("analytics_config"), dict) else {},
    )
    lc_base = DEFAULT_ENGINE_CONFIG.get("language_config") if isinstance(DEFAULT_ENGINE_CONFIG.get("language_config"), dict) else {}
    lc_override = engine_config.get("language_config") if isinstance(engine_config.get("language_config"), dict) else {}
    merged_language_config = {**lc_base, **lc_override}
    first_line = str(version.get("welcome_message") or "").strip() or FALLBACK_FIRST_LINE
    agent_instructions = str(version.get("system_prompt") or "").strip() or DEFAULT_SYSTEM_PROMPT
    voice_pipeline = _voice_pipeline_for_runtime(agent, engine_config)
    runtime_config = {
        "agent_id": agent.get("id"),
        "agent_version_id": version.get("id"),
        "agent_name": agent.get("name"),
        "first_line": first_line,
        "welcome_message": first_line,
        "welcomeMessage": first_line,
        "agent_instructions": agent_instructions,
        "system_prompt": agent_instructions,
        "prompt": agent_instructions,
        "multilingual_prompts": version.get("multilingual_prompts") or DEFAULT_MULTILINGUAL_PROMPTS,
        "prompt_variables": version.get("prompt_variables") or DEFAULT_PROMPT_VARIABLES,
        "llm_provider": llm_config.get("provider"),
        "llm_model": llm_config.get("model"),
        "llm_temperature": llm_config.get("temperature"),
        "llm_max_tokens": llm_config.get("max_tokens"),
        "llm_fallback_providers": llm_config.get("fallback_providers") or [],
        "tts_provider": audio_config.get("tts_provider"),
        "tts_model": audio_config.get("tts_model"),
        "tts_voice": audio_config.get("tts_voice"),
        "tts_language": audio_config.get("tts_language"),
        "stt_provider": audio_config.get("stt_provider"),
        "stt_model": audio_config.get("stt_model"),
        "stt_language": audio_config.get("stt_language"),
        "noise_suppression": audio_config.get("noise_suppression"),
        "voice_pipeline": voice_pipeline,
        "lang_preset": engine_config.get("language_profile") or agent.get("default_language") or "multilingual",
        "stt_min_endpointing_delay": engine_config.get("stt_min_endpointing_delay"),
        "max_turns": engine_config.get("max_turns"),
        "silence_timeout_seconds": engine_config.get("silence_timeout_seconds"),
        "interruption_words": engine_config.get("interruption_words") or [],
        "response_latency_mode": engine_config.get("response_latency_mode") or "normal",
        "vertical": (engine_config.get("vertical") or "").strip(),
        "language_config": merged_language_config,
        "llm_config": llm_config,
        "audio_config": audio_config,
        "engine_config": {**engine_config, "voice_pipeline": voice_pipeline},
        "call_config": call_config,
        "tools_config": version.get("tools_config") or [],
        "analytics_config": analytics_config,
    }
    existing = agent.get("config") if isinstance(agent.get("config"), dict) else {}
    for key in ("phone", "inbound_number_id", "inbound_assign_enabled"):
        if key in existing and key not in runtime_config:
            runtime_config[key] = existing.get(key)
    return runtime_config


def _validate_publishable_runtime_config(version: Dict[str, Any], runtime_config: Dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(version.get("welcome_message") or "").strip():
        missing.append("welcome_message")
    if not str(version.get("system_prompt") or "").strip():
        missing.append("agent_prompt")
    if not str(runtime_config.get("tts_provider") or "").strip() or not str(runtime_config.get("stt_provider") or "").strip():
        missing.append("voice config")
    if not str(runtime_config.get("llm_provider") or "").strip() or not str(runtime_config.get("voice_pipeline") or "").strip():
        missing.append("pipeline config")
    return missing


def _normalize_agent(agent: Dict[str, Any], active_version: Dict[str, Any] | None = None, versions: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    row = dict(agent)
    if active_version:
        row["active_version"] = active_version
        row["active_version_id"] = active_version.get("id")
    if active_version and active_version.get("status") == "published":
        row["published_agent_uuid"] = row.get("published_agent_uuid") or row.get("id")
    else:
        row["published_agent_uuid"] = None
    if versions is not None:
        row["versions"] = versions
    row["config"] = _legacy_agent_config(row, active_version)
    return row


def _fetch_agent_version(sb: Client, agent_id: str, version_id: str | None = None) -> Dict[str, Any] | None:
    try:
        query = sb.table("agent_versions").select("*").eq("agent_id", agent_id)
        if version_id:
            query = query.eq("id", version_id)
        else:
            query = query.order("published_at", desc=True).order("version", desc=True).limit(1)
        res = query.limit(1).execute()
        return (res.data or [None])[0]
    except Exception as e:
        logger.error(f"Failed to fetch agent version: {_friendly_supabase_error('Fetch agent version', e)}")
        return None


def _fetch_agent_versions(sb: Client, agent_id: str) -> List[Dict[str, Any]]:
    try:
        res = sb.table("agent_versions").select("*").eq("agent_id", agent_id).order("version", desc=False).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch agent versions: {_friendly_supabase_error('Fetch agent versions', e)}")
        return []


def _fetch_active_agent_version(sb: Client, agent: Dict[str, Any]) -> Dict[str, Any] | None:
    active_version_id = agent.get("active_version_id")
    if active_version_id:
        active = _fetch_agent_version(sb, agent.get("id"), active_version_id)
        if active:
            return active
    versions = _fetch_agent_versions(sb, agent.get("id"))
    published = [row for row in versions if row.get("status") == "published"]
    return (published or versions or [None])[-1]


def _audit_agent_event(workspace_id: str | None, user_id: str | None, action: str, agent_id: str | None = None, payload: Dict[str, Any] | None = None) -> None:
    if not workspace_id:
        return
    sb = get_supabase(service_role=True)
    if not sb:
        return
    try:
        sb.table("audit_logs").insert(
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "action": action,
                "entity_type": "agent",
                "entity_id": agent_id,
                "payload": payload or {},
            }
        ).execute()
    except Exception as e:
        logger.debug(f"Audit log skipped: {_friendly_supabase_error('Insert audit log', e)}")


def fetch_agents(workspace_id: str | None = None, access_token: str | None = None) -> List[Dict[str, Any]]:
    sb = get_supabase(service_role=True if workspace_id else False, access_token=access_token if not workspace_id else None)
    if not sb:
        return []
    try:
        query = sb.table("agents").select("*").order("created_at", desc=True).limit(100)
        if workspace_id:
            query = query.eq("workspace_id", workspace_id)
        res = query.execute()
        rows = [row for row in (res.data or []) if row.get("status") != "deleted"]
        return [_normalize_agent(row, _fetch_active_agent_version(sb, row)) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch agents: {_friendly_supabase_error('Fetch agents', e)}")
        return []


def get_agent(agent_id: str, workspace_id: str | None = None, include_versions: bool = False) -> Dict[str, Any] | None:
    sb = get_supabase(service_role=True)
    if not sb:
        return None
    try:
        query = sb.table("agents").select("*").eq("id", agent_id).limit(1)
        if workspace_id:
            query = query.eq("workspace_id", workspace_id)
        res = query.execute()
        agent = (res.data or [None])[0]
        if not agent or agent.get("status") == "deleted":
            return None
        versions = _fetch_agent_versions(sb, agent_id) if include_versions else None
        active_version = _fetch_active_agent_version(sb, agent)
        return _normalize_agent(agent, active_version, versions)
    except Exception as e:
        logger.error(f"Failed to get agent: {_friendly_supabase_error('Get agent', e)}")
        return None


def create_agent(workspace_id: str, user_id: str | None, data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("[AGENT_SAVE_REQUEST] create workspace_id=%s user_id=%s", workspace_id, user_id)
    if not workspace_id:
        return {"success": False, "message": "workspace_id required"}
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        data_use = dict(data)
        tmpl = str(data_use.get("template") or "").strip().lower().replace("-", "_")
        if tmpl == "tamil_real_estate":
            seed = _tamil_real_estate_template_seed()
            data_use["engine_config"] = _merge_json(seed.get("engine_config") or {}, data_use.get("engine_config"))
            data_use["audio_config"] = _merge_json(DEFAULT_AUDIO_CONFIG, seed.get("audio_config"))
            data_use["audio_config"] = _merge_json(data_use["audio_config"], data.get("audio_config"))
            data_use["multilingual_prompts"] = _merge_json(seed.get("multilingual_prompts") or {}, data_use.get("multilingual_prompts"))
            if not str(data_use.get("welcome_message") or data_use.get("first_line") or "").strip():
                data_use["welcome_message"] = seed.get("welcome_message")
            if not str(data_use.get("system_prompt") or data_use.get("prompt") or "").strip():
                data_use["system_prompt"] = seed.get("system_prompt")
            data_use.setdefault("default_language", seed.get("default_language"))
        name = (data_use.get("name") or "Voice Agent").strip()
        agent_payload = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "created_by": user_id,
            "name": name,
            "description": data_use.get("description") or "",
            "status": data_use.get("status") or "draft",
            "visibility": data_use.get("visibility") or "private",
            "default_language": data_use.get("default_language") or data_use.get("language_profile") or "multilingual",
            "config": data_use.get("config") if isinstance(data_use.get("config"), dict) else {},
        }
        ast = str(data_use.get("agent_state") or "active").strip().lower()
        if ast:
            agent_payload["agent_state"] = ast if ast in {"active", "paused", "inactive"} else "active"
        try:
            agent_res = sb.table("agents").insert(agent_payload).execute()
        except Exception as e:
            if "agent_state" in agent_payload and _missing_schema_column(e, "agent_state"):
                logger.warning("[AGENT_SAVE_REQUEST] agent_state column missing; retrying create without agent_state")
                agent_payload.pop("agent_state", None)
                agent_res = sb.table("agents").insert(agent_payload).execute()
            else:
                raise
        agent = (agent_res.data or [{}])[0]
        agent_id = agent.get("id")
        if not agent_id:
            return {"success": False, "message": "Agent insert returned no id"}
        version_payload = _agent_version_payload(data_use, agent_id, 1, user_id, status=data_use.get("version_status") or "draft")
        version_res = sb.table("agent_versions").insert(version_payload).execute()
        version = (version_res.data or [{}])[0]
        update_payload = {
            "active_version_id": version.get("id"),
            "config": _legacy_agent_config(agent, version),
            "updated_at": _now_iso(),
        }
        sb.table("agents").update(update_payload).eq("id", agent_id).execute()
        agent.update(update_payload)
        _audit_agent_event(workspace_id, user_id, "agent.created", agent_id, {"name": name})
        logger.info("[AGENT_SAVE_SUCCESS] create agent_id=%s version_id=%s", agent_id, version.get("id"))
        return {"success": True, "agent": _normalize_agent(agent, version, [version])}
    except Exception as e:
        message = _friendly_supabase_error("Create agent", e)
        logger.error(f"Failed to create agent: {message}")
        return {"success": False, "message": message}


def update_agent(agent_id: str, workspace_id: str, user_id: str | None, data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("[AGENT_SAVE_REQUEST] update agent_id=%s workspace_id=%s user_id=%s", agent_id, workspace_id, user_id)
    allowed = {"name", "description", "status", "visibility", "default_language", "config", "agent_state"}
    payload = _clean_dict({k: v for k, v in data.items() if k in allowed})
    if not payload:
        agent = get_agent(agent_id, workspace_id, include_versions=True)
        return {"success": bool(agent), "agent": agent, "message": "" if agent else "Agent not found"}
    payload["updated_at"] = _now_iso()
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        existing = get_agent(agent_id, workspace_id)
        if not existing:
            return {"success": False, "message": "Agent not found"}
        try:
            sb.table("agents").update(payload).eq("id", agent_id).eq("workspace_id", workspace_id).execute()
        except Exception as e:
            if "agent_state" in payload and _missing_schema_column(e, "agent_state"):
                logger.warning("[AGENT_SAVE_REQUEST] agent_state column missing; retrying update without agent_state")
                payload.pop("agent_state", None)
                sb.table("agents").update(payload).eq("id", agent_id).eq("workspace_id", workspace_id).execute()
            else:
                raise
        _audit_agent_event(workspace_id, user_id, "agent.updated", agent_id, payload)
        logger.info("[AGENT_SAVE_SUCCESS] update agent_id=%s", agent_id)
        return {"success": True, "agent": get_agent(agent_id, workspace_id, include_versions=True)}
    except Exception as e:
        message = _friendly_supabase_error("Update agent", e)
        logger.error(f"Failed to update agent: {message}")
        return {"success": False, "message": message}


def delete_agent(agent_id: str, workspace_id: str, user_id: str | None) -> Dict[str, Any]:
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        existing = get_agent(agent_id, workspace_id)
        if not existing:
            return {"success": False, "message": "Agent not found"}
        sb.table("agents").update({"status": "deleted", "deleted_at": _now_iso(), "updated_at": _now_iso()}).eq("id", agent_id).eq("workspace_id", workspace_id).execute()
        _audit_agent_event(workspace_id, user_id, "agent.deleted", agent_id)
        return {"success": True}
    except Exception as e:
        message = _friendly_supabase_error("Delete agent", e)
        logger.error(f"Failed to delete agent: {message}")
        return {"success": False, "message": message}


def create_agent_version(agent_id: str, workspace_id: str, user_id: str | None, data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("[AGENT_SAVE_REQUEST] create_version agent_id=%s workspace_id=%s user_id=%s", agent_id, workspace_id, user_id)
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        agent = get_agent(agent_id, workspace_id)
        if not agent:
            return {"success": False, "message": "Agent not found"}
        versions = _fetch_agent_versions(sb, agent_id)
        next_version = max([int(v.get("version") or 0) for v in versions] or [0]) + 1
        base = dict(agent.get("active_version") or {})
        merged = {**base, **_clean_dict(data)}
        payload = _agent_version_payload(merged, agent_id, next_version, user_id, status="draft")
        version_res = sb.table("agent_versions").insert(payload).execute()
        version = (version_res.data or [{}])[0]
        agent_update = {
            "active_version_id": version.get("id"),
            "status": "draft",
            "config": _legacy_agent_config(agent, version),
            "updated_at": _now_iso(),
        }
        try:
            sb.table("agents").update({**agent_update, "published_agent_uuid": None}).eq("id", agent_id).eq("workspace_id", workspace_id).execute()
        except Exception:
            sb.table("agents").update(agent_update).eq("id", agent_id).eq("workspace_id", workspace_id).execute()
        _audit_agent_event(workspace_id, user_id, "agent_version.created", agent_id, {"version": next_version})
        logger.info("[AGENT_VERSION_CREATED] agent_id=%s version_id=%s version=%s", agent_id, version.get("id"), next_version)
        logger.info("[AGENT_SAVE_SUCCESS] create_version agent_id=%s version_id=%s", agent_id, version.get("id"))
        return {"success": True, "version": version}
    except Exception as e:
        message = _friendly_supabase_error("Create agent version", e)
        logger.error(f"Failed to create agent version: {message}")
        return {"success": False, "message": message}


def update_agent_version(agent_id: str, version_id: str, workspace_id: str, user_id: str | None, data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("[AGENT_SAVE_REQUEST] update_version agent_id=%s version_id=%s workspace_id=%s user_id=%s", agent_id, version_id, workspace_id, user_id)
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        agent = get_agent(agent_id, workspace_id)
        if not agent:
            return {"success": False, "message": "Agent not found"}
        version = _fetch_agent_version(sb, agent_id, version_id)
        if not version:
            return {"success": False, "message": "Agent version not found"}
        if version.get("status") == "published":
            return {"success": False, "message": "Published agent versions are immutable. Create a new draft version first."}
        allowed = {
            "welcome_message",
            "system_prompt",
            "multilingual_prompts",
            "prompt_variables",
            "llm_config",
            "audio_config",
            "engine_config",
            "call_config",
            "tools_config",
            "analytics_config",
            "status",
        }
        payload = _clean_dict({k: v for k, v in data.items() if k in allowed})
        if not payload:
            return {"success": True, "version": version}
        for key, defaults in (
            ("llm_config", DEFAULT_LLM_CONFIG),
            ("audio_config", DEFAULT_AUDIO_CONFIG),
            ("engine_config", DEFAULT_ENGINE_CONFIG),
            ("call_config", DEFAULT_CALL_CONFIG),
            ("analytics_config", DEFAULT_ANALYTICS_CONFIG),
            ("multilingual_prompts", DEFAULT_MULTILINGUAL_PROMPTS),
        ):
            if key in payload:
                payload[key] = _merge_json(version.get(key) or defaults, payload[key])
        payload["updated_at"] = _now_iso()
        res = sb.table("agent_versions").update(payload).eq("id", version_id).eq("agent_id", agent_id).execute()
        updated = (res.data or [None])[0] or {**version, **payload}
        if agent.get("active_version_id") == version_id:
            sb.table("agents").update({"config": _legacy_agent_config(agent, updated), "updated_at": _now_iso()}).eq("id", agent_id).execute()
        _audit_agent_event(workspace_id, user_id, "agent_version.updated", agent_id, {"version_id": version_id})
        logger.info("[AGENT_SAVE_SUCCESS] update_version agent_id=%s version_id=%s", agent_id, version_id)
        return {"success": True, "version": updated}
    except Exception as e:
        message = _friendly_supabase_error("Update agent version", e)
        logger.error(f"Failed to update agent version: {message}")
        return {"success": False, "message": message}


def publish_agent_version(agent_id: str, version_id: str, workspace_id: str, user_id: str | None) -> Dict[str, Any]:
    logger.info("[AGENT_PUBLISH_REQUEST] agent_id=%s version_id=%s workspace_id=%s user_id=%s", agent_id, version_id, workspace_id, user_id)
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        agent = get_agent(agent_id, workspace_id)
        if not agent:
            return {"success": False, "message": "Agent not found"}
        version = _fetch_agent_version(sb, agent_id, version_id)
        if not version:
            return {"success": False, "message": "Agent version not found"}
        runtime_config = _build_agent_runtime_config(agent, version)
        missing = _validate_publishable_runtime_config(version, runtime_config)
        if missing:
            return {
                "success": False,
                "message": "Publish validation failed. Missing: " + ", ".join(missing),
                "missing": missing,
            }
        sb.table("agent_versions").update({"status": "archived", "updated_at": _now_iso()}).eq("agent_id", agent_id).eq("status", "published").neq("id", version_id).execute()
        publish_payload = {"status": "published", "published_at": _now_iso(), "updated_at": _now_iso()}
        res = sb.table("agent_versions").update(publish_payload).eq("id", version_id).eq("agent_id", agent_id).execute()
        published = (res.data or [None])[0] or {**version, **publish_payload}
        runtime_config = _build_agent_runtime_config(agent, published)
        agent_update = {
            "active_version_id": version_id,
            "status": "active",
            "config": runtime_config,
            "updated_at": _now_iso(),
        }
        published_uuid = agent_id
        try:
            sb.table("agents").update({**agent_update, "published_agent_uuid": published_uuid}).eq("id", agent_id).eq("workspace_id", workspace_id).execute()
        except Exception:
            sb.table("agents").update(agent_update).eq("id", agent_id).eq("workspace_id", workspace_id).execute()
        _audit_agent_event(workspace_id, user_id, "agent_version.published", agent_id, {"version_id": version_id})
        agent_row = get_agent(agent_id, workspace_id, include_versions=True)
        logger.info("[PUBLISHED_AGENT_UUID_CREATED] agent_id=%s published_agent_uuid=%s version_id=%s", agent_id, published_uuid, version_id)
        logger.info(
            "[AGENT_PUBLISH_SUCCESS] agent_id=%s version_id=%s status=published first_line=%s voice_pipeline=%s stt_provider=%s tts_provider=%s llm_provider=%s",
            agent_id,
            version_id,
            runtime_config.get("first_line"),
            runtime_config.get("voice_pipeline"),
            runtime_config.get("stt_provider"),
            runtime_config.get("tts_provider"),
            runtime_config.get("llm_provider"),
        )
        return {"success": True, "agent": agent_row, "version": published, "published_agent_uuid": published_uuid}
    except Exception as e:
        message = _friendly_supabase_error("Publish agent version", e)
        logger.error(f"Failed to publish agent version: {message}")
        return {"success": False, "message": message}


def unpublish_active_agent(agent_id: str, workspace_id: str, user_id: str | None) -> Dict[str, Any]:
    """Move active published version back to draft so dispatch resolution fails until re-published."""
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    agent = get_agent(agent_id, workspace_id)
    if not agent:
        return {"success": False, "message": "Agent not found"}
    vid = agent.get("active_version_id")
    if not vid:
        return {"success": False, "message": "No active version"}
    ver = _fetch_agent_version(sb, agent_id, str(vid))
    if not ver or ver.get("status") != "published":
        return {"success": False, "message": "Active version is not published"}
    try:
        sb.table("agent_versions").update(
            {"status": "draft", "published_at": None, "updated_at": _now_iso()}
        ).eq("id", str(vid)).eq("agent_id", agent_id).execute()
        sb.table("agents").update({"status": "draft", "updated_at": _now_iso()}).eq("id", agent_id).eq("workspace_id", workspace_id).execute()
        _audit_agent_event(workspace_id, user_id, "agent_version.unpublished", agent_id, {"version_id": str(vid)})
        return {"success": True, "agent": get_agent(agent_id, workspace_id, include_versions=True)}
    except Exception as e:
        msg = _friendly_supabase_error("Unpublish agent", e)
        return {"success": False, "message": msg}


def duplicate_agent(agent_id: str, workspace_id: str, user_id: str | None) -> Dict[str, Any]:
    source = get_agent(agent_id, workspace_id, include_versions=True)
    if not source:
        return {"success": False, "message": "Agent not found"}
    data = {
        "name": f"{source.get('name') or 'Voice Agent'} Copy",
        "description": source.get("description") or "",
        "visibility": "private",
        "default_language": source.get("default_language") or "multilingual",
    }
    created = create_agent(workspace_id, user_id, {**data, **(source.get("active_version") or {})})
    if created.get("success"):
        _audit_agent_event(workspace_id, user_id, "agent.duplicated", created["agent"].get("id"), {"source_agent_id": agent_id})
    return created


def export_agent(agent_id: str, workspace_id: str) -> Dict[str, Any]:
    agent = get_agent(agent_id, workspace_id, include_versions=True)
    if not agent:
        return {"success": False, "message": "Agent not found"}
    portable_agent = {
        "name": agent.get("name"),
        "description": agent.get("description") or "",
        "status": agent.get("status") or "draft",
        "visibility": agent.get("visibility") or "private",
        "default_language": agent.get("default_language") or "multilingual",
    }
    portable_versions = []
    for version in agent.get("versions") or []:
        portable_versions.append(
            {
                "version": version.get("version"),
                "status": version.get("status"),
                "welcome_message": version.get("welcome_message"),
                "system_prompt": version.get("system_prompt"),
                "multilingual_prompts": version.get("multilingual_prompts") or {},
                "prompt_variables": version.get("prompt_variables") or [],
                "llm_config": version.get("llm_config") or {},
                "audio_config": version.get("audio_config") or {},
                "engine_config": version.get("engine_config") or {},
                "call_config": version.get("call_config") or {},
                "tools_config": version.get("tools_config") or [],
                "analytics_config": version.get("analytics_config") or {},
                "published_at": version.get("published_at"),
            }
        )
    return {
        "success": True,
        "export": {
            "schema_version": 1,
            "exported_at": _now_iso(),
            "agent": portable_agent,
            "versions": portable_versions,
        },
    }


def import_agent(workspace_id: str, user_id: str | None, export_data: Dict[str, Any]) -> Dict[str, Any]:
    agent_data = export_data.get("agent") if isinstance(export_data.get("agent"), dict) else {}
    versions = export_data.get("versions") if isinstance(export_data.get("versions"), list) else []
    first_version = versions[0] if versions and isinstance(versions[0], dict) else {}
    created = create_agent(workspace_id, user_id, {**agent_data, **first_version})
    if not created.get("success"):
        return created
    agent_id = created["agent"].get("id")
    sb = get_supabase(service_role=True)
    if sb and agent_id and len(versions) > 1:
        try:
            for index, version in enumerate(versions[1:], start=2):
                if isinstance(version, dict):
                    payload = _agent_version_payload(version, agent_id, index, user_id, status=version.get("status") or "draft")
                    sb.table("agent_versions").insert(payload).execute()
        except Exception as e:
            logger.warning(f"Partial agent import: {_friendly_supabase_error('Import agent versions', e)}")
    _audit_agent_event(workspace_id, user_id, "agent.imported", agent_id)
    return {"success": True, "agent": get_agent(agent_id, workspace_id, include_versions=True)}


def resolve_agent_runtime_config(agent_id: str, workspace_id: str | None = None) -> Dict[str, Any]:
    agent = get_agent(agent_id, workspace_id, include_versions=True)
    if not agent:
        return {"success": False, "message": "Agent not found"}
    if agent.get("status") == "deleted":
        return {"success": False, "message": "Agent is deleted"}
    state = str(agent.get("agent_state") or agent.get("state") or "active").lower()
    if state in {"paused", "inactive"}:
        return {"success": False, "message": "Agent is paused and cannot be used for calls until re-activated."}
    version = agent.get("active_version") or {}
    if not version:
        return {"success": False, "message": "Agent has no version"}
    if version.get("status") != "published" and (os.getenv("ALLOW_DRAFT_AGENT_CALLS", "").lower() not in {"1", "true", "yes"}):
        return {"success": False, "message": "Agent has no published version. Publish a version before using it for calls."}
    runtime_config = _build_agent_runtime_config(agent, version)
    return {
        "success": True,
        "agent_id": agent.get("id"),
        "agent_version_id": version.get("id"),
        "agent_name": agent.get("name"),
        "version_status": version.get("status"),
        "config": runtime_config,
    }


def record_provider_usage_event(
    workspace_id: str | None,
    user_id: str | None,
    agent_id: str | None,
    agent_version_id: str | None,
    call_log_id: Any = None,
    provider_type: str = "",
    provider_name: str = "",
    model: str = "",
    metric: str = "estimated_cost_usd",
    quantity: float = 0.0,
    estimated_cost_usd: float = 0.0,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        payload = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "call_log_id": call_log_id,
            "provider_type": provider_type,
            "provider_name": provider_name,
            "model": model,
            "metric": metric,
            "quantity": quantity,
            "estimated_cost_usd": estimated_cost_usd,
            "metadata": metadata or {},
        }
        sb.table("provider_usage_events").insert(payload).execute()
        return {"success": True}
    except Exception as e:
        message = _friendly_supabase_error("Record provider usage", e)
        logger.debug(f"Provider usage event skipped: {message}")
        return {"success": False, "message": message}


def fetch_usage(workspace_id: str | None = None, access_token: str | None = None) -> List[Dict[str, Any]]:
    prefer_sr = bool(workspace_id)
    sb = get_supabase(access_token=None if prefer_sr else access_token, service_role=prefer_sr)
    if not sb:
        return []
    try:
        q = sb.table("usage_events").select("*").order("created_at", desc=True).limit(500)
        if workspace_id and hasattr(q, "eq"):
            try:
                q = q.eq("workspace_id", workspace_id)
            except Exception:
                pass
        res = q.execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch usage: {_friendly_supabase_error('Fetch usage', e)}")
        return []


def fetch_call_log_detail(call_log_id: Any, workspace_id: str) -> Dict[str, Any] | None:
    if not workspace_id:
        return None
    sb = get_supabase(service_role=True)
    if not sb:
        return None
    try:
        res = sb.table("call_logs").select("*").eq("id", call_log_id).eq("workspace_id", workspace_id).limit(1).execute()
        return (res.data or [None])[0]
    except Exception as e:
        logger.warning(f"fetch_call_log_detail: {e}")
        return None


def set_manual_disposition(call_log_id: Any, workspace_id: str, user_id: str | None, disposition: str) -> Dict[str, Any]:
    allowed = {"interested", "not_interested", "follow_up", "transferred", "failed", "unknown"}
    d = (disposition or "").strip().lower()
    if d not in allowed:
        return {"success": False, "message": f"Disposition must be one of: {sorted(allowed)}"}
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    row = fetch_call_log_detail(call_log_id, workspace_id)
    if not row:
        return {"success": False, "message": "Call log not found"}
    try:
        sb.table("call_logs").update(
            {"manual_disposition": d, "manual_disposition_at": _now_iso()}
        ).eq("id", call_log_id).eq("workspace_id", workspace_id).execute()
        _audit_workspace_event(workspace_id, user_id, "call.disposition_set", entity_type="call_log", entity_id=str(call_log_id))
        return {"success": True, "call_log_id": call_log_id, "manual_disposition": d}
    except Exception as e:
        return {"success": False, "message": _friendly_supabase_error("Disposition update", e)}


def normalize_phone_to_e164(phone: str, default_region: str = "IN") -> str | None:
    raw = (phone or "").strip()
    if not raw:
        return None
    try:
        import phonenumbers  # type: ignore

        try:
            p = phonenumbers.parse(raw, default_region.upper() if default_region else None)
        except Exception:
            p = phonenumbers.parse(raw, None)
        if not phonenumbers.is_valid_number(p):
            digits = re.sub(r"\D+", "", raw)
            if len(digits) >= 11 and digits.startswith("91"):
                p2 = phonenumbers.parse(f"+{digits}", None)
                if phonenumbers.is_valid_number(p2):
                    return phonenumbers.format_number(p2, phonenumbers.PhoneNumberFormat.E164)
            return None
        return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        digits = re.sub(r"\D+", "", raw)
        if not digits:
            return None
        if digits.startswith("0") and len(digits) >= 11:
            digits = digits.lstrip("0")
        if not digits.startswith("91") and len(digits) == 10:
            digits = "91" + digits
        if digits.startswith("91") and len(digits) >= 12:
            return f"+{digits}"
        return f"+{digits}" if digits else None


def import_contacts_csv(workspace_id: str, lines: List[str]) -> Dict[str, Any]:
    if not workspace_id:
        return {"success": False, "message": "workspace_id required"}
    region = (os.getenv("DEFAULT_PHONE_REGION") or "IN").strip()
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    created = 0
    skipped = 0
    errors: List[str] = []
    rows_out: List[Dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            parts = next(csv.reader([line]))
        except Exception:
            parts = []
        parts = [(p or "").strip() for p in parts]
        parts = [p for p in parts if p != ""]
        if len(parts) < 1:
            continue
        phone_raw = parts[0]
        full_name = parts[1] if len(parts) > 1 else ""
        e164 = normalize_phone_to_e164(phone_raw, region)
        if not e164:
            skipped += 1
            errors.append(f"Bad phone: {phone_raw}")
            continue
        try:
            ex = sb.table("contacts").select("id").eq("workspace_id", workspace_id).eq("phone_e164", e164).limit(1).execute()
            existing_id = ((ex.data or [{}])[0] or {}).get("id") if ex.data else None
            if existing_id:
                sb.table("contacts").update({"full_name": full_name or ""}).eq("id", existing_id).execute()
            else:
                sb.table("contacts").insert(
                    {
                        "workspace_id": workspace_id,
                        "phone_e164": e164,
                        "full_name": full_name or "",
                        "tags": [],
                        "source": "csv_import",
                    }
                ).execute()
            created += 1
        except Exception as e:
            skipped += 1
            errors.append(_friendly_supabase_error("contact upsert", e))
    _audit_workspace_event(workspace_id, None, "contact.import", payload={"created": created, "skipped": skipped})
    return {"success": True, "created": created, "skipped": skipped, "errors": errors[:20], "rows": rows_out}


def fetch_campaigns(workspace_id: str | None = None, access_token: str | None = None) -> List[Dict[str, Any]]:
    prefer_sr = bool(workspace_id)
    sb = get_supabase(access_token=None if prefer_sr else access_token, service_role=prefer_sr)
    if not sb:
        return []
    try:
        q = sb.table("campaigns").select("*").order("created_at", desc=True).limit(100)
        if workspace_id:
            q = q.eq("workspace_id", workspace_id)
        res = q.execute()
        return res.data or []
    except Exception as e:
        logger.info(f"Campaigns table unavailable or empty: {_friendly_supabase_error('Fetch campaigns', e)}")
        return []


def create_campaign_record(
    workspace_id: str, user_id: str | None, name: str, agent_id: str | None = None
) -> Dict[str, Any]:
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    payload = {"workspace_id": workspace_id, "name": name.strip() or "Campaign", "agent_id": agent_id, "status": "draft"}
    try:
        res = sb.table("campaigns").insert(payload).execute()
        cid = ((res.data or [{}])[0] or {}).get("id")
        _audit_workspace_event(workspace_id, user_id, "campaign.created", payload={"campaign_id": cid})
        return {"success": True, "campaign": (res.data or [{}])[0]}
    except Exception as e:
        return {"success": False, "message": _friendly_supabase_error("Create campaign", e)}


def update_campaign_workspace(
    campaign_id: str, workspace_id: str, user_id: str | None, fields: Dict[str, Any]
) -> Dict[str, Any]:
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    payload = _clean_dict({k: fields.get(k) for k in fields if fields.get(k) is not None})
    if not payload:
        return {"success": False, "message": "No fields"}
    payload["updated_at"] = _now_iso()
    try:
        sb.table("campaigns").update(payload).eq("id", campaign_id).eq("workspace_id", workspace_id).execute()
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": _friendly_supabase_error("Update campaign", e)}


def seed_campaign_rows_from_workspace_contacts(campaign_id: str, workspace_id: str, limit: int = 500) -> Dict[str, Any]:
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        contacts = sb.table("contacts").select("id,phone_e164").eq("workspace_id", workspace_id).limit(limit).execute()
        rows_built = 0
        for row in contacts.data or []:
            pid = row.get("phone_e164")
            cid = row.get("id")
            if not pid:
                continue
            sb.table("campaign_contacts").upsert(
                {
                    "campaign_id": campaign_id,
                    "contact_id": cid,
                    "phone_e164": pid,
                    "status": "queued",
                },
                on_conflict="campaign_id,phone_e164",
            ).execute()
            rows_built += 1
        return {"success": True, "rows": rows_built}
    except Exception as e:
        return {"success": False, "message": _friendly_supabase_error("Campaign seed", e)}


def list_campaign_contact_queue(campaign_id: str, workspace_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    sb = get_supabase(service_role=True)
    if not sb:
        return []
    camp = sb.table("campaigns").select("id").eq("id", campaign_id).eq("workspace_id", workspace_id).limit(1).execute()
    if not camp.data:
        return []
    try:
        q = sb.table("campaign_contacts").select("*").eq("campaign_id", campaign_id).eq("status", "queued").limit(limit)
        res = q.execute()
        return res.data or []
    except Exception as e:
        logger.warning(str(e))
        return []


def mark_campaign_started(campaign_id: str, workspace_id: str) -> None:
    sb = get_supabase(service_role=True)
    if not sb:
        return
    sb.table("campaigns").update(
        {"status": "running", "started_at": _now_iso(), "stopped_at": None, "updated_at": _now_iso()}
    ).eq("id", campaign_id).eq("workspace_id", workspace_id).execute()


def mark_campaign_stopped(campaign_id: str, workspace_id: str) -> None:
    sb = get_supabase(service_role=True)
    if not sb:
        return
    sb.table("campaigns").update({"status": "stopped", "stopped_at": _now_iso(), "updated_at": _now_iso()}).eq(
        "id", campaign_id
    ).eq("workspace_id", workspace_id).execute()


def plan_row(plan_id: str | None) -> Dict[str, Any]:
    pid = plan_id or "free"
    sb = get_supabase(service_role=True)
    defaults = {"id": "free", "label": "Free", "included_minutes": 60.0, "max_contacts": 500, "max_campaigns": 2}
    if not sb:
        return defaults
    try:
        res = sb.table("plans").select("*").eq("id", pid).limit(1).execute()
        row = (res.data or [{}])[0] or defaults
        return row
    except Exception:
        return defaults


def workspace_plan_bundle(workspace_id: str | None) -> Dict[str, Any]:
    if not workspace_id:
        return plan_row(None)
    sb = get_supabase(service_role=True)
    plan_id = "free"
    if sb:
        try:
            ws = sb.table("workspace_settings").select("plan_id").eq("workspace_id", workspace_id).limit(1).execute()
            pid = ((ws.data or [{}])[0] or {}).get("plan_id")
            if pid:
                plan_id = str(pid)
        except Exception:
            pass
    return plan_row(plan_id)


def monthly_usage_aggregate(workspace_id: str) -> Dict[str, Any]:
    """Minutes + contact/campaign counts (service_role). Month = UTC calendar month."""
    sb = get_supabase(service_role=True)
    since = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if not sb:
        return {"minutes_used": 0.0, "contacts": 0, "campaigns_active": 0}
    mins = 0.0
    try:
        res = sb.table("call_logs").select("duration").gte("created_at", since.isoformat()).eq(
            "workspace_id", workspace_id
        ).limit(5000).execute()
        for row in res.data or []:
            mins += float(row.get("duration") or 0) / 60.0
    except Exception as e:
        logger.warning(f"monthly_usage_aggregate logs: {e}")
    contacts = 0
    campaigns = 0
    try:
        cts = sb.table("contacts").select("id").eq("workspace_id", workspace_id).limit(20000).execute()
        contacts = len(cts.data or [])
        cps = (
            sb.table("campaigns").select("id").eq("workspace_id", workspace_id).eq("status", "running").limit(500).execute()
        )
        campaigns = len(cps.data or [])
    except Exception:
        pass
    return {"minutes_used": round(mins, 2), "contacts": contacts, "campaigns_active": campaigns}


def soft_limit_blocked(workspace_id: str, action: str) -> Dict[str, Any]:
    enforce = os.getenv("ENFORCE_SOFT_LIMITS", "").lower() in {"1", "true", "yes"}
    plan = workspace_plan_bundle(workspace_id)
    if not enforce:
        return {"blocked": False, "enforce": False}
    use = monthly_usage_aggregate(workspace_id)
    inc_min = float(plan.get("included_minutes") or 0)
    mc = plan.get("max_contacts")
    mcp = plan.get("max_campaigns")
    if action in {"dispatch_campaign", "outbound_manual"}:
        pass
    if action == "contact_import":
        if isinstance(mc, (int, float)) and mc > 0 and use["contacts"] >= int(mc):
            return {"blocked": True, "code": "limit_contacts", "plan": plan, "usage": use}
        return {"blocked": False, "enforce": True}
    if action == "campaign_start":
        if isinstance(mcp, (int, float)) and mcp > 0 and use["campaigns_active"] >= int(mcp):
            return {"blocked": True, "code": "limit_campaigns", "plan": plan, "usage": use}
        return {"blocked": False, "enforce": True}
    if action in {"dispatch", "campaign_dial_batch"}:
        if inc_min > 0 and use["minutes_used"] > inc_min * 1.05:
            return {"blocked": True, "code": "limit_minutes", "plan": plan, "usage": use}
    return {"blocked": False, "enforce": True}


def platform_aggregate_metrics(ops_user_ids: set[str]) -> Dict[str, Any]:
    sb = get_supabase(service_role=True)
    out: Dict[str, Any] = {"workspaces": 0, "call_logs_recent": 0, "profiles": 0, "provider_usage_rows": 0}
    if not sb:
        return out
    try:
        ws = sb.table("workspaces").select("id").limit(5000).execute()
        out["workspaces"] = len(ws.data or [])
    except Exception:
        pass
    try:
        cl = sb.table("call_logs").select("id").limit(1000).execute()
        out["call_logs_recent"] = len(cl.data or [])
    except Exception:
        pass
    try:
        pr = sb.table("profiles").select("id").limit(5000).execute()
        out["profiles"] = len(pr.data or [])
    except Exception:
        pass
    try:
        pu = sb.table("provider_usage_events").select("estimated_cost_usd").limit(2000).execute()
        rows = pu.data or []
        out["provider_usage_rows"] = len(rows)
        out["provider_usage_estimate_usd"] = round(sum(float(r.get("estimated_cost_usd") or 0) for r in rows), 4)
    except Exception:
        out["provider_usage_estimate_usd"] = 0
    # auth user count omitted (requires Admin API); use profiles as proxy when available.
    _ = ops_user_ids
    return out


def fetch_billing_summary(
    access_token: str | None = None, workspace_id: str | None = None
) -> Dict[str, Any]:
    stats = fetch_stats(access_token=access_token, workspace_id=workspace_id)
    used_minutes_hist = float(stats.get("total_minutes") or 0)
    plan = workspace_plan_bundle(workspace_id) if workspace_id else plan_row(None)
    monthly = monthly_usage_aggregate(workspace_id) if workspace_id else {}
    planned_minutes = float(plan.get("included_minutes") or os.getenv("BILLING_INCLUDED_MINUTES", "250") or 250)
    used_minutes = float(monthly.get("minutes_used") or used_minutes_hist)
    estimated_cost = float(stats.get("estimated_ai_cost") or 0)
    included_minutes = int(planned_minutes) if planned_minutes else int(os.getenv("BILLING_INCLUDED_MINUTES", "250") or 250)
    overage_rate = float(os.getenv("BILLING_OVERAGE_RATE_USD", "0.18") or 0.18)
    base_price = float(os.getenv("BILLING_BASE_PRICE_USD", "49") or 49)
    overage_minutes = max(0.0, used_minutes - included_minutes)
    return {
        "plan": plan.get("label") or plan.get("id") or os.getenv("BILLING_PLAN_NAME", "Launch"),
        "plan_id": plan.get("id"),
        "status": os.getenv("BILLING_STATUS", "trial"),
        "included_minutes": included_minutes,
        "used_minutes": round(used_minutes, 2),
        "minutes_used_calendar_month": round(float(monthly.get("minutes_used") or 0), 2),
        "overage_minutes": round(overage_minutes, 2),
        "estimated_ai_cost": round(estimated_cost, 4),
        "next_invoice_estimate": round(base_price + (overage_minutes * overage_rate), 2),
        "soft_limits_enabled": os.getenv("ENFORCE_SOFT_LIMITS", "").lower() in {"1", "true", "yes"},
        "max_contacts": plan.get("max_contacts"),
        "max_campaigns": plan.get("max_campaigns"),
        "usage_snapshot": monthly,
    }


def auth_sign_up(email: str, password: str) -> Dict[str, Any]:
    sb = get_supabase()
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        res = sb.auth.sign_up({"email": email, "password": password})
        user = getattr(res, "user", None)
        session = getattr(res, "session", None)
        return {
            "success": True,
            "user_id": getattr(user, "id", None),
            "email": getattr(user, "email", email),
            "session": session is not None,
        }
    except Exception as e:
        message = _friendly_supabase_error("Sign up", e)
        logger.error(f"Sign up failed: {message}")
        return {"success": False, "message": message}


def auth_sign_in(email: str, password: str) -> Dict[str, Any]:
    sb = get_supabase()
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        user = getattr(res, "user", None)
        session = getattr(res, "session", None)
        return {
            "success": True,
            "user_id": getattr(user, "id", None),
            "email": getattr(user, "email", email),
            "access_token": getattr(session, "access_token", None),
            "refresh_token": getattr(session, "refresh_token", None),
        }
    except Exception as e:
        message = _friendly_supabase_error("Sign in", e)
        logger.error(f"Sign in failed: {message}")
        return {"success": False, "message": message}


def auth_send_email_otp(email: str) -> Dict[str, Any]:
    sb = get_supabase()
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        sb.auth.sign_in_with_otp({"email": email})
        return {"success": True, "message": "OTP sent if the email is allowed by Supabase auth settings"}
    except Exception as e:
        message = _friendly_supabase_error("Send email OTP", e)
        logger.error(f"Send email OTP failed: {message}")
        return {"success": False, "message": message}


def auth_verify_email_otp(email: str, token: str, otp_type: str = "email") -> Dict[str, Any]:
    sb = get_supabase()
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        res = sb.auth.verify_otp({"email": email, "token": token, "type": otp_type})
        user = getattr(res, "user", None)
        session = getattr(res, "session", None)
        return {
            "success": True,
            "user_id": getattr(user, "id", None),
            "email": getattr(user, "email", email),
            "access_token": getattr(session, "access_token", None),
            "refresh_token": getattr(session, "refresh_token", None),
        }
    except Exception as e:
        message = _friendly_supabase_error("Verify email OTP", e)
        logger.error(f"Verify email OTP failed: {message}")
        return {"success": False, "message": message}


def auth_reset_password(email: str) -> Dict[str, Any]:
    sb = get_supabase()
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        sb.auth.reset_password_for_email(email)
        return {"success": True}
    except Exception as e:
        message = _friendly_supabase_error("Reset password", e)
        logger.error(f"Reset password failed: {message}")
        return {"success": False, "message": message}


def auth_get_user(access_token: str) -> Dict[str, Any]:
    sb = get_supabase()
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    try:
        user_res = sb.auth.get_user(access_token)
        user = getattr(user_res, "user", None)
        app_metadata = getattr(user, "app_metadata", {}) or {}
        roles = app_metadata.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]
        return {
            "success": True,
            "user_id": getattr(user, "id", None),
            "email": getattr(user, "email", None),
            "role": app_metadata.get("role", "user"),
            "roles": roles,
            "app_metadata": app_metadata,
        }
    except Exception as e:
        message = _friendly_supabase_error("Get user", e)
        logger.error(f"Get user failed: {message}")
        return {"success": False, "message": message}
