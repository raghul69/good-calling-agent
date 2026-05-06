"""Structured latency logging for realtime voice turns."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger("outbound-agent.latency")


@dataclass
class VoiceLatencySnapshot:
    call_id: str = ""
    stage: str = ""
    stt_partial_ms: int = 0
    stt_final_ms: int = 0
    router_ms: int = 0
    llm_first_token_ms: int = 0
    tts_first_audio_ms: int = 0
    publish_ms: int = 0
    total_first_audio_ms: int = 0
    livekit_publish_ms: int = 0
    total_response_ms: int = 0


class VoiceLatencyLogger:
    def __init__(self, *, call_id: str = "", slow_threshold_ms: int = 1500, label: str = "VOICE_LATENCY") -> None:
        self.call_id = call_id
        self.slow_threshold_ms = slow_threshold_ms
        self.label = label

    def log(self, **values: int | str) -> None:
        payload = VoiceLatencySnapshot(call_id=self.call_id)
        for key, value in values.items():
            if hasattr(payload, key):
                setattr(payload, key, value)
        if payload.publish_ms == 0 and payload.livekit_publish_ms:
            payload.publish_ms = payload.livekit_publish_ms
        if payload.livekit_publish_ms == 0 and payload.publish_ms:
            payload.livekit_publish_ms = payload.publish_ms
        if payload.total_first_audio_ms == 0 and payload.total_response_ms:
            payload.total_first_audio_ms = payload.total_response_ms
        if payload.total_response_ms == 0 and payload.total_first_audio_ms:
            payload.total_response_ms = payload.total_first_audio_ms
        data = asdict(payload)
        logger.info("[%s] %s", self.label, json.dumps(data, ensure_ascii=True, separators=(",", ":")))
        total_ms = int(data.get("total_first_audio_ms") or data.get("total_response_ms") or 0)
        if total_ms > self.slow_threshold_ms:
            logger.warning("[SLOW_RESPONSE] %s", json.dumps(data, ensure_ascii=True, separators=(",", ":")))
