"""B2B sales vertical — Groq JSON orchestration output."""

from __future__ import annotations

import json
import logging
from typing import Any

from .groq_json import DEFAULT_MODEL, groq_json_completion

logger = logging.getLogger("outbound-agent.orchestration.packs")

STAGES = (
    "INTRO",
    "NEED_DISCOVERY",
    "QUALIFICATION",
    "OBJECTION_HANDLING",
    "DEMO_BOOKING",
    "FOLLOWUP",
    "CLOSE",
)

INTENTS = (
    "interested",
    "not_interested",
    "too_expensive",
    "competitor",
    "callback_request",
    "demo_request",
    "general",
)

SYSTEM = """You are a B2B sales voice-call orchestration brain. Output a single JSON object only.

Allowed workflow_stage: """ + ", ".join(STAGES) + """

Allowed intent: """ + ", ".join(INTENTS) + """

lead_fields must include:
- company_name, team_size, budget, urgency, decision_maker, interest_level (e.g. low/medium/high)

Rules:
- action: speak | transfer | end_call | save_data | noop
- transfer: user asks for human/account executive explicitly.
- end_call: user ends politely.
- save_data: qualified lead or demo booked / strong interest captured.
- message: short next line for the agent (1-2 sentences).

Return exactly:
{
  "workflow_stage": "<STAGE>",
  "intent": "<INTENT>",
  "action": "speak|transfer|end_call|save_data|noop",
  "message": "<text>",
  "lead_fields": { ... },
  "lead_score": 0
}
"""


async def run_sales_pack(
    *,
    agent_config: dict[str, Any],
    pack_state: dict[str, Any],
    user_text: str,
    transcript_context: str,
    language_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("[SALES_PACK] inference started")
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
        logger.warning("[SALES_PACK] empty model output")
        return {}
    return out
