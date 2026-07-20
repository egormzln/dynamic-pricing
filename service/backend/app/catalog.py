"""Загрузка каталога (data/catalog.json) в память."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    if not DATA.exists():
        raise FileNotFoundError(
            f"Каталог не найден: {DATA}. Сначала запустите scripts/build_catalog.py"
        )
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def sku_index() -> dict[int, dict]:
    return {s["upc"]: s for s in load_catalog()["skus"]}


def get_sku(upc: int) -> dict | None:
    return sku_index().get(upc)


def all_skus() -> list[dict]:
    return load_catalog()["skus"]


def meta() -> dict:
    return load_catalog()["meta"]


def stores() -> dict:
    return load_catalog()["stores"]


def history() -> list[dict]:
    return load_catalog()["history"]


def promo_lift_log() -> dict[str, float]:
    return meta()["promo_lift_log"]
