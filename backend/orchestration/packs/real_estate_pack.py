"""Real estate vertical — Groq JSON orchestration output."""

from __future__ import annotations

import json
import logging
from typing import Any

from .groq_json import DEFAULT_MODEL, groq_json_completion

logger = logging.getLogger("outbound-agent.orchestration.packs")

STAGES = (
    "INTRO",
    "LOCATION_CAPTURE",
    "BUDGET_CAPTURE",
    "PROPERTY_TYPE",
    "BHK_CAPTURE",
    "PURPOSE_CAPTURE",
    "TIMELINE_CAPTURE",
    "SITE_VISIT",
    "WHATSAPP_CONFIRM",
    "LEAD_SAVE",
    "END",
)

INTENTS = (
    "book_site_visit",
    "request_brochure",
    "callback_request",
    "investment_interest",
    "loan_help",
    "general",
)

SYSTEM = """You are a real-estate voice-call orchestration brain. Output a single JSON object only.

Allowed workflow_stage values: """ + ", ".join(STAGES) + """

Allowed intent values: """ + ", ".join(INTENTS) + """

lead_fields must include these keys (strings unless noted):
- name, location, budget, property_type, bhk, timeline, purpose
- whatsapp_available (boolean)

Rules:
- Progress workflow_stage based on what is still unknown and the latest user message.
- action must be one of: speak, transfer, end_call, save_data, noop
- transfer: only if user asks for human/agent or loan help that should be routed away (or intent loan_help and they insist on human).
- end_call: user clearly ends the conversation.
- save_data: when lead is ready to persist (LEAD_SAVE) or user confirms WhatsApp / details.
- message: short line the agent should say next (1-2 sentences, conversational). English or match user language implied from conversation.
- lead_score: optional number 0-100 for lead quality.

Return exactly this JSON shape:
{
  "workflow_stage": "<STAGE>",
  "intent": "<INTENT>",
  "action": "speak|transfer|end_call|save_data|noop",
  "message": "<text>",
  "lead_fields": { ... },
  "lead_score": 0
}
"""


async def run_real_estate_pack(
    *,
    agent_config: dict[str, Any],
    pack_state: dict[str, Any],
    user_text: str,
    transcript_context: str,
    language_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("[REAL_ESTATE_PACK] inference started")
    user_payload = json.dumps(
        {
            "current_workflow_stage": pack_state.get("workflow_stage") or "INTRO",
            "merged_lead_fields": pack_state.get("extracted_fields") or {},
            "transcript_tail": transcript_context,
            "latest_user_message": user_text,
            "business_type_hint": agent_config.get("business_type") or "",
        },
        ensure_ascii=True,
    )
    out = await groq_json_completion(system=SYSTEM, user=user_payload, model=DEFAULT_MODEL)
    if not out:
        logger.warning("[REAL_ESTATE_PACK] empty model output")
        return {}
    return out
