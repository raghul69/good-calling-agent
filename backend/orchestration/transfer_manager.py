"""Resolve and validate SIP/PSTN transfer destinations without exposing full numbers in logs."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("outbound-agent.orchestration.transfer")


def mask_e164_for_log(e164: str) -> str:
    """Show country hint + last 3 digits only (never full number)."""
    s = (e164 or "").strip().replace(" ", "").replace("-", "")
    if not s.startswith("+") or len(s) < 5:
        return "[invalid]"
    tail = s[-3:]
    cc_len = min(3, max(1, len(s) - 3 - 3))
    return f"+{'*' * cc_len}…{tail}"


def validate_e164(raw: str) -> bool:
    """
    E.164: leading +, then 8–15 digits. Reject spaces/dashes inside the string.
    """
    inner = (raw or "").strip()
    if " " in inner or "-" in inner:
        return False
    if not inner.startswith("+"):
        return False
    digits = inner[1:]
    if not digits.isdigit():
        return False
    return 8 <= len(digits) <= 15


class TransferManager:
    """Reads call_config then DEFAULT_TRANSFER_NUMBER; validates E.164 for safe routing."""

    def __init__(self, call_config: dict[str, Any] | None = None) -> None:
        self._call_config = call_config if isinstance(call_config, dict) else {}
        cc = self._call_config
        raw = (cc.get("transfer_destination_e164") or "").strip()
        if raw:
            self._source = "call_config"
            self._raw_e164: str | None = raw
        else:
            env_raw = (os.getenv("DEFAULT_TRANSFER_NUMBER", "") or "").strip()
            if env_raw:
                self._source = "env"
                self._raw_e164 = env_raw
            else:
                self._source = "disabled"
                self._raw_e164 = None
        logger.info(
            "[TRANSFER_CONFIG] source=%s destination_set=%s mask=%s",
            self._source,
            str(bool(self._raw_e164)).lower(),
            mask_e164_for_log(self._raw_e164 or "+000"),
        )

    def get_raw_e164(self) -> str | None:
        return self._raw_e164

    def is_transfer_allowed(self) -> bool:
        raw = self._raw_e164
        return bool(raw and validate_e164(raw))

    def effective_destination_for_sip(self, sip_domain: str | None) -> str | None:
        """
        Match AgentTools.transfer_call: optional Vobiz sip: user@domain, else sip prefix.
        """
        raw = self._raw_e164
        if not raw or not validate_e164(raw):
            return None
        destination = raw
        domain = (sip_domain or "").strip()
        if domain and "@" not in destination:
            clean_dest = destination.replace("tel:", "").replace("sip:", "")
            destination = f"sip:{clean_dest}@{domain}"
        elif destination and not destination.startswith("sip:"):
            destination = f"sip:{destination}"
        return destination
