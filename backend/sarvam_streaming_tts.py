"""Sarvam TTS factory for low-latency LiveKit audio output."""

from __future__ import annotations

import logging
from typing import Any

from livekit.plugins import sarvam

logger = logging.getLogger("outbound-agent.sarvam_tts")


def build_sarvam_tts(
    *,
    language: str,
    model: str,
    speaker: str,
    sample_rate: int = 24000,
    pace: float = 1.12,
) -> Any:
    resolved_model = (model or "bulbul:v3").strip() or "bulbul:v3"
    tts = sarvam.TTS(
        target_language_code=language,
        model=resolved_model,
        speaker=speaker,
        speech_sample_rate=sample_rate,
        pace=pace,
        enable_preprocessing=False,
    )
    logger.info(
        "[TTS] Using Sarvam streaming/chunked path model=%s language=%s speaker=%s pace=%s",
        resolved_model,
        language,
        speaker,
        pace,
    )
    return tts
