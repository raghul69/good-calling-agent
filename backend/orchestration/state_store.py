"""Persist orchestration snapshot to Supabase when the table exists; otherwise warn once."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger("outbound-agent.orchestration.state")


class OrchestrationStateStore:
    TABLE = "orchestration_session_state"

    def __init__(
        self,
        *,
        call_id: str,
        agent_id: str | None,
        org_id: str | None,
        user_id: str | None,
        room_name: str,
    ) -> None:
        self.call_id = call_id
        self.agent_id = agent_id
        self.org_id = org_id or ""
        self.user_id = user_id or ""
        self.room_name = room_name
        self._transcript_lines: list[dict[str, str]] = []
        self._action_history: list[dict[str, Any]] = []
        self._collected_fields: dict[str, Any] = {}
        self._call_status = "active"
        self._warned_unavailable = False
        self._last_persist = 0.0
        self._vertical: str | None = None
        self._workflow_stage: str | None = None
        self._intent: str | None = None
        self._risk_level: str | None = None
        self._lead_score: float | None = None
        self._extracted_fields: dict[str, Any] = {}

    def append_user_text(self, text: str) -> None:
        self._transcript_lines.append({"role": "user", "content": text, "ts": time.time()})

    def append_agent_text(self, text: str) -> None:
        self._transcript_lines.append({"role": "assistant", "content": text, "ts": time.time()})

    def record_action(self, action: dict[str, Any]) -> None:
        self._action_history.append(action)

    def merge_collected(self, fields: dict[str, Any]) -> None:
        self._collected_fields.update(fields)

    def set_status(self, status: str) -> None:
        self._call_status = status

    def set_pack_snapshot(
        self,
        *,
        vertical: str | None = None,
        workflow_stage: str | None = None,
        intent: str | None = None,
        risk_level: str | None = None,
        lead_score: float | None = None,
        extracted_fields: dict[str, Any] | None = None,
    ) -> None:
        if vertical is not None:
            self._vertical = vertical
        if workflow_stage is not None:
            self._workflow_stage = workflow_stage
        if intent is not None:
            self._intent = intent
        if risk_level is not None:
            self._risk_level = risk_level
        if lead_score is not None:
            self._lead_score = lead_score
        if extracted_fields:
            self._extracted_fields.update(extracted_fields)

    def snapshot_payload(self) -> dict[str, Any]:
        # collected_fields kept for backward compatibility; extracted_fields is canonical for vertical packs
        merged_extracted = dict(self._extracted_fields)
        if self._collected_fields:
            merged_extracted = {**self._collected_fields, **merged_extracted}
        return {
            "call_id": self.call_id,
            "agent_id": self.agent_id,
            "org_id": self.org_id or None,
            "user_id": self.user_id or None,
            "room_name": self.room_name,
            "transcript": json.dumps(self._transcript_lines, ensure_ascii=True),
            "action_history": json.dumps(self._action_history, ensure_ascii=True, default=str),
            "call_status": self._call_status,
            "collected_fields": json.dumps(self._collected_fields, ensure_ascii=True, default=str),
            "vertical": self._vertical,
            "workflow_stage": self._workflow_stage,
            "intent": self._intent,
            "risk_level": self._risk_level,
            "lead_score": self._lead_score,
            "extracted_fields": json.dumps(merged_extracted, ensure_ascii=True, default=str),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def persist(self) -> None:
        """Best-effort upsert. Skips if Supabase missing or table not deployed."""
        try:
            import backend.db as db

            sb = db.get_supabase(service_role=True)
            if not sb:
                self._warn_once("Supabase client unavailable — orchestration state not persisted")
                return
            row = self.snapshot_payload()
            sb.table(self.TABLE).upsert(row).execute()
            self._last_persist = time.time()
        except Exception as e:
            err = str(e).lower()
            if "relation" in err or "does not exist" in err or "42p01" in err or "column" in err:
                self._warn_once(f"Table {self.TABLE} missing or schema mismatch — run optional SQL migration")
            else:
                logger.debug("[ORCHESTRATION_STATE] persist skipped: %s", e)

    def flush(self) -> None:
        self.persist()

    def _warn_once(self, msg: str) -> None:
        if self._warned_unavailable:
            return
        self._warned_unavailable = True
        logger.warning("[ORCHESTRATION_STATE] %s", msg)
