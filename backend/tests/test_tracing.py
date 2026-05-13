import asyncio
import importlib
import logging

from fastapi.testclient import TestClient

import backend.agent as agent_module
from backend import main


def _reload_tracing(monkeypatch):
    import backend.tracing as tracing

    return importlib.reload(tracing)


def test_tracing_disabled_when_env_missing(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    tracing = _reload_tracing(monkeypatch)

    assert tracing.langsmith_enabled() is False
    assert tracing.configure_langsmith_env() is False


def test_langsmith_key_normalized_from_malformed_railway_value(monkeypatch):
    token = "v2_pt_abcdefghijklmnopqrstuvwxyz123456"
    monkeypatch.setenv("LANGCHAIN_API_KEY", f"LANGCHAIN_API_KEY\n{token}\n")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    tracing = _reload_tracing(monkeypatch)

    assert tracing.configure_langsmith_env() is True
    assert tracing.langsmith_enabled() is True
    assert "\n" not in tracing.os.environ["LANGCHAIN_API_KEY"]
    assert tracing.os.environ["LANGCHAIN_API_KEY"] == token
    assert tracing.os.environ["LANGSMITH_API_KEY"] == token


def test_langsmith_key_rejects_non_token_value(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_API_KEY", "LANGCHAIN_API_KEY")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    tracing = _reload_tracing(monkeypatch)

    assert tracing.langsmith_enabled() is False
    assert tracing.configure_langsmith_env() is False


def test_phone_masking_works(monkeypatch):
    tracing = _reload_tracing(monkeypatch)

    assert tracing.mask_phone_number("+919500049469") == "+9195****9469"
    assert tracing.mask_phone_number("919500049469") == "9195****9469"
    assert tracing.sanitize_for_trace({"phone": "+919500049469"}) == {"phone": "+9195****9469"}


def test_trace_wrapper_does_not_crash(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    tracing = _reload_tracing(monkeypatch)

    @tracing.traceable(name="unit_trace")
    def wrapped(value):
        return value + 1

    assert wrapped(1) == 2
    tracing.trace_event("unit_event", phone="+919500049469", api_key="secret")


def test_tts_blocked_event_logs_safely(monkeypatch, caplog):
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    tracing = _reload_tracing(monkeypatch)

    caplog.set_level(logging.INFO, logger="outbound-agent.langsmith")
    tracing.log_tts_filter_blocked(
        source="unit",
        text="call +919500049469 with token secret",
        reason="no_speakable_text",
    )

    logs = caplog.text
    assert "[TRACE] tts_filter_blocked" in logs
    assert "+919500049469" not in logs
    assert "secret" not in logs


def test_sip_480_classifies_as_provider_temporarily_unavailable():
    err = (
        "TwirpError(code=resource_exhausted, message=twirp error unknown: "
        "INVITE failed: sip status: 480: Temporarily Unavailable, status=429, "
        "metadata={'sip_status': 'Temporarily Unavailable', 'sip_status_code': '480'})"
    )

    classified = main.db.classify_sip_failure(err)

    assert classified == {
        "sip_status": "480",
        "normalized_reason": "provider_temporarily_unavailable",
    }
    assert main._sip_failure_reason(Exception(err)) == "provider_temporarily_unavailable"


def test_sip_480_failure_does_not_enable_safe_mode(monkeypatch):
    monkeypatch.setattr(main, "_SAFE_MODE_ENABLED", False)

    reason = main._sip_failure_reason(
        Exception("TwirpError: INVITE failed: sip status: 480: Temporarily Unavailable")
    )
    health = main.health_check()

    assert reason == "provider_temporarily_unavailable"
    assert main._SAFE_MODE_ENABLED is False
    assert health["safe_mode"] is False


def test_sip_480_retry_is_capped_to_one_when_enabled(monkeypatch):
    captured = {}
    monkeypatch.setenv("CALL_RETRY_ENABLED", "true")
    monkeypatch.delenv("DISABLE_CALL_RETRY_SCHEDULER", raising=False)
    monkeypatch.setattr(main.db, "update_call_log", lambda call_id, **fields: captured.update(fields) or {"success": True})

    main.db.mark_call_failed(
        "call-1",
        "provider_temporarily_unavailable",
        retry_count=0,
        max_retries=3,
    )

    assert captured["status"] == "retry_scheduled"
    assert captured["failure_reason"] == "provider_temporarily_unavailable"
    assert captured["max_retries"] == 1
    assert captured["next_retry_at"]


def test_sip_480_retry_is_not_infinite_after_one_attempt(monkeypatch):
    captured = {}
    monkeypatch.setenv("CALL_RETRY_ENABLED", "true")
    monkeypatch.delenv("DISABLE_CALL_RETRY_SCHEDULER", raising=False)
    monkeypatch.setattr(main.db, "update_call_log", lambda call_id, **fields: captured.update(fields) or {"success": True})

    main.db.mark_call_failed(
        "call-1",
        "provider_temporarily_unavailable",
        retry_count=1,
        max_retries=3,
    )

    assert captured["status"] == "failed"
    assert captured["max_retries"] == 1
    assert captured["next_retry_at"] is None


def test_connected_call_with_tts_audio_has_no_silence_flag(monkeypatch):
    updates = []
    monkeypatch.setattr(main.db, "update_call_quality_fields", lambda call_id, **fields: updates.append(fields) or {"success": True})

    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr(agent_module.asyncio, "sleep", fast_sleep)

    async def run():
        diag = agent_module.ConnectedCallDiagnostics(
            call_id="call-1",
            room_name="room-1",
            destination="+15555550100",
            trunk_id="trunk-1",
            tts_provider="sarvam",
        )
        diag.mark_connected()
        diag.mark_tts_audio_sent(128, text_preview="Hello there")
        await diag._watch_for_silent_connected_call()
        return diag

    diag = asyncio.run(run())

    assert diag.silence_detected is False
    assert not any(update.get("silence_detected") is True for update in updates)


def test_connected_call_without_tts_sets_silence_flag(monkeypatch, caplog):
    updates = []
    monkeypatch.setattr(main.db, "update_call_quality_fields", lambda call_id, **fields: updates.append(fields) or {"success": True})

    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr(agent_module.asyncio, "sleep", fast_sleep)
    caplog.set_level(logging.WARNING, logger="outbound-agent")

    async def run():
        diag = agent_module.ConnectedCallDiagnostics(
            call_id="call-2",
            room_name="room-2",
            destination="+15555550101",
            trunk_id="trunk-1",
            tts_provider="sarvam",
        )
        diag.mark_connected()
        await diag._watch_for_silent_connected_call()
        return diag

    diag = asyncio.run(run())

    assert diag.silence_detected is True
    assert diag.audio_issue_reason == "no_tts_audio_within_5s"
    assert "[SILENT_CONNECTED_CALL] call_id=call-2 reason=no_tts_audio_within_5s" in caplog.text
    assert any(update.get("silence_detected") is True for update in updates)


def test_user_audio_without_stt_logs_stt_stall(monkeypatch, caplog):
    updates = []
    monkeypatch.setattr(main.db, "update_call_quality_fields", lambda call_id, **fields: updates.append(fields) or {"success": True})

    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr(agent_module.asyncio, "sleep", fast_sleep)
    caplog.set_level(logging.WARNING, logger="outbound-agent")

    async def run():
        diag = agent_module.ConnectedCallDiagnostics(
            call_id="call-3",
            room_name="room-3",
            destination="+15555550102",
            trunk_id="trunk-1",
            tts_provider="sarvam",
        )
        diag.mark_user_audio_detected()
        await diag._watch_for_stt_stall()
        return diag

    diag = asyncio.run(run())

    assert diag.audio_issue_reason == "stt_stall"
    assert "[STT_STALL] call_id=call-3" in caplog.text
    assert any(update.get("audio_issue_reason") == "stt_stall" for update in updates)


def test_call_debug_timeline_requires_auth():
    client = TestClient(main.app)

    response = client.get("/api/calls/123/debug-timeline")

    assert response.status_code == 401
