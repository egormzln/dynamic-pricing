"""Pydantic-схемы запросов/ответов API."""
from __future__ import annotations

from pydantic import BaseModel

from .rules import Policy


class ApplyRequest(BaseModel):
    upc: int
    store: int | None = None


class RecommendResponse(BaseModel):
    policy: Policy
    kpi: dict
    rows: list[dict]
