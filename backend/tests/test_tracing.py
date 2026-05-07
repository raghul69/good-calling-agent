import importlib
import logging


def _reload_tracing(monkeypatch):
    import backend.tracing as tracing

    return importlib.reload(tracing)


def test_tracing_disabled_when_env_missing(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
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
