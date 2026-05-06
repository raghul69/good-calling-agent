"""Vertical pack registry for AgentOrchestrator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .loan_collection_pack import run_loan_collection_pack
from .real_estate_pack import run_real_estate_pack
from .sales_pack import run_sales_pack
from .tamil_loan_collection_pack import run_tamil_loan_collection_pack
from .tamil_real_estate_pack import run_tamil_real_estate_pack
from .tamil_sales_pack import run_tamil_sales_pack

PackFn = Callable[..., Awaitable[dict[str, Any]]]

VERTICAL_PACKS: dict[str, PackFn] = {
    "real_estate": run_real_estate_pack,
    "loan_collection": run_loan_collection_pack,
    "sales": run_sales_pack,
    "tamil_real_estate": run_tamil_real_estate_pack,
    "tamil_sales": run_tamil_sales_pack,
    "tamil_loan_collection": run_tamil_loan_collection_pack,
}


def normalize_vertical(raw: str | None) -> str | None:
    if not raw:
        return None
    v = raw.strip().lower()
    if v in ("loan", "loans", "collections"):
        return "loan_collection"
    if v == "tamil_re":
        return "tamil_real_estate"
    return v if v in VERTICAL_PACKS else None


def get_pack(vertical: str | None) -> PackFn | None:
    nv = normalize_vertical(vertical)
    if not nv:
        return None
    return VERTICAL_PACKS.get(nv)
