"""Central decision policy: STT text in → structured `AgentAction` out."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any

import pytz

from backend.orchestration.conversation_understanding import run_conversation_understanding
from backend.orchestration.packs import get_pack, normalize_vertical
from backend.orchestration.packs.loan_collection_pack import normalize_loan_risk
from backend.orchestration.schemas import AgentAction, AgentSessionState
from backend.orchestration.state_store import OrchestrationStateStore
from backend.orchestration.tool_executor import ToolExecutor
from backend.orchestration.transfer_manager import TransferManager

logger = logging.getLogger("outbound-agent.orchestration")

_CONFUSION_RE = re.compile(
    r"\b(hello+|not\s+clear|speak\s+properly|speak\s+clearly|i\s+don'?t\s+understand|"
    r"i\s+dont\s+understand|puriyala|theriyala|clear\s+ah\s+illa|seria\s+pesu)\b",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(r"[?？]\s*$|\b(sollunga|tell me|pannalama|prefer|interest)\b", re.IGNORECASE)


def _float_safe(x: Any) -> float | None:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _norm_voice(text: str) -> str:
    return re.sub(r"[^a-z0-9\u0b80-\u0bff]+", " ", str(text or "").lower()).strip()


def _is_confusion(text: str) -> bool:
    t = str(text or "").strip()
    low = _norm_voice(t)
    return bool(_CONFUSION_RE.search(t)) or low in {"hello", "hello hello", "hello sir", "hello madam"}


class AgentOrchestrator:
    def __init__(
        self,
        *,
        agent_config: dict[str, Any],
        call_config: dict[str, Any],
        tools_config: list[dict[str, Any]] | Any,
        call_id: str,
        room_name: str,
        user_id: str,
        org_id: str,
        transfer_manager: TransferManager,
        state_store: OrchestrationStateStore | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self._agent_config = agent_config if isinstance(agent_config, dict) else {}
        self._call_config = call_config if isinstance(call_config, dict) else {}
        self._tools_config = tools_config if isinstance(tools_config, list) else []
        self._call_id = call_id
        self._room_name = room_name
        self._user_id = user_id or ""
        self._org_id = org_id or ""
        self._transfer_manager = transfer_manager
        self._state_store = state_store
        self._tool_executor = tool_executor or ToolExecutor()
        self._state = AgentSessionState()
        self._pack_ctx: dict[str, Any] = {"workflow_stage": None, "extracted_fields": {}}

    def start_session(self) -> None:
        self._state.started_at = time.time()
        self._state.call_status = "active"
        self._state.current_stage = "live"
        nv = normalize_vertical(self._agent_config.get("vertical"))
        if self._state_store and nv:
            self._state_store.set_pack_snapshot(vertical=nv)
            self._state_store.persist()
        vr = (self._agent_config.get("vertical") or "").strip().lower()
        if vr.startswith("tamil_"):
            logger.info("[TAMIL_ORCH] vertical=%s language_config=%s", vr, self._agent_config.get("language_config"))
        logger.info("[ORCHESTRATOR] session_started call_id=%s room=%s", self._call_id, self._room_name)

    def handle_interruption(self) -> None:
        self._state.interruption_count += 1
        logger.debug("[ORCHESTRATOR] interruption n=%s", self._state.interruption_count)

    def end_session(self) -> None:
        if self._state.ended_at is not None:
            return
        self._state.ended_at = time.time()
        self._state.call_status = "ended"
        self._state.current_stage = "ended"
        if self._state_store:
            self._state_store.set_status("ended")
            self._state_store.flush()
        logger.info("[ORCHESTRATOR] session_ended call_id=%s", self._call_id)

    def _enabled_tool_ids(self) -> set[str]:
        out: set[str] = set()
        for x in self._tools_config:
            if isinstance(x, dict) and x.get("enabled"):
                tid = str(x.get("id", "")).strip()
                if tid:
                    out.add(tid)
        return out

    def _append_transcript(self, text: str, role: str = "user") -> None:
        line = {"role": role, "content": text}
        self._state.transcript.append(line)
        self._state.last_user_message = text if role == "user" else self._state.last_user_message
        if self._state_store and role == "user":
            self._state_store.append_user_text(text)

    def _transcript_tail(self, max_lines: int = 10) -> str:
        lines = self._state.transcript[-max_lines:]
        return "\n".join(f"{x.get('role', '?')}: {x.get('content', '')}" for x in lines)

    def _record_action(self, action: AgentAction) -> None:
        if self._state_store:
            self._state_store.record_action(
                {
                    "type": action.type,
                    "tool": action.tool_name,
                    "reason": action.reason,
                    "intent": action.intent,
                    "workflow_stage": action.workflow_stage,
                }
            )
            self._state_store.persist()

    def _log_lead_extracted(self, fields: dict[str, Any]) -> None:
        keys = [k for k, v in fields.items() if v not in (None, "", [], {})]
        logger.info("[LEAD_EXTRACTED] call_id=%s keys=%s n=%s", self._call_id, ",".join(sorted(keys))[:300], len(keys))

    async def handle_user_message(self, text: str) -> AgentAction:
        t = (text or "").strip()
        logger.info("[ORCHESTRATOR] message_received call_id=%s len=%s", self._call_id, len(t))

        self._append_transcript(t, "user")

        if not t:
            act = AgentAction(type="noop")
            self._log_selected(act)
            self._record_action(act)
            return act

        if _is_confusion(t):
            act = AgentAction(
                type="speak",
                reason="confusion_recovery",
                intent="confused",
                orchestration_message="Sorry sir, simple-ah sollren. Which area looking?",
                workflow_stage=self._pack_ctx.get("workflow_stage") or "QUALIFICATION",
            )
            self._finalize_assistant_action(act)
            self._log_selected(act)
            self._record_action(act)
            return act

        # Guardrails first
        if self._detect_end_call_intent(t):
            act = AgentAction(type="end_call", reason="caller_intent")
            self._log_selected(act)
            self._record_action(act)
            return act

        if self._detect_transfer_intent(t):
            en = self._enabled_tool_ids()
            if "transfer_call" in en and self._transfer_manager.is_transfer_allowed():
                act = AgentAction(type="transfer", reason="caller_intent")
                self._state.transfer_requested = True
                self._log_selected(act)
                self._record_action(act)
                return act
            logger.info(
                "[ORCHESTRATOR] transfer_intent_ignored allowed_tool=%s tm_ok=%s",
                "transfer_call" in en,
                self._transfer_manager.is_transfer_allowed(),
            )

        vertical_key = normalize_vertical(self._agent_config.get("vertical"))
        pack_fn = get_pack(self._agent_config.get("vertical"))
        if pack_fn and vertical_key:
            lang_c = self._agent_config.get("language_config")
            lang_pass = lang_c if isinstance(lang_c, dict) else {}
            understanding: dict[str, Any] | None = None
            if vertical_key == "tamil_real_estate":
                understanding = await run_conversation_understanding(
                    user_text=t,
                    transcript_context=self._transcript_tail(),
                    pack_state=self._pack_ctx,
                )
                logger.info(
                    "[UNDERSTANDING] call_id=%s intent=%s interest=%s objection=%s next_action=%s human_transfer=%s",
                    self._call_id,
                    understanding.get("intent"),
                    understanding.get("interest_level"),
                    understanding.get("objection"),
                    understanding.get("next_action"),
                    understanding.get("human_transfer_needed"),
                )
                ob = (understanding.get("objection") or "").strip().lower()
                if ob and ob not in ("", "none", "unknown"):
                    logger.info("[OBJECTION_DETECTED] call_id=%s objection=%s", self._call_id, ob)
                self._pack_ctx["last_understanding"] = understanding
                raw = await pack_fn(
                    agent_config=self._agent_config,
                    pack_state=self._pack_ctx,
                    user_text=t,
                    transcript_context=self._transcript_tail(),
                    language_config=lang_pass,
                    understanding=understanding,
                )
            else:
                raw = await pack_fn(
                    agent_config=self._agent_config,
                    pack_state=self._pack_ctx,
                    user_text=t,
                    transcript_context=self._transcript_tail(),
                    language_config=lang_pass,
                )
            act = self._map_pack_output(vertical_key, raw)
            self._apply_pack_state(vertical_key, raw, act)
            self._finalize_assistant_action(act)
            if vertical_key == "tamil_real_estate" and act.type in (
                "save_data",
                "schedule_callback",
                "send_whatsapp",
            ):
                logger.info(
                    "[CONVERSION_ACTION] call_id=%s type=%s stage=%s intent=%s",
                    self._call_id,
                    act.type,
                    act.workflow_stage or "-",
                    act.intent or "-",
                )
            self._log_selected(act)
            self._record_action(act)
            return act

        tool_act = self._select_tool(t)
        if tool_act is not None:
            self._finalize_assistant_action(tool_act)
            self._log_selected(tool_act)
            self._record_action(tool_act)
            return tool_act

        if self._detect_save_data_intent(t):
            act = AgentAction(type="save_data", reason="caller_intent", payload={"note": t[:500]})
            self._log_selected(act)
            self._record_action(act)
            return act

        act = AgentAction(type="speak")
        self._finalize_assistant_action(act)
        self._log_selected(act)
        self._record_action(act)
        return act

    def _finalize_assistant_action(self, action: AgentAction) -> None:
        msg = (action.orchestration_message or action.next_question or "").strip()
        if not msg:
            return
        norm = _norm_voice(msg)
        last = _norm_voice(self._state.last_agent_message)
        repeated_question = bool(_QUESTION_RE.search(msg)) and norm == last
        if norm and (norm == last or repeated_question):
            logger.info("[ORCHESTRATOR] duplicate_question_guard text=%s", msg[:120])
            action.orchestration_message = "Seri sir, vera simple-ah: area preference irukka?"
            norm = _norm_voice(action.orchestration_message)
        self._state.last_agent_message = action.orchestration_message or action.next_question or msg
        self._append_transcript(self._state.last_agent_message, "assistant")
        if self._state_store:
            self._state_store.append_agent_text(self._state.last_agent_message)

    def _apply_pack_state(self, vertical_key: str, raw: dict[str, Any], act: AgentAction) -> None:
        if not raw:
            return
        prev_wf = self._pack_ctx.get("workflow_stage")
        wf = raw.get("workflow_stage") or act.workflow_stage
        intent = raw.get("intent") or act.intent
        if wf:
            logger.info(
                "[WORKFLOW_STAGE] call_id=%s vertical=%s transition=%s->%s",
                self._call_id,
                vertical_key,
                prev_wf,
                wf,
            )
        if str(wf or "").strip() == "WHATSAPP_CONFIRM":
            logger.info("[WHATSAPP_CONFIRM] call_id=%s intent=%s", self._call_id, intent or "-")
        if intent:
            logger.info("[INTENT_DETECTED] call_id=%s vertical=%s intent=%s", self._call_id, vertical_key, intent)

        if vertical_key in ("loan_collection", "tamil_loan_collection"):
            extracted = dict(raw.get("extracted") or {})
            risk = normalize_loan_risk((raw.get("risk_level") or extracted.get("risk_level") or act.risk_level))
            act.risk_level = risk
            self._pack_ctx["workflow_stage"] = wf
            self._pack_ctx["extracted_fields"] = {**self._pack_ctx.get("extracted_fields", {}), **extracted}
            self._log_lead_extracted(self._pack_ctx["extracted_fields"])
            ls = _float_safe(raw.get("lead_score"))
            act.lead_score = ls if ls is not None else act.lead_score
            if self._state_store:
                self._state_store.set_pack_snapshot(
                    vertical=vertical_key,
                    workflow_stage=str(wf) if wf else None,
                    intent=str(intent) if intent else None,
                    risk_level=risk,
                    lead_score=act.lead_score,
                    extracted_fields=self._pack_ctx["extracted_fields"],
                )
            return

        lf = dict(raw.get("lead_fields") or {})
        self._pack_ctx["workflow_stage"] = wf
        self._pack_ctx["extracted_fields"] = {**self._pack_ctx.get("extracted_fields", {}), **lf}
        self._log_lead_extracted(self._pack_ctx["extracted_fields"])
        ls = _float_safe(raw.get("lead_score"))
        if ls is not None:
            act.lead_score = ls
        if self._state_store:
            self._state_store.set_pack_snapshot(
                vertical=vertical_key,
                workflow_stage=str(wf) if wf else None,
                intent=str(intent) if intent else None,
                risk_level=act.risk_level,
                lead_score=act.lead_score,
                extracted_fields=self._pack_ctx["extracted_fields"],
            )

    @staticmethod
    def _tts_line_from_pack(raw: dict[str, Any]) -> str | None:
        m = str(raw.get("message") or "").strip()
        if m:
            return m
        nq = str(raw.get("next_question") or "").strip()
        return nq or None

    @staticmethod
    def _merge_lead_and_action_payload(raw: dict[str, Any]) -> dict[str, Any]:
        out = dict(raw.get("lead_fields") or {})
        ap = raw.get("action_payload")
        if isinstance(ap, dict):
            out.update(ap)
        return out

    def _map_pack_output(self, vertical_key: str, raw: dict[str, Any]) -> AgentAction:
        if not raw:
            return AgentAction(type="speak")

        action_s = str(raw.get("action") or "speak").strip().lower()
        next_q = str(raw.get("next_question") or "").strip() or None
        orch_lang = str(raw.get("language") or "").strip() or None
        orch_tone = str(raw.get("tone") or "").strip() or None
        msg = self._tts_line_from_pack(raw)
        wf = str(raw.get("workflow_stage") or "").strip() or None
        intent = str(raw.get("intent") or "").strip() or None
        risk = None
        if vertical_key in ("loan_collection", "tamil_loan_collection"):
            risk = normalize_loan_risk(raw.get("risk_level"))

        ls = _float_safe(raw.get("lead_score"))

        if action_s == "transfer":
            en = self._enabled_tool_ids()
            if "transfer_call" not in en or not self._transfer_manager.is_transfer_allowed():
                return AgentAction(
                    type="speak",
                    orchestration_message=msg or "I can connect you to our team one moment.",
                    workflow_stage=wf,
                    intent=intent,
                    risk_level=risk,
                    lead_score=ls,
                    reason="pack_transfer_blocked",
                    next_question=next_q,
                    orchestration_language=orch_lang,
                    orchestration_tone=orch_tone,
                )
            return AgentAction(
                type="transfer",
                reason=intent or "pack",
                orchestration_message=msg,
                workflow_stage=wf,
                intent=intent,
                risk_level=risk,
                lead_score=ls,
                next_question=next_q,
                orchestration_language=orch_lang,
                orchestration_tone=orch_tone,
            )

        if action_s == "end_call":
            return AgentAction(
                type="end_call",
                reason=intent or "pack",
                orchestration_message=msg,
                workflow_stage=wf,
                intent=intent,
                risk_level=risk,
                lead_score=ls,
                next_question=next_q,
                orchestration_language=orch_lang,
                orchestration_tone=orch_tone,
            )

        if action_s == "save_data":
            payload = dict(raw.get("lead_fields") or raw.get("extracted") or {})
            return AgentAction(
                type="save_data",
                reason=intent or "pack",
                payload=payload,
                orchestration_message=msg,
                workflow_stage=wf,
                intent=intent,
                risk_level=risk,
                lead_score=ls,
                next_question=next_q,
                orchestration_language=orch_lang,
                orchestration_tone=orch_tone,
            )

        if action_s == "schedule_callback":
            pl = self._merge_lead_and_action_payload(raw)
            return AgentAction(
                type="schedule_callback",
                reason=intent or "pack",
                payload=pl,
                orchestration_message=msg,
                workflow_stage=wf,
                intent=intent,
                risk_level=risk,
                lead_score=ls,
                next_question=next_q,
                orchestration_language=orch_lang,
                orchestration_tone=orch_tone,
            )

        if action_s == "send_whatsapp":
            pl = self._merge_lead_and_action_payload(raw)
            return AgentAction(
                type="send_whatsapp",
                reason=intent or "pack",
                payload=pl,
                orchestration_message=msg,
                workflow_stage=wf,
                intent=intent,
                risk_level=risk,
                lead_score=ls,
                next_question=next_q,
                orchestration_language=orch_lang,
                orchestration_tone=orch_tone,
            )

        if action_s == "tool_call":
            tn = str(raw.get("tool_name") or "").strip()
            tp = raw.get("tool_payload")
            if not isinstance(tp, dict):
                tp = {}
            return AgentAction(
                type="tool_call",
                tool_name=tn or None,
                payload=tp,
                reason=intent or "pack",
                orchestration_message=msg,
                workflow_stage=wf,
                intent=intent,
                risk_level=risk,
                lead_score=ls,
                next_question=next_q,
                orchestration_language=orch_lang,
                orchestration_tone=orch_tone,
            )

        if action_s == "noop":
            return AgentAction(
                type="noop",
                workflow_stage=wf,
                intent=intent,
                risk_level=risk,
                lead_score=ls,
                next_question=next_q,
                orchestration_language=orch_lang,
                orchestration_tone=orch_tone,
            )

        return AgentAction(
            type="speak",
            orchestration_message=msg,
            workflow_stage=wf,
            intent=intent,
            risk_level=risk,
            lead_score=ls,
            next_question=next_q,
            orchestration_language=orch_lang,
            orchestration_tone=orch_tone,
        )

    def _log_selected(self, action: AgentAction) -> None:
        logger.info(
            "[ORCHESTRATOR] action_selected type=%s tool=%s intent=%s stage=%s",
            action.type,
            action.tool_name or "-",
            action.intent or "-",
            action.workflow_stage or "-",
        )

    def _detect_end_call_intent(self, text: str) -> bool:
        low = text.lower()
        return bool(
            re.search(r"\b(bye|goodbye|end the call|hang\s*up|disconnect|that'?s all|no thanks|stop)\b", low)
        )

    def _detect_transfer_intent(self, text: str) -> bool:
        low = text.lower()
        return bool(
            re.search(
                r"\b(transfer me|talk to a human|human agent|real person|representative|speak to someone|call a person|manager\s+kitta\s+connect\s+pannunga|manager\s+kitta|connect\s+pannunga)\b",
                low,
            )
        )

    def _detect_save_data_intent(self, text: str) -> bool:
        low = text.lower()
        return bool(re.search(r"\b(save my (details|info|number)|contact me at|my email is|reach me at)\b", low))

    def _extract_iso_date(self, text: str) -> str | None:
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if m:
            return m.group(1)
        low = text.lower()
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)
        if "tomorrow" in low:
            return (now + timedelta(days=1)).strftime("%Y-%m-%d")
        if "today" in low:
            return now.strftime("%Y-%m-%d")
        return None

    def _select_tool(self, text: str) -> AgentAction | None:
        en = self._enabled_tool_ids()
        low = text.lower()

        if "check_availability" in en and re.search(
            r"\b(availability|available|slot|slots|open|free time|calendar)\b", low
        ):
            d = self._extract_iso_date(text) or datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d")
            return AgentAction(type="tool_call", tool_name="check_availability", payload={"date": d})

        if "save_booking_intent" in en and re.search(
            r"\b(book|booking|appointment|schedule|reserve|demo|meeting)\b", low
        ):
            return AgentAction(
                type="tool_call",
                tool_name="save_booking_intent",
                payload={"hint": text[:300]},
            )

        if "get_business_hours" in en and re.search(r"\b(open|close|hours|when are you)\b", low):
            return AgentAction(type="tool_call", tool_name="get_business_hours", payload={})

        return None
