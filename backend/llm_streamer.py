"""LLM factory for the slower layer of the realtime voice pipeline."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

from livekit.agents import (
    APIConnectOptions,
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    NotGivenOr,
    llm,
)
from livekit.plugins import openai
from backend.tracing import log_langsmith_status_once, trace_event

logger = logging.getLogger("outbound-agent.llm_streamer")
log_langsmith_status_once()

GROQ_COOLDOWN_SECONDS = 60
_groq_cooldown_until = 0.0


def openai_fallback_enabled() -> bool:
    return str(os.getenv("OPENAI_FALLBACK_ENABLED") or "").strip().lower() == "true"


def mark_groq_rate_limited(*, seconds: int = GROQ_COOLDOWN_SECONDS) -> float:
    global _groq_cooldown_until
    _groq_cooldown_until = max(_groq_cooldown_until, time.time() + max(1, int(seconds)))
    return _groq_cooldown_until


def groq_cooldown_remaining() -> int:
    return max(0, int(_groq_cooldown_until - time.time()))


def groq_cooldown_active() -> bool:
    return groq_cooldown_remaining() > 0


def _is_rate_limit_error(error: BaseException) -> bool:
    status_code = int(getattr(error, "status_code", 0) or 0)
    if status_code == 429:
        return True
    response = getattr(error, "response", None)
    response_status = int(getattr(response, "status_code", 0) or 0)
    if response_status == 429:
        return True
    text = str(error).lower()
    return "429" in text or "rate limit" in text or "quota" in text


class FallbackLLMStream(llm.LLMStream):
    def __init__(
        self,
        owner: "Groq429FallbackLLM",
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        conn_options: APIConnectOptions,
        parallel_tool_calls: Any,
        tool_choice: Any,
        extra_kwargs: Any,
    ) -> None:
        super().__init__(owner, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        self._owner = owner
        self._parallel_tool_calls = parallel_tool_calls
        self._tool_choice = tool_choice
        self._extra_kwargs = extra_kwargs

    async def _forward(self, stream: llm.LLMStream) -> None:
        async with stream:
            async for chunk in stream:
                if chunk.usage is not None:
                    logger.info(
                        "[GROQ_QUOTA_USED] provider=%s model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s cached_tokens=%s",
                        self._owner.active_provider,
                        self._owner.active_model,
                        chunk.usage.prompt_tokens,
                        chunk.usage.completion_tokens,
                        chunk.usage.total_tokens,
                        chunk.usage.prompt_cached_tokens,
                    )
                    trace_event(
                        "groq_response",
                        provider=self._owner.active_provider,
                        model=self._owner.active_model,
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                    )
                self._event_ch.send_nowait(chunk)

    def _send_local_reply(self, text: str) -> None:
        self._event_ch.send_nowait(
            llm.ChatChunk(
                id=f"local-groq-cooldown-{uuid.uuid4().hex[:12]}",
                delta=llm.ChoiceDelta(role="assistant", content=text),
            )
        )

    async def _run(self) -> None:
        if groq_cooldown_active():
            remaining = groq_cooldown_remaining()
            logger.warning("[GROQ_COOLDOWN_ACTIVE] remaining_seconds=%s source=llm_stream", remaining)
            logger.info("[LOCAL_REPLY_USED] reason=groq_cooldown source=llm_stream")
            self._send_local_reply("Sorry sir, system busy. Please repeat shortly.")
            return

        self._owner.active_provider = "groq"
        self._owner.active_model = self._owner.primary_model
        trace_event(
            "llm_call_start",
            provider="groq",
            model=self._owner.primary_model,
            tool_count=len(self._tools or []),
        )
        primary_conn = APIConnectOptions(
            max_retry=0,
            retry_interval=self._conn_options.retry_interval,
            timeout=self._conn_options.timeout,
        )
        try:
            await self._forward(
                self._owner.primary.chat(
                    chat_ctx=self._chat_ctx,
                    tools=self._tools,
                    conn_options=primary_conn,
                    parallel_tool_calls=self._parallel_tool_calls,
                    tool_choice=self._tool_choice,
                    extra_kwargs=self._extra_kwargs,
                )
            )
            return
        except Exception as e:
            if not _is_rate_limit_error(e):
                raise
            cooldown_until = mark_groq_rate_limited()
            logger.warning(
                "[GROQ_RATE_LIMIT] provider=groq model=%s status_code=429 request_id=%s cooldown_seconds=%s cooldown_until=%s",
                self._owner.primary_model,
                getattr(e, "request_id", "") or "",
                GROQ_COOLDOWN_SECONDS,
                int(cooldown_until),
            )
            logger.warning(
                "[LLM_RATE_LIMIT] provider=groq model=%s status_code=429 request_id=%s",
                self._owner.primary_model,
                getattr(e, "request_id", "") or "",
            )
            logger.info("[LOCAL_REPLY_USED] reason=groq_rate_limit source=llm_stream")
            self._send_local_reply("Sorry sir, system busy. Please repeat shortly.")
            return


class Groq429FallbackLLM(llm.LLM):
    def __init__(self, *, primary: Any, fallback: Any | None, primary_model: str, fallback_model: str) -> None:
        super().__init__()
        self.primary = primary
        self.fallback = fallback
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.active_provider = "groq"
        self.active_model = primary_model

    @property
    def model(self) -> str:
        return self.primary_model

    @property
    def provider(self) -> str:
        return "groq-quota-managed"

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> llm.LLMStream:
        return FallbackLLMStream(
            self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        )

    async def aclose(self) -> None:
        close_primary = getattr(self.primary, "aclose", None)
        if callable(close_primary):
            await close_primary()
        close_fallback = getattr(self.fallback, "aclose", None)
        if callable(close_fallback):
            await close_fallback()


def build_voice_llm(
    *,
    provider: str,
    model: str,
    max_completion_tokens: int,
    temperature: float,
    fallback_provider: str | None = None,
    fallback_model: str | None = None,
) -> Any:
    provider_l = (provider or "groq").lower()
    if provider_l == "groq":
        primary = openai.LLM(
            model=model or "llama-3.1-8b-instant",
            base_url=os.getenv("GROQ_OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=os.getenv("GROQ_API_KEY", ""),
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            max_retries=0,
        )
        fallback = None
        fallback_provider_l = (fallback_provider or "").lower()
        fallback_model_resolved = fallback_model or "gpt-4o-mini"
        if fallback_provider_l == "openai" and openai_fallback_enabled() and os.getenv("OPENAI_API_KEY", "").strip():
            fallback = openai.LLM(
                model=fallback_model_resolved,
                max_completion_tokens=max_completion_tokens,
                temperature=temperature,
                max_retries=0,
            )
            logger.info(
                "[LLM] Using Groq model=%s with OpenAI fallback enabled model=%s",
                model or "llama-3.1-8b-instant",
                fallback_model_resolved,
            )
            return Groq429FallbackLLM(
                primary=primary,
                fallback=fallback,
                primary_model=model or "llama-3.1-8b-instant",
                fallback_model=fallback_model_resolved,
            )
        logger.info("[LLM] Using Groq streaming-compatible OpenAI API model=%s", model or "llama-3.1-8b-instant")
        return Groq429FallbackLLM(
            primary=primary,
            fallback=None,
            primary_model=model or "llama-3.1-8b-instant",
            fallback_model=fallback_model_resolved,
        )
    if provider_l == "claude":
        llm = openai.LLM(
            model=model or "claude-haiku-3-5-latest",
            base_url="https://api.anthropic.com/v1/",
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
        )
        logger.info("[LLM] Using Claude via OpenAI-compatible API model=%s", model or "claude-haiku-3-5-latest")
        return llm
    if provider_l == "gemini":
        llm = openai.LLM(
            model=model or "gemini-2.0-flash",
            base_url=os.getenv("GEMINI_OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
            api_key=os.getenv("GEMINI_API_KEY", ""),
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
        )
        logger.info("[LLM] Using Gemini via OpenAI-compatible API model=%s", model or "gemini-2.0-flash")
        return llm
    llm = openai.LLM(model=model, max_completion_tokens=max_completion_tokens, temperature=temperature, max_retries=0)
    logger.info("[LLM] Using OpenAI streaming-compatible model=%s", model)
    return llm
