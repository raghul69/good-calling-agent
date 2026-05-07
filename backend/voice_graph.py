"""Compatibility trace surface for voice graph style callers.

The production voice flow currently runs through ``backend.agent`` and
``backend.orchestration``. This module exists so optional callers can trace a
voice-graph reply without changing the LiveKit call path.
"""

from __future__ import annotations

from typing import Any

from backend.tracing import sanitize_for_trace, trace_event, traceable


@traceable(name="voice_graph.get_voice_reply", run_type="chain")
async def get_voice_reply(*, user_text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    safe_meta = sanitize_for_trace(metadata or {})
    trace_event("voice_graph_start", text_len=len(user_text or ""), metadata=safe_meta)
    result = {"reply": "", "handled": False}
    trace_event("voice_graph_end", handled=False, metadata=safe_meta)
    return result
