"""Tamil / Tanglish real-estate sales conversion — Groq JSON (DECIDE step after conversation understanding)."""

from __future__ import annotations

import json
import logging
from typing import Any

from .groq_json import groq_json_completion, resolve_groq_model

logger = logging.getLogger("outbound-agent.orchestration.packs")

STAGES = (
    "GREETING",
    "QUALIFICATION",
    "LOCATION_CAPTURE",
    "BUDGET_CAPTURE",
    "PROPERTY_TYPE",
    "PURPOSE_CAPTURE",
    "TIMELINE_CAPTURE",
    "OBJECTION_HANDLE",
    "SITE_VISIT",
    "WHATSAPP_CONFIRM",
    "LEAD_SAVE",
    "CLOSING",
)

SYSTEM = """You are the DECIDE step for a Chennai Tanglish real-estate voice agent.
Listen to inputs: you receive prior conversation understanding JSON + user text. Output ONE JSON object only, no markdown.

Pipeline: LISTEN (already done) → UNDERSTANDING (provided) → YOU DECIDE response → agent will RESPOND via TTS.

Tamil/Tanglish style (voice-friendly):
- Short sentences; respectful (sir/madam, neenga); one clear question at a time.
- Keep reply under 9 words when possible; TTS starts faster.
- Use simple Tanglish over formal Tamil pronunciation-heavy wording.
- Never ask the exact same question twice in a row; rephrase or move to a simpler next slot.
- Natural fillers allowed: "seri sir", "okay madam", "actually", "roughly".
- BAD (too English-only): "What is your budget?"
- GOOD: "Approx budget range sollunga sir — adhuku suitable options suggest panren."
- BAD: "Are you interested?"
- GOOD: "Weekend site visit arrange pannalama sir?"
- Confirm before WhatsApp number share or transfer.

workflow_stage must be exactly one of: """ + ", ".join(STAGES) + """

Progress the stage based on what is still unknown and the latest user message + understanding.
When user raises objection (too_expensive, call_later, etc.), use OBJECTION_HANDLE and steer toward smaller budget options / callback / site visit — remain helpful.
When user sounds confused ("hello", "not clear", "speak properly", "I don't understand", "puriyala"), apologize once, switch to simpler English/Tanglish, and continue with one easy question.

Objection handling examples (adapt in Tanglish, do not copy verbatim if context differs):
- too_expensive → acknowledge, offer smaller budget tier or flexible payment angle.
- call_later → agree, offer short callback window or WhatsApp.

lead_fields keys (strings unless boolean):
name, location, budget, property_type, bhk, timeline, purpose, interest_level (low/medium/high),
site_visit_interest (yes/no/maybe), whatsapp_available (boolean)

Primary conversion: SITE_VISIT, WHATSAPP_CONFIRM, schedule_callback, brochure (via tool_call if needed).
Secondary: qualify (QUALIFICATION..TIMELINE_CAPTURE), LEAD_SAVE with save_data.

action must be one of:
  speak — normal reply; set "message" and optional "next_question" if message empty.
  transfer — human needed (respect tool policy).
  save_data — persist lead (LEAD_SAVE / confirmed details).
  schedule_callback — user agreed callback; optional extra keys in action_payload.
  send_whatsapp — WhatsApp handoff confirmed at WHATSAPP_CONFIRM.
  end_call — polite close.
  tool_call — generic tool: set tool_name, tool_payload.

Return exactly:
{
  "language": "ta-IN",
  "tone": "friendly_chennai_tanglish",
  "workflow_stage": "",
  "intent": "",
  "action": "speak|transfer|save_data|end_call|schedule_callback|send_whatsapp|tool_call",
  "message": "",
  "lead_fields": {},
  "next_question": "",
  "tool_name": "",
  "tool_payload": {},
  "action_payload": {}
}
Use action_payload for schedule_callback/send_whatsapp hints (preferred_date, time_window, phone_last4) when relevant.
"""


async def run_tamil_real_estate_pack(
    *,
    agent_config: dict[str, Any],
    pack_state: dict[str, Any],
    user_text: str,
    transcript_context: str,
    language_config: dict[str, Any] | None = None,
    understanding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("[TAMIL_REAL_ESTATE_PACK] inference started")
    lc = language_config if isinstance(language_config, dict) else {}
    u = understanding if isinstance(understanding, dict) else {}
    user_payload = json.dumps(
        {
            "language_config": lc,
            "conversation_understanding": u,
            "current_workflow_stage": pack_state.get("workflow_stage") or "GREETING",
            "merged_lead_fields": pack_state.get("extracted_fields") or {},
            "transcript_tail": transcript_context,
            "latest_user_message": user_text,
            "business_type_hint": agent_config.get("business_type") or "",
        },
        ensure_ascii=True,
    )
    out = await groq_json_completion(system=SYSTEM, user=user_payload, model=resolve_groq_model())
    if not out:
        logger.warning("[TAMIL_REAL_ESTATE_PACK] empty model output")
        return {}
    return out
