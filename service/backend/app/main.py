"""FastAPI-приложение: сервис динамического ценообразования."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import catalog, db, pricing
from .rules import PROMO_LABELS, PROMO_ORDER, Policy
from .schemas import ApplyRequest

app = FastAPI(title="Dynamic Pricing Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    catalog.load_catalog()  # прогрев кэша / ранняя ошибка, если каталога нет


@app.get("/api/meta")
def get_meta() -> dict:
    m = catalog.meta()
    return {
        **m,
        "promo_labels": PROMO_LABELS,
        "promo_order": PROMO_ORDER,
        "n_stores": len(catalog.stores()),
    }


@app.get("/api/skus")
def get_skus() -> list[dict]:
    """Каталог с рекомендациями под текущую политику."""
    policy = db.get_policy()
    return pricing.optimize_all(policy)


@app.get("/api/skus/{upc}")
def get_sku_detail(upc: int) -> dict:
    sku = catalog.get_sku(upc)
    if sku is None:
        raise HTTPException(404, f"SKU {upc} не найден")
    policy = db.get_policy()
    # capacity-aware рекомендация (консистентно с таблицей /api/skus)
    rec = next((r for r in pricing.optimize_all(policy) if r["upc"] == upc), None)
    if rec is None:
        rec = pricing.optimize(sku, policy)
    curves = {
        promo: pricing.profit_curve(sku, promo, policy)
        for promo in PROMO_ORDER if promo in policy.allowed_promos
    }
    # история цен из каталога (seed)
    hist = [h for h in catalog.history() if h["upc"] == upc]
    return {
        "sku": sku,
        "recommendation": rec,
        "curves": curves,
        "history": hist,
        "store_meta": catalog.stores().get(str(sku["flagship_store"])),
    }


@app.get("/api/policy", response_model=Policy)
def read_policy() -> Policy:
    return db.get_policy()


@app.put("/api/policy", response_model=Policy)
def update_policy(policy: Policy) -> Policy:
    db.save_policy(policy)
    return policy


@app.post("/api/recommend")
def recommend(policy: Policy | None = None) -> dict:
    """Пересчёт рекомендаций под переданную политику (для живого превью слайдеров).

    Если тело пустое — берётся активная политика. НЕ сохраняет политику.
    """
    p = policy or db.get_policy()
    rows = pricing.optimize_all(p)
    return {"policy": p.model_dump(), "kpi": pricing.kpi(rows), "rows": rows}


@app.get("/api/kpi")
def get_kpi() -> dict:
    policy = db.get_policy()
    rows = pricing.optimize_all(policy)
    return pricing.kpi(rows)


@app.post("/api/apply")
def apply(req: ApplyRequest) -> dict:
    """Применить рекомендацию по SKU: пишет событие изменения цены (аудит)."""
    sku = catalog.get_sku(req.upc)
    if sku is None:
        raise HTTPException(404, f"SKU {req.upc} не найден")
    policy = db.get_policy()
    # capacity-aware рекомендация (консистентно с таблицей и деталью SKU)
    rec = next((r for r in pricing.optimize_all(policy) if r["upc"] == sku["upc"]), None)
    if rec is None:
        rec = pricing.optimize(sku, policy)
    reason = ", ".join(rec["binding_rules"]) or policy.objective.value
    db.add_price_event(
        upc=sku["upc"],
        description=sku["description"],
        store=req.store or sku["flagship_store"],
        old_price=rec["current_price"],
        new_price=rec["recommended_price"],
        old_promo=rec["current_promo"],
        new_promo=rec["recommended_promo"],
        uplift_pct=rec["profit_uplift_pct"],
        reason=reason,
    )
    return {"ok": True, "event": rec}


@app.post("/api/apply_all")
def apply_all() -> dict:
    """Применить все рекомендации с ненулевым изменением цены."""
    policy = db.get_policy()
    rows = pricing.optimize_all(policy)
    applied = 0
    for r in rows:
        if abs(r["price_change_pct"]) < 0.5 and r["recommended_promo"] == r["current_promo"]:
            continue
        reason = ", ".join(r["binding_rules"]) or policy.objective.value
        db.add_price_event(
            upc=r["upc"],
            description=r["description"],
            store=catalog.get_sku(r["upc"])["flagship_store"],
            old_price=r["current_price"],
            new_price=r["recommended_price"],
            old_promo=r["current_promo"],
            new_promo=r["recommended_promo"],
            uplift_pct=r["profit_uplift_pct"],
            reason=reason,
        )
        applied += 1
    return {"ok": True, "applied": applied}


@app.get("/api/history")
def history(limit: int = 200) -> dict:
    return {
        "events": db.list_price_events(limit),
        "series": catalog.history(),
    }
