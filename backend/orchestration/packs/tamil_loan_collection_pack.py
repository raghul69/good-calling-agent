"""Tamil / Tanglish loan collections vertical — Groq JSON orchestration output."""

from __future__ import annotations

import json
import logging
from typing import Any

from .groq_json import DEFAULT_MODEL, groq_json_completion
from .loan_collection_pack import normalize_loan_risk

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

RISK_LEVELS = ("low", "medium", "high")

SYSTEM = """You are a Tamil / Tanglish loan collections voice-call orchestration brain. Output one JSON object only, no markdown.

Voice rules:
- Calm, respectful Chennai Tanglish; short lines; no threats; de-escalate; one question at a time.
- Confirm before transfer to legal/supervisor if policy requires.
- Escalate risk_level for abuse, legal threats, clear refusal—still keep message professional.

workflow_stage must be exactly one of: """ + ", ".join(STAGES) + """

risk_level must be one of: """ + ", ".join(RISK_LEVELS) + """

extracted keys: customer_name, loan_type, pending_amount, payment_date, payment_commitment, risk_level (mirror top-level risk_level).

action: speak | transfer | tool_call | save_data | end_call
- tool_call: tool_name + tool_payload when recording payment promise or callback in a system.
- save_data: promise_to_pay or material facts to log.

Include language "ta-IN" and tone "friendly_chennai_tanglish".

Return exactly:
{
  "language": "ta-IN",
  "tone": "friendly_chennai_tanglish",
  "workflow_stage": "",
  "intent": "",
  "risk_level": "low|medium|high",
  "action": "speak|transfer|tool_call|save_data|end_call",
  "message": "",
  "next_question": "",
  "extracted": {},
  "lead_fields": {},
  "tool_name": "",
  "tool_payload": {}
}
"""


async def run_tamil_loan_collection_pack(
    *,
    agent_config: dict[str, Any],
    pack_state: dict[str, Any],
    user_text: str,
    transcript_context: str,
    language_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("[TAMIL_LOAN_COLLECTION_PACK] inference started")
    lc = language_config if isinstance(language_config, dict) else {}
    user_payload = json.dumps(
        {
            "language_config": lc,
            "current_workflow_stage": pack_state.get("workflow_stage") or "GREETING",
            "merged_extracted": pack_state.get("extracted_fields") or {},
            "transcript_tail": transcript_context,
            "latest_user_message": user_text,
            "business_type_hint": agent_config.get("business_type") or "",
        },
        ensure_ascii=True,
    )
    out = await groq_json_completion(system=SYSTEM, user=user_payload, model=DEFAULT_MODEL)
    if not out:
        logger.warning("[TAMIL_LOAN_COLLECTION_PACK] empty model output")
        return {}
    if isinstance(out, dict):
        out["risk_level"] = normalize_loan_risk(out.get("risk_level"))
    return out
