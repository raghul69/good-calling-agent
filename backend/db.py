import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

from supabase import Client, create_client

logger = logging.getLogger("backend-db")

RETRYABLE_CALL_FAILURES = {"no_answer", "busy", "sip_failure", "timeout"}
MAX_CALL_RETRIES = int(os.getenv("MAX_CALL_RETRIES", "3") or 3)
CALL_RETRY_DELAY_SECONDS = int(os.getenv("CALL_RETRY_DELAY_SECONDS", "300") or 300)


def _supabase_settings(service_role: bool = False) -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip()
    anon_key = (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    key = service_key if service_role and service_key else anon_key or service_key
    return url, key


def _friendly_supabase_error(action: str, error: Exception) -> str:
    url, _key = _supabase_settings()
    host = urlparse(url).netloc or "unknown"
    message = str(error)
    if "[Errno 11001]" in message or "getaddrinfo failed" in message:
        return (
            f"{action} failed: DNS lookup failed for Supabase host '{host}'. "
            "Check SUPABASE_URL, internet/DNS access, and Render environment variables."
        )
    return message


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


def get_supabase(access_token: str | None = None, service_role: bool = False) -> Client | None:
    url, key = _supabase_settings(service_role=service_role)
    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_KEY not set.")
        return None
    if not get_supabase_config_status()["url_valid"]:
        logger.error("SUPABASE_URL is invalid. Expected https://<project-ref>.supabase.co")
        return None
    try:
        client = create_client(url, key)
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
        role = next(
            (row.get("role") for row in member_rows if row.get("user_id") == user.get("user_id")),
            user.get("role") or "member",
        )
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
) -> Dict[str, Any]:
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
    }
    if owner_user_id:
        payload["user_id"] = owner_user_id
    if workspace_id:
        payload["workspace_id"] = workspace_id
    try:
        res = sb.table("call_logs").insert(payload).execute()
        row = (res.data or [{}])[0]
        return {"success": True, "id": row.get("id")}
    except Exception as e:
        message = _friendly_supabase_error("Save call log", e)
        logger.error(f"Failed to save call log: {message}")
        return {"success": False, "message": message}


def update_call_log(call_id: Any, **fields: Any) -> Dict[str, Any]:
    if not call_id:
        return {"success": False, "message": "call_id required"}
    sb = get_supabase(service_role=True)
    if not sb:
        return {"success": False, "message": "Supabase not configured"}
    clean = dict(fields)
    if not clean:
        return {"success": True}
    try:
        sb.table("call_logs").update(clean).eq("id", call_id).execute()
        return {"success": True}
    except Exception as e:
        message = _friendly_supabase_error("Update call log", e)
        logger.error(f"Failed to update call log {call_id}: {message}")
        return {"success": False, "message": message}


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


def fetch_call_logs(limit: int = 50, user_id: str | None = None, access_token: str | None = None) -> List[Dict[str, Any]]:
    sb = get_supabase(access_token=access_token)
    if not sb:
        return []
    try:
        query = (
            sb.table("call_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        # Prefer RLS-only filtering (workspace + legacy user_id). Optional narrow for older DBs without SaaS migration.
        if user_id:
            query = query.eq("user_id", user_id)
        res = query.execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch call logs: {_friendly_supabase_error('Fetch call logs', e)}")
        return []


def fetch_stats(user_id: str | None = None, access_token: str | None = None) -> Dict[str, Any]:
    logs = fetch_call_logs(limit=1000, user_id=user_id, access_token=access_token)
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


def fetch_contacts(user_id: str | None = None, access_token: str | None = None) -> List[Dict[str, Any]]:
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
        if user_id:
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


def fetch_agents(access_token: str | None = None) -> List[Dict[str, Any]]:
    sb = get_supabase(access_token=access_token)
    if not sb:
        return []
    try:
        res = sb.table("agents").select("*").order("created_at", desc=True).limit(100).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch agents: {_friendly_supabase_error('Fetch agents', e)}")
        return []


def fetch_usage(access_token: str | None = None) -> List[Dict[str, Any]]:
    sb = get_supabase(access_token=access_token)
    if not sb:
        return []
    try:
        res = sb.table("usage_events").select("*").order("created_at", desc=True).limit(500).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch usage: {_friendly_supabase_error('Fetch usage', e)}")
        return []


def fetch_campaigns(access_token: str | None = None) -> List[Dict[str, Any]]:
    sb = get_supabase(access_token=access_token)
    if not sb:
        return []
    try:
        res = sb.table("campaigns").select("*").order("created_at", desc=True).limit(100).execute()
        return res.data or []
    except Exception as e:
        logger.info(f"Campaigns table unavailable or empty: {_friendly_supabase_error('Fetch campaigns', e)}")
        return []


def fetch_billing_summary(access_token: str | None = None) -> Dict[str, Any]:
    stats = fetch_stats(access_token=access_token)
    used_minutes = float(stats.get("total_minutes") or 0)
    estimated_cost = float(stats.get("estimated_ai_cost") or 0)
    included_minutes = int(os.getenv("BILLING_INCLUDED_MINUTES", "250") or 250)
    overage_rate = float(os.getenv("BILLING_OVERAGE_RATE_USD", "0.18") or 0.18)
    base_price = float(os.getenv("BILLING_BASE_PRICE_USD", "49") or 49)
    overage_minutes = max(0.0, used_minutes - included_minutes)
    return {
        "plan": os.getenv("BILLING_PLAN_NAME", "Launch"),
        "status": os.getenv("BILLING_STATUS", "trial"),
        "included_minutes": included_minutes,
        "used_minutes": round(used_minutes, 2),
        "overage_minutes": round(overage_minutes, 2),
        "estimated_ai_cost": round(estimated_cost, 4),
        "next_invoice_estimate": round(base_price + (overage_minutes * overage_rate), 2),
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
