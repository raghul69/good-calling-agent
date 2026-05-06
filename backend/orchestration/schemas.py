"""Typed orchestration state and action envelopes for the realtime voice brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ActionType = Literal[
    "speak",
    "transfer",
    "end_call",
    "tool_call",
    "save_data",
    "noop",
    "schedule_callback",
    "send_whatsapp",
]


@dataclass
class AgentAction:
    """Single routing decision after processing final STT text for one turn."""

    type: ActionType
    tool_name: str | None = None
    payload: dict[str, Any] | None = None
    reason: str | None = None
    orchestration_message: str | None = None
    workflow_stage: str | None = None
    intent: str | None = None
    risk_level: str | None = None
    lead_score: float | None = None
    next_question: str | None = None
    orchestration_language: str | None = None
    orchestration_tone: str | None = None


@dataclass
class AgentSessionState:
    """In-memory conversation state for one room / call."""

    current_stage: str = "live"
    transcript: list[dict[str, str]] = field(default_factory=list)
    collected_fields: dict[str, Any] = field(default_factory=dict)
    last_user_message: str = ""
    last_agent_message: str = ""
    transfer_requested: bool = False
    call_status: str = "active"
    started_at: float | None = None
    ended_at: float | None = None
    interruption_count: int = 0


@dataclass
class RuntimeConfig:
    """Light snapshot used when constructing an orchestrator outside the worker."""

    agent_id: str | None = None
    call_id: str | None = None
    room_name: str | None = None
    user_id: str | None = None
    org_id: str | None = None
