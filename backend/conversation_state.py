"""Conversation state helpers for the low-latency Tamil/Tanglish voice path."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

ConversationStage = Literal[
    "greeting",
    "collect_language",
    "collect_property_type",
    "collect_area",
    "collect_budget",
    "collect_timeline",
    "offer_site_visit",
    "transfer",
    "completed",
]


@dataclass
class FastRouteResult:
    handled: bool
    message: str = ""
    intent: str = ""
    stage: ConversationStage | None = None
    needs_llm: bool = False
    allow_repeat: bool = False
    confidence: float = 1.0


@dataclass
class FastVoiceState:
    stage: ConversationStage = "greeting"
    language_preference: str = ""
    property_type: str = ""
    area: str = ""
    budget: str = ""
    timeline: str = ""
    caller_name: str = ""
    appointment_confirmed: bool = False
    last_question: str = ""
    last_stage: ConversationStage = "greeting"
    repeat_counter: int = 0
    last_question_key: str = ""
    last_agent_text: str = ""
    last_user_text: str = ""
    repeated_question_count: int = 0
    turn_index: int = 0
    early_intent: str = ""
    answered_fields: set[str] = field(default_factory=set)
    fields: dict[str, Any] = field(default_factory=dict)


def normalize_voice_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\u0b80-\u0bff]+", " ", str(text or "").lower()).strip()


def has_voice_pattern(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def is_budget_answer(text: str) -> bool:
    low = normalize_voice_text(text)
    return bool(
        re.search(r"\b(\d+(\.\d+)?\s*(l|lac|lakh|lakhs|cr|crore|crores|k|thousand)|budget)\b", low)
        or re.search(r"\b(under|below|around|approx|approximately)\s+\d+", low)
    )


def is_property_type_answer(text: str) -> bool:
    low = normalize_voice_text(text)
    return bool(re.search(r"\b(flat|apartment|plot|villa|land|house|individual|1bhk|2bhk|3bhk|4bhk|bhk)\b", low))


def is_area_answer(text: str) -> bool:
    low = normalize_voice_text(text)
    if not low or is_budget_answer(low) or is_property_type_answer(low):
        return False
    known = (
        "adyar|anna nagar|velachery|tambaram|omr|ecr|porur|medavakkam|sholinganallur|"
        "guindy|chromepet|pallavaram|perungudi|thoraipakkam|nungambakkam|tnagar|t nagar|"
        "chennai|coimbatore|madurai|trichy|salem"
    )
    return bool(re.search(rf"\b({known})\b", low) or has_voice_pattern(r"\b(area|location|near|side|la|le)\b", low))
