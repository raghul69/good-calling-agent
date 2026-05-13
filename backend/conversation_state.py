"""Conversation state helpers for the low-latency Tamil/Tanglish voice path."""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger("outbound-agent.conversation_state")

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

CallStage = Literal[
    "greeting",
    "qualification",
    "objection_handling",
    "clarification",
    "transfer_ready",
    "scheduling",
    "closing",
    "completed",
]

ALLOWED_CALL_STAGE_TRANSITIONS: dict[CallStage, set[CallStage]] = {
    "greeting": {"qualification", "clarification", "closing", "completed"},
    "qualification": {"objection_handling", "clarification", "transfer_ready", "scheduling", "closing", "completed"},
    "objection_handling": {"qualification", "clarification", "closing", "completed"},
    "clarification": {"qualification", "objection_handling", "closing", "completed"},
    "transfer_ready": {"scheduling", "closing", "completed"},
    "scheduling": {"transfer_ready", "closing", "completed"},
    "closing": {"completed"},
    "completed": set(),
}


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
    asked_questions: set[str] = field(default_factory=set)
    last_user_intent: str = ""
    last_reply: str = ""
    retry_count: int = 0
    interruption_count: int = 0
    silence_count: int = 0
    fallback_count: int = 0
    last_fallback_at: float = 0.0
    answered_fields: set[str] = field(default_factory=set)
    fields: dict[str, Any] = field(default_factory=dict)
    current_stage: CallStage = "greeting"
    stage_history: list[str] = field(default_factory=lambda: ["greeting"])
    invalid_stage_jump_count: int = 0
    stage_loop_count: int = 0
    compressed_memory: str = ""
    memory_turns: list[dict[str, str]] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    transfer_status: str = ""

    def transition_call_stage(self, next_stage: CallStage, *, reason: str = "") -> bool:
        current = self.current_stage
        if next_stage == current:
            self.stage_loop_count += 1
            logger.info("[CALL_STAGE] current=%s next=%s changed=false reason=%s loop_count=%s", current, next_stage, reason, self.stage_loop_count)
            return False
        if next_stage not in ALLOWED_CALL_STAGE_TRANSITIONS.get(current, set()):
            self.invalid_stage_jump_count += 1
            logger.info(
                "[CALL_STAGE] current=%s next=%s changed=false reason=invalid_jump:%s invalid_count=%s",
                current,
                next_stage,
                reason,
                self.invalid_stage_jump_count,
            )
            return False
        self.current_stage = next_stage
        self.stage_history.append(next_stage)
        logger.info("[CALL_STAGE] current=%s previous=%s changed=true reason=%s", next_stage, current, reason)
        return True

    def remember_turn(self, *, role: str, text: str, intent: str = "") -> None:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        if not cleaned:
            return
        self.memory_turns.append({"role": role[:20], "text": cleaned[:180], "intent": intent[:60]})
        if len(self.memory_turns) > 6:
            self.compress_memory()

    def compress_memory(self) -> str:
        old = self.memory_turns[:-6]
        self.memory_turns = self.memory_turns[-6:]
        if old:
            intents = [item.get("intent", "") for item in old if item.get("intent")]
            user_bits = [item.get("text", "") for item in old if item.get("role") == "user"]
            summary = "; ".join(part for part in [", ".join(intents[-4:]), " | ".join(user_bits[-3:])] if part)
            if summary:
                self.compressed_memory = (self.compressed_memory + " " + summary).strip()[-700:]
            logger.info(
                "[MEMORY_COMPRESSED] kept_turns=%s summarized_turns=%s answered_questions=%s transfer_status=%s",
                len(self.memory_turns),
                len(old),
                len(self.asked_questions),
                self.transfer_status or "-",
            )
        return self.compressed_memory

    def call_isolation_ok(self, *, room_name: str, agent_id: str) -> bool:
        logger.info(
            "[CALL_ISOLATION_OK] room=%s agent_id=%s stage=%s interruptions=%s tts_buffer_shared=false transcript_shared=false",
            room_name or "-",
            agent_id or "-",
            self.current_stage,
            self.interruption_count,
        )
        return True


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
