"""Barge-in helpers for cancelling agent speech when the caller interrupts."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("outbound-agent.barge_in")


class BargeInController:
    def __init__(self) -> None:
        self.latest_user_transcript = ""
        self.interrupt_count = 0
        self.last_interrupt_started_at: float | None = None

    def note_user_speech(self, text: str) -> None:
        self.latest_user_transcript = str(text or "").strip()

    def interrupt(self, session: Any, response_task: asyncio.Task[Any] | None = None, *, reason: str = "user_speech") -> None:
        self.interrupt_count += 1
        self.last_interrupt_started_at = time.perf_counter()
        cancelled = False
        try:
            session.interrupt(force=True)
        except Exception as e:
            logger.debug("[BARGE_IN] session interrupt failed reason=%s err=%s", reason, e)
        if response_task is not None and not response_task.done():
            response_task.cancel()
            cancelled = True
        recovery_ms = int((time.perf_counter() - self.last_interrupt_started_at) * 1000)
        logger.info(
            "[BARGE_IN_TRIGGERED] reason=%s count=%s response_task_cancelled=%s recovery_ms=%s",
            reason,
            self.interrupt_count,
            cancelled,
            recovery_ms,
        )
