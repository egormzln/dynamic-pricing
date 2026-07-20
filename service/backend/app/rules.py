"""Схема политики ценообразования (правила, редактируемые на ходу)."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

PROMO_ORDER = ["none", "tpr", "display", "feature", "feature_display"]
PROMO_LABELS = {
    "none": "Без промо",
    "tpr": "Скидка (TPR)",
    "display": "Выкладка",
    "feature": "Каталог",
    "feature_display": "Каталог + выкладка",
}


class Objective(str, Enum):
    profit = "profit"        # максимизация прибыли
    revenue = "revenue"      # максимизация выручки
    target_margin = "target_margin"  # держать целевую маржу


class PriceEnding(str, Enum):
    none = "none"
    p99 = "99"    # окончание .99
    p49 = "49"    # окончание .49 или .99 (charm pricing)


class Policy(BaseModel):
    """Активная политика. Хранится в SQLite, редактируется через API."""

    objective: Objective = Objective.profit

    # --- границы цены и маржи ---
    min_margin: float = Field(0.15, ge=0, le=2, description="Мин. наценка над cost, доля")
    max_discount: float = Field(0.40, ge=0, le=0.9, description="Макс. скидка от base_price, доля")
    max_markup: float = Field(0.25, ge=0, le=2, description="Макс. наценка над base_price, доля")
    respect_bounds: bool = Field(True, description="Ограничивать цену историческими p05..p95")

    # --- бизнес-цель target_margin ---
    target_margin_value: float = Field(0.35, ge=0, le=2, description="Целевая маржа для objective=target_margin")

    # --- промо-политика ---
    allowed_promos: list[str] = Field(default_factory=lambda: list(PROMO_ORDER))
    promo_capacity: dict[str, float] = Field(
        default_factory=lambda: {
            "tpr": 0.15,
            "display": 0.10,
            "feature": 0.10,
            "feature_display": 0.08,
        },
        description="Доля SKU, которым можно назначить данный тип промо (none без лимита)",
    )

    # --- округление и шаг ---
    price_ending: PriceEnding = PriceEnding.p99
    max_change_per_cycle: float = Field(
        0.20, ge=0.01, le=1.0, description="Макс. относительное изменение цены за цикл"
    )


def default_policy() -> Policy:
    return Policy()
