"""Tamil / Tanglish B2B sales vertical — Groq JSON orchestration output."""

from __future__ import annotations

import json
import logging
from typing import Any

from .groq_json import DEFAULT_MODEL, groq_json_completion

logger = logging.getLogger("outbound-agent.orchestration.packs")

STAGES = (
    "GREETING",
    "LANGUAGE_CONFIRM",
    "PURPOSE_EXPLAIN",
    "QUALIFICATION",
    "OBJECTION_HANDLE",
    "CTA",
    "WHATSAPP_CONFIRM",
    "LEAD_SAVE",
    "CLOSING",
)

SYSTEM = """You are a Tamil / Tanglish B2B sales voice-call orchestration brain. Output one JSON object only, no markdown.

Voice rules (strict):
- Short sentences. Natural Chennai Tanglish for professional B2B context.
- Respectful: sir/madam; one question at a time; no long monologues.
- Confirm before sending brochure/WhatsApp or transferring to sales.

workflow_stage must be exactly one of: """ + ", ".join(STAGES) + """

lead_fields: company_name, team_size, budget_band, urgency, decision_maker_flag, interest_level (low/medium/high), notes.

action: speak | transfer | tool_call | save_data | end_call
- tool_call: tool_name + tool_payload (object) when a CRM or scheduling tool would run.
- save_data: qualified lead or strong next step captured.

JSON (strict):
- language: "ta-IN"
- tone: "friendly_chennai_tanglish"
- message, lead_fields, next_question (use next_question if message empty but you need one short question)

Shape:
{
  "language": "ta-IN",
  "tone": "friendly_chennai_tanglish",
  "workflow_stage": "",
  "intent": "",
  "action": "speak|transfer|tool_call|save_data|end_call",
  "message": "",
  "lead_fields": {},
  "next_question": "",
  "tool_name": "",
  "tool_payload": {}
}
"""


async def run_tamil_sales_pack(
    *,
    agent_config: dict[str, Any],
    pack_state: dict[str, Any],
    user_text: str,
    transcript_context: str,
    language_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("[TAMIL_SALES_PACK] inference started")
    lc = language_config if isinstance(language_config, dict) else {}
    user_payload = json.dumps(
        {
            "language_config": lc,
            "current_workflow_stage": pack_state.get("workflow_stage") or "GREETING",
            "merged_lead_fields": pack_state.get("extracted_fields") or {},
            "transcript_tail": transcript_context,
            "latest_user_message": user_text,
            "business_type_hint": agent_config.get("business_type") or "",
        },
        ensure_ascii=True,
    )
    out = await groq_json_completion(system=SYSTEM, user=user_payload, model=DEFAULT_MODEL)
    if not out:
        logger.warning("[TAMIL_SALES_PACK] empty model output")
        return {}
    return out
