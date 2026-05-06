"""Loan collection vertical — Groq JSON orchestration output."""

from __future__ import annotations

import json
import logging
from typing import Any

from .groq_json import DEFAULT_MODEL, groq_json_completion

logger = logging.getLogger("outbound-agent.orchestration.packs")

STAGES = (
    "VERIFY_CUSTOMER",
    "VERIFY_PAYMENT_STATUS",
    "PAYMENT_REMINDER",
    "PAYMENT_DATE_CAPTURE",
    "ESCALATION",
    "CALLBACK",
    "SETTLEMENT_DISCUSSION",
    "END",
)

INTENTS = (
    "promise_to_pay",
    "dispute",
    "callback_request",
    "settlement_request",
    "refusal",
    "escalation",
    "general",
)

RISK_LEVELS = ("low", "medium", "high")

SYSTEM = """You are a loan collections voice-call orchestration brain. Output a single JSON object only.

Allowed workflow_stage: """ + ", ".join(STAGES) + """

Allowed intent: """ + ", ".join(INTENTS) + """

risk_level must be one of: """ + ", ".join(RISK_LEVELS) + """

extracted object keys (strings unless boolean):
- customer_name, loan_type, pending_amount, payment_date, payment_commitment, risk_level

Rules:
- Escalate risk_level for threats, abuse, legal threats, or clear refusal to pay.
- action: speak | transfer | end_call | save_data | noop
- transfer: escalation or user demands supervisor/human (if policy would route to human).
- end_call: polite closure or user ends call.
- save_data: promise_to_pay with date captured or settlement discussion outcome worth logging.
- message: short next assistant line (1-2 sentences).

Return exactly:
{
  "workflow_stage": "<STAGE>",
  "intent": "<INTENT>",
  "risk_level": "low|medium|high",
  "action": "speak|transfer|end_call|save_data|noop",
  "message": "<text>",
  "extracted": {
     "customer_name": "",
     "loan_type": "",
     "pending_amount": "",
     "payment_date": "",
     "payment_commitment": "",
     "risk_level": ""
  },
  "lead_score": 0
}
"""


async def run_loan_collection_pack(
    *,
    agent_config: dict[str, Any],
    pack_state: dict[str, Any],
    user_text: str,
    transcript_context: str,
    language_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("[LOAN_COLLECTION_PACK] inference started")
    user_payload = json.dumps(
        {
            "current_workflow_stage": pack_state.get("workflow_stage") or "VERIFY_CUSTOMER",
            "merged_extracted": pack_state.get("extracted_fields") or {},
            "transcript_tail": transcript_context,
            "latest_user_message": user_text,
            "business_type_hint": agent_config.get("business_type") or "",
        },
        ensure_ascii=True,
    )
    out = await groq_json_completion(system=SYSTEM, user=user_payload, model=DEFAULT_MODEL)
    if not out:
        logger.warning("[LOAN_COLLECTION_PACK] empty model output")
        return {}
    return out


def normalize_loan_risk(raw: str | None) -> str:
    v = (raw or "").strip().lower()
    if v in RISK_LEVELS:
        return v
    return "low"
