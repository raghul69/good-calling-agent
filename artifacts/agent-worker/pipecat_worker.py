"""Optional Pipecat realtime voice worker.

This worker is intentionally parallel to the existing LiveKit Agents worker.
It is selected only when `VOICE_PIPELINE=pipecat`; otherwise Railway continues
to run `backend.agent`.

The implementation keeps outbound SIP dispatch and the LiveKit room model
outside this module. Pipecat support is optional because the current production
image does not pin `pipecat-ai` yet. Enabling this flag without installing
Pipecat fails fast with an actionable message instead of silently falling back
to the old path.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.barge_in import BargeInController
from backend.fast_voice_router import FastVoiceRouter
from backend.latency_logger import VoiceLatencyLogger
from backend.llm_streamer import build_voice_llm
from backend.sarvam_streaming_stt import build_sarvam_stt
from backend.sarvam_streaming_tts import build_sarvam_tts

logger = logging.getLogger("pipecat-worker")
logging.basicConfig(level=logging.INFO)


def _require_pipecat() -> None:
    try:
        import pipecat  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            "VOICE_PIPELINE=pipecat requested, but Pipecat is not installed in this image. "
            "Add the pinned Pipecat packages to requirements.txt before enabling this production flag."
        ) from exc


class PipecatRealtimeVoicePipeline:
    """Thin orchestration shell for the optional Pipecat path.

    The fast deterministic layer is production-ready and shared with the
    existing worker. The Pipecat transport wiring is intentionally isolated here
    so it can be enabled after `pipecat-ai` is pinned and validated.
    """

    def __init__(self, *, call_id: str = "") -> None:
        self.call_id = call_id
        self.router = FastVoiceRouter()
        logger.info("[FAST_ROUTER_READY] call_id=%s", call_id)
        self.barge_in = BargeInController()
        logger.info("[BARGE_IN_READY] call_id=%s", call_id)
        self.latency = VoiceLatencyLogger(call_id=call_id, label="PIPECAT_LATENCY")
        self.active_response_task: asyncio.Task[Any] | None = None
        self.tts_playing = False

    async def handle_transcript(self, text: str, *, is_final: bool) -> str | None:
        if not is_final:
            started = time.perf_counter()
            route = self.router.note_partial(text)
            self.latency.log(stage=self.router.state.stage, stt_partial_ms=int((time.perf_counter() - started) * 1000))
            if route.handled and self.tts_playing:
                self.barge_in.note_user_speech(text)
                self.barge_in.interrupt(self, self.active_response_task, reason=f"partial_intent:{route.intent}")
            return None

        started = time.perf_counter()
        self.router.start_turn()
        route = self.router.route_final(text)
        router_ms = int((time.perf_counter() - started) * 1000)
        self.latency.log(stage=self.router.state.stage, router_ms=router_ms)
        if route.handled:
            return route.message
        return None

    def build_services(self, config: dict[str, Any]) -> dict[str, Any]:
        """Build reusable STT/LLM/TTS service instances for Pipecat wiring."""
        stt = build_sarvam_stt(
            language=str(config.get("stt_language") or "unknown"),
            model=str(config.get("stt_model") or "saaras:v3"),
        )
        logger.info("[SARVAM_STT_READY] provider=sarvam model=%s", str(config.get("stt_model") or "saaras:v3"))
        llm = build_voice_llm(
            provider=str(config.get("llm_provider") or "groq"),
            model=str(config.get("llm_model") or "llama-3.1-8b-instant"),
            max_completion_tokens=int(config.get("llm_max_tokens") or 36),
            temperature=float(config.get("llm_temperature") or 0.2),
        )
        logger.info("[LLM_READY] provider=%s model=%s", str(config.get("llm_provider") or "groq"), str(config.get("llm_model") or "llama-3.1-8b-instant"))
        tts = build_sarvam_tts(
            language=str(config.get("tts_language") or "ta-IN"),
            model=str(config.get("tts_model") or "bulbul:v3"),
            speaker=str(config.get("tts_voice") or "priya"),
            pace=float(config.get("tts_pace") or 1.12),
        )
        logger.info("[SARVAM_TTS_READY] provider=sarvam model=%s", str(config.get("tts_model") or "bulbul:v3"))
        return {"stt": stt, "llm": llm, "tts": tts}

    def interrupt(self, *, force: bool = True) -> None:
        self.tts_playing = False

    def log_call_started(self, *, phone: str = "", agent: str = "") -> None:
        logger.info("[CALL_STARTED] call_id=%s pipeline=pipecat phone=%s agent=%s", self.call_id, phone, agent)


async def main() -> None:
    logger.info("[PIPECAT_WORKER_STARTED] pipeline=pipecat argv=%s", " ".join(sys.argv[1:]))
    _require_pipecat()
    # The actual Pipecat LiveKit transport wiring is intentionally kept behind
    # the feature flag and package check. This module provides the production
    # router/barge-in/service composition without changing the default worker.
    pipeline = PipecatRealtimeVoicePipeline(call_id=os.getenv("RAILWAY_DEPLOYMENT_ID", "pipecat"))
    pipeline.log_call_started(
        phone=os.getenv("OUTBOUND_PHONE_NUMBER", os.getenv("PHONE_NUMBER", "")),
        agent=os.getenv("LIVEKIT_AGENT_NAME", os.getenv("AGENT_NAME", "outbound-agent")),
    )
    pipeline.build_services(
        {
            "stt_language": os.getenv("STT_LANGUAGE", "unknown"),
            "stt_model": os.getenv("STT_MODEL", "saaras:v3"),
            "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
            "llm_model": os.getenv("LLM_MODEL", "llama-3.1-8b-instant"),
            "tts_language": os.getenv("TTS_LANGUAGE", "ta-IN"),
            "tts_model": os.getenv("TTS_MODEL", "bulbul:v3"),
            "tts_voice": os.getenv("TTS_VOICE", "priya"),
        }
    )
    raise RuntimeError(
        "Pipecat package is installed, but LiveKit transport wiring is not enabled yet. "
        "Keep VOICE_PIPELINE=livekit_agents until the transport is validated in staging."
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
