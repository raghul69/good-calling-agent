"""LLM factory for the slower layer of the realtime voice pipeline."""

from __future__ import annotations

import logging
import os
from typing import Any

from livekit.plugins import openai

logger = logging.getLogger("outbound-agent.llm_streamer")


def build_voice_llm(
    *,
    provider: str,
    model: str,
    max_completion_tokens: int,
    temperature: float,
) -> Any:
    provider_l = (provider or "openai").lower()
    if provider_l == "groq":
        llm = openai.LLM(
            model=model or "llama-3.1-8b-instant",
            base_url=os.getenv("GROQ_OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=os.getenv("GROQ_API_KEY", ""),
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
        )
        logger.info("[LLM] Using Groq streaming-compatible OpenAI API model=%s", model or "llama-3.1-8b-instant")
        return llm
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
    llm = openai.LLM(model=model, max_completion_tokens=max_completion_tokens, temperature=temperature)
    logger.info("[LLM] Using OpenAI streaming-compatible model=%s", model)
    return llm
