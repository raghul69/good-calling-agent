"""Placeholder async executor for non-calendar orchestration tools (mocked until wired)."""

from __future__ import annotations

import json
import logging
from typing import Any
from backend.tracing import sanitize_for_trace, trace_event

logger = logging.getLogger("outbound-agent.orchestration.tools")

ORCH_LEAD_SUMMARY_CAP = 4000

# IDs supported by this executor (calendar tools stay on AgentTools in the worker).
_EXEC_IDS = frozenset(
    {
        "webhook",
        "custom_function",
        "save_lead",
        "create_ticket",
        "crm_push",
        "schedule_callback",
        "send_whatsapp",
    }
)


def caller_name_from_orchestration_lead(lead: dict[str, Any]) -> str:
    for k in ("caller_name", "full_name", "name", "customer_name"):
        v = lead.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()[:160]
    return ""


def format_summary_with_orchestration_lead(
    base: str,
    lead: dict[str, Any] | None,
    cap: int = ORCH_LEAD_SUMMARY_CAP,
) -> str:
    """Append bounded JSON snapshot of orchestration lead fields for call_logs.summary / CRM."""
    if not lead:
        return base[:cap] if len(base) > cap else base
    try:
        blob = json.dumps(lead, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        blob = str(lead)
    sep = " | orch_lead="
    max_total = cap
    if len(base) >= max_total:
        return base[:max_total]
    overhead = len(base) + len(sep)
    if overhead >= max_total:
        return base[:max_total]
    budget = max_total - overhead
    if budget < 32:
        return base[:max_total]
    if len(blob) > budget:
        blob = blob[: max(0, budget - 1)] + "…"
    return f"{base}{sep}{blob}"


class ToolExecutor:
    def __init__(self) -> None:
        self.latest_lead: dict[str, Any] | None = None

    async def execute(self, tool_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        tid = (tool_id or "").strip()
        trace_event("tool_execution_start", tool_id=tid, payload=sanitize_for_trace(payload or {}))
        if tid not in _EXEC_IDS:
            logger.info("[TRACE] tool_failure_continued tool_id=%s error=unknown_tool", tid)
            result = {"ok": False, "error": "unknown_tool", "tool_id": tid}
            trace_event("tool_failure_continued", tool_id=tid, error="unknown_tool")
            return result
        if tid == "save_lead":
            fields = dict(payload or {})
            prior = dict(self.latest_lead) if isinstance(self.latest_lead, dict) else {}
            self.latest_lead = {**prior, **fields}
            logger.info("[SAVE_LEAD] captured_keys=%s", sorted(fields.keys()))
            result = {"ok": True, "tool_id": tid, "payload": fields}
            trace_event("tool_execution_end", tool_id=tid, ok=True, payload=sanitize_for_trace(fields))
            return result
        logger.info("[TOOL_EXEC] mock_execute tool_id=%s", tid)
        result = {"ok": True, "mocked": True, "tool_id": tid, "payload": payload or {}}
        trace_event("tool_execution_end", tool_id=tid, ok=True)
        return result
