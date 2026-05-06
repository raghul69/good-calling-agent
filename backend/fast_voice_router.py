"""Deterministic no-LLM router for realtime Tamil/Tanglish outbound calls."""

from __future__ import annotations

import logging
import time

from backend.conversation_state import (
    ConversationStage,
    FastRouteResult,
    FastVoiceState,
    has_voice_pattern,
    is_area_answer,
    is_budget_answer,
    is_property_type_answer,
    normalize_voice_text,
)

logger = logging.getLogger("outbound-agent.fast_voice_router")


class FastVoiceRouter:
    """Handles predictable call-flow turns without touching the LLM."""

    CONFUSION_RESPONSE = "Sorry sir, konjam simple-ah solren."
    DUPLICATE_RECOVERY_RESPONSE = "Sir, answer clear-ah varala. Konjam simple-ah sollunga."
    CLEAR_CHECK = "Hello sir, voice clear-ah kekkudha?"
    INTRO_RESPONSE = "MAXR Consultancy la irundhu property regarding call panniruken sir."
    BUSY_RESPONSE = "No problem sir, convenient time la call pannaren."
    WRONG_NUMBER_RESPONSE = "Sorry sir, wrong number disturb panniten."
    CUT_CALL_RESPONSE = "Seri sir, thanks. Call cut pannuren."
    PROPERTY_TYPE_QUESTION = "Flat venuma illa plot venuma sir?"
    AREA_QUESTION = "Chennai la endha area property venum sir?"
    BUDGET_QUESTION = "Budget approx evlo sir?"
    TIMELINE_QUESTION = "Eppo buying plan panreenga sir?"
    SITE_VISIT_QUESTION = "Site visit arrange pannalama sir?"

    def __init__(self, *, initial_stage: ConversationStage = "greeting") -> None:
        self.state = FastVoiceState(stage=initial_stage)
        self._turn_start: float | None = None
        self._partial_started_at: float | None = None
        self.last_router_ms = 0
        self.last_partial_ms = 0

    def start_turn(self) -> None:
        self.state.turn_index += 1
        self._turn_start = time.perf_counter()
        self._partial_started_at = None
        self.state.early_intent = ""

    def note_partial(self, text: str) -> FastRouteResult:
        if self._partial_started_at is None:
            self._partial_started_at = time.perf_counter()
        result = self._classify(text, partial=True)
        self.last_partial_ms = self._ms_since(self._partial_started_at)
        if result.intent:
            self.state.early_intent = result.intent
            logger.info(
                "[VOICE_LATENCY] stage=%s stt_partial_ms=%s intent=%s text=%s",
                self.state.stage,
                self.last_partial_ms,
                result.intent,
                text[:120],
            )
        return result

    def route_final(self, text: str) -> FastRouteResult:
        start = time.perf_counter()
        self.state.last_user_text = str(text or "").strip()
        result = self._classify(text, partial=False)
        if result.handled and result.stage:
            self.state.last_stage = self.state.stage
            self.state.stage = result.stage
        if result.handled and result.message:
            result.message = self._guard_repeated_question(result.message, result.intent, result.allow_repeat)
            self.state.last_agent_text = result.message
        self.last_router_ms = self._ms_since(start)
        logger.info(
            "[VOICE_LATENCY] stage=%s router_ms=%s handled=%s intent=%s needs_llm=%s",
            self.state.stage,
            self.last_router_ms,
            result.handled,
            result.intent or "-",
            result.needs_llm,
        )
        return result

    def mark_agent_reply(self, text: str, *, question_key: str = "") -> None:
        cleaned = str(text or "").strip()
        self.state.last_agent_text = cleaned
        if question_key:
            self.state.last_question_key = question_key

    def _classify(self, text: str, *, partial: bool) -> FastRouteResult:
        raw = str(text or "").strip()
        low = normalize_voice_text(raw)
        if not low:
            return FastRouteResult(False, needs_llm=False)

        if has_voice_pattern(r"\b(hello+|helo+|hallo+|hi|hey)\b", low):
            logger.info("[CONFUSION_DETECTED] phrase=hello stage=%s", self.state.stage)
            return FastRouteResult(True, self.CLEAR_CHECK, "hello", "collect_language", allow_repeat=True)
        if has_voice_pattern(r"\b(what|what is it|enna|edhukku|yaru|who is this)\b", low):
            return FastRouteResult(True, self.INTRO_RESPONSE, "what_is_it", self.state.stage, allow_repeat=True)
        if has_voice_pattern(r"\b(not clear|speak properly|speak clearly|i don'?t understand|don'?t understand|dont understand|puriyala|theriyala|clear ah illa)\b", low):
            logger.info("[CONFUSION_DETECTED] phrase=unclear stage=%s", self.state.stage)
            return FastRouteResult(True, self.CONFUSION_RESPONSE, "confused", "collect_language", allow_repeat=True)
        if has_voice_pattern(r"\b(repeat|again|once more|innoru thadava|marubadi|thirumba)\b", low):
            return FastRouteResult(True, self.state.last_agent_text or self.PROPERTY_TYPE_QUESTION, "repeat", self.state.stage, allow_repeat=True)
        if has_voice_pattern(r"\b(busy|velai|meeting|later|call later)\b", low):
            return FastRouteResult(True, self.BUSY_RESPONSE, "busy", "completed", allow_repeat=True)
        if has_voice_pattern(r"\b(wrong number|wrong person|number wrong|thappu number|wrong call)\b", low):
            return FastRouteResult(True, self.WRONG_NUMBER_RESPONSE, "wrong_number", "completed", allow_repeat=True)
        if has_voice_pattern(r"\b(cut the call|cut call|disconnect|hang up|phone cut|call cut|vachudunga)\b", low):
            return FastRouteResult(True, self.CUT_CALL_RESPONSE, "cut_call", "completed", allow_repeat=True)
        if has_voice_pattern(r"\b(tamil|tamizh)\b", low):
            self.state.language_preference = "tamil"
            self.state.answered_fields.add("language")
            return FastRouteResult(True, self.PROPERTY_TYPE_QUESTION, "language_tamil", "collect_property_type")
        if has_voice_pattern(r"\b(english|inglish)\b", low):
            self.state.language_preference = "english"
            self.state.answered_fields.add("language")
            return FastRouteResult(True, self.PROPERTY_TYPE_QUESTION, "language_english", "collect_property_type")

        if is_property_type_answer(raw):
            self.state.property_type = raw[:80]
            self.state.fields["property_type"] = self.state.property_type
            self.state.answered_fields.add("property_type")
            return FastRouteResult(True, self.AREA_QUESTION, "property_type_answer", "collect_area")

        if self._contains_area_signal(raw) and is_budget_answer(raw):
            self.state.area = raw[:80]
            self.state.budget = raw[:80]
            self.state.fields["area"] = self.state.area
            self.state.fields["budget"] = self.state.budget
            self.state.answered_fields.update({"area", "budget"})
            return FastRouteResult(True, self.TIMELINE_QUESTION, "area_budget_answer", "collect_timeline")

        if is_area_answer(raw):
            self.state.area = raw[:80]
            self.state.fields["area"] = self.state.area
            self.state.answered_fields.add("area")
            return FastRouteResult(True, self.BUDGET_QUESTION, "area_answer", "collect_budget")

        if is_budget_answer(raw):
            self.state.budget = raw[:80]
            self.state.fields["budget"] = self.state.budget
            self.state.answered_fields.add("budget")
            return FastRouteResult(True, self.TIMELINE_QUESTION, "budget_answer", "collect_timeline")

        if has_voice_pattern(r"\b(today|tomorrow|weekend|this week|next week|immediate|immediately|month|months|later)\b", low):
            self.state.timeline = raw[:80]
            self.state.fields["timeline"] = self.state.timeline
            self.state.answered_fields.add("timeline")
            return FastRouteResult(True, self.SITE_VISIT_QUESTION, "timeline_answer", "offer_site_visit")

        if has_voice_pattern(r"\b(yes|yeah|ok|okay|seri|sure|pannalam|venum|interested)\b", low):
            if self.state.stage == "offer_site_visit":
                self.state.appointment_confirmed = True
                return FastRouteResult(True, "Super sir, unga name sollunga?", "site_visit_yes", "completed")
            return FastRouteResult(True, self._next_question_for_stage(), "yes_continue", self.state.stage)

        if has_voice_pattern(r"\b(no|illa|vendam|not interested)\b", low):
            if self.state.stage == "offer_site_visit":
                return FastRouteResult(True, "No problem sir, WhatsApp details send pannalama?", "site_visit_no", "completed")
            return FastRouteResult(True, self._next_question_for_stage(), "no_continue", self.state.stage)

        if partial:
            return FastRouteResult(False, intent="", needs_llm=False, confidence=0.0)
        return FastRouteResult(False, intent="complex", needs_llm=True, confidence=0.0)

    def _next_question_for_stage(self) -> str:
        if "property_type" not in self.state.answered_fields:
            return self.PROPERTY_TYPE_QUESTION
        if "area" not in self.state.answered_fields:
            return self.AREA_QUESTION
        if "budget" not in self.state.answered_fields:
            return self.BUDGET_QUESTION
        if "timeline" not in self.state.answered_fields:
            return self.TIMELINE_QUESTION
        return self.SITE_VISIT_QUESTION

    def _guard_repeated_question(self, message: str, intent: str, allow_repeat: bool) -> str:
        key = self._question_key(message, intent)
        if allow_repeat:
            self.state.last_question_key = key
            return message
        if key and key == self.state.last_question_key:
            self.state.repeated_question_count += 1
            self.state.repeat_counter += 1
            logger.info(
                "[DUPLICATE_QUESTION_BLOCKED] key=%s count=%s stage=%s",
                key,
                self.state.repeat_counter,
                self.state.stage,
            )
            message = self.DUPLICATE_RECOVERY_RESPONSE
            key = self._question_key(message, intent)
        self.state.last_question_key = key
        self.state.last_question = message if key else ""
        return message

    @staticmethod
    def _question_key(message: str, intent: str) -> str:
        low = normalize_voice_text(message)
        if "flat" in low or "plot" in low:
            return "property_type"
        if "area" in low:
            return "area"
        if "budget" in low:
            return "budget"
        if "buying" in low or "timeline" in low or "eppo" in low:
            return "timeline"
        if "site visit" in low:
            return "site_visit"
        return intent or low

    @staticmethod
    def _contains_area_signal(text: str) -> bool:
        low = normalize_voice_text(text)
        known = (
            "adyar|anna nagar|velachery|tambaram|omr|ecr|porur|medavakkam|sholinganallur|"
            "guindy|chromepet|pallavaram|perungudi|thoraipakkam|nungambakkam|tnagar|t nagar|"
            "chennai|coimbatore|madurai|trichy|salem"
        )
        return bool(has_voice_pattern(rf"\b({known})\b", low) or has_voice_pattern(r"\b(area|location|near|side|la|le)\b", low))

    @staticmethod
    def _ms_since(start: float | None) -> int:
        if start is None:
            return 0
        return max(0, int((time.perf_counter() - start) * 1000))
