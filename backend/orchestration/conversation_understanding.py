"""
Conversation understanding pass (LISTEN → UNDERSTAND): Groq JSON only.
Used before the Tamil real-estate pack DECIDE step — does not touch STT/TTS.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.orchestration.packs.groq_json import groq_json_completion, resolve_groq_model

logger = logging.getLogger("outbound-agent.orchestration.understanding")

DEFAULT_UNDERSTANDING: dict[str, Any] = {
    "intent": "",
    "emotion": "",
    "workflow_stage": "",
    "interest_level": "",
    "objection": "",
    "entities": {},
    "next_action": "",
    "human_transfer_needed": False,
}

SYSTEM = """You classify the latest user turn in a Tamil/Tanglish real-estate sales phone call.
Output one JSON object only, no markdown.

Fields:
- intent: one of
  interested | confused | not_interested | callback_request | budget_issue | family_discussion | investment_interest | immediate_purchase | other
- emotion: short label (e.g. neutral, hesitant, frustrated, happy, urgent)
- workflow_stage: which selling stage this maps to (free text, but prefer):
  GREETING | QUALIFICATION | LOCATION_CAPTURE | BUDGET_CAPTURE | PROPERTY_TYPE | PURPOSE_CAPTURE | TIMELINE_CAPTURE |
  OBJECTION_HANDLE | SITE_VISIT | WHATSAPP_CONFIRM | LEAD_SAVE | CLOSING
- interest_level: low | medium | high | unknown
- objection: one of
  none | too_expensive | call_later | family_discussion | not_interested | already_booked | other
  Use "none" when there is no objection.
- entities: object with any short string slots you extract (budget range, location, property type, timeline, etc.)
- next_action: short machine label for what the seller should do next, e.g. qualify_location | handle_objection | propose_site_visit | confirm_whatsapp | save_lead | end_call
- human_transfer_needed: boolean; true if caller insists on human/agent/supervisor.

Rules:
- User may speak Tamil, Tanglish, or English; judge meaning, not script.
- If unclear, set intent to "other" and interest_level to "unknown".
- If caller says hello repeatedly, not clear, speak properly, I don't understand, or puriyala, set intent to "confused", emotion to "confused", and next_action to "recover_simpler_language".

Return exactly:
{
  "intent": "",
  "emotion": "",
  "workflow_stage": "",
  "interest_level": "",
  "objection": "",
  "entities": {},
  "next_action": "",
  "human_transfer_needed": false
}
"""


def normalize_understanding(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_UNDERSTANDING)
    if not isinstance(raw, dict):
        return out
    for k in ("intent", "emotion", "workflow_stage", "interest_level", "objection", "next_action"):
        if raw.get(k) is not None:
            out[k] = str(raw[k] or "").strip()
    ent = raw.get("entities")
    out["entities"] = ent if isinstance(ent, dict) else {}
    h = raw.get("human_transfer_needed")
    if isinstance(h, bool):
        out["human_transfer_needed"] = h
    elif isinstance(h, str):
        out["human_transfer_needed"] = h.strip().lower() in ("true", "1", "yes")
    return out


async def run_conversation_understanding(
    *,
    user_text: str,
    transcript_context: str,
    pack_state: dict[str, Any],
    model: str | None = None,
) -> dict[str, Any]:
    """Second Groq call for `tamil_real_estate` vertical (after transcript append)."""
    user_payload = json.dumps(
        {
            "current_workflow_stage": (pack_state or {}).get("workflow_stage") or "",
            "known_lead_fields": (pack_state or {}).get("extracted_fields") or {},
            "transcript_tail": transcript_context,
            "latest_user_message": user_text,
        },
        ensure_ascii=True,
    )
    m = model or resolve_groq_model()
    out = await groq_json_completion(system=SYSTEM, user=user_payload, model=m)
    if not out:
        logger.warning("[UNDERSTANDING] empty model output — using defaults")
    nu = normalize_understanding(out if isinstance(out, dict) else None)
    return nu
