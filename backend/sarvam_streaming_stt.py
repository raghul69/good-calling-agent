"""Sarvam STT factory for the LiveKit realtime worker.

LiveKit owns the frame subscription and streaming lifecycle. The important
production choice here is to avoid OpenAI STT for Tamil/Tanglish calls and use
Sarvam with low endpointing latency and high VAD sensitivity.
"""

from __future__ import annotations

import logging
from typing import Any

from livekit.plugins import sarvam

logger = logging.getLogger("outbound-agent.sarvam_stt")


def build_sarvam_stt(*, language: str, model: str, sample_rate: int = 16000) -> Any:
    resolved_model = (model or "saaras:v3").strip() or "saaras:v3"
    stt = sarvam.STT(
        language=language or "unknown",
        model=resolved_model,
        mode="translate",
        flush_signal=True,
        high_vad_sensitivity=True,
        sample_rate=sample_rate,
    )
    logger.info("[STT] Using Sarvam streaming path model=%s language=%s sample_rate=%s", resolved_model, language or "unknown", sample_rate)
    return stt
