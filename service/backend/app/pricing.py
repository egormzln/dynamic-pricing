"""Движок ценообразования: демодель, оптимизатор цены×промо, применение правил.

Экономика (serving поверх сохранённых коэффициентов, как ноутбук 06_02):
    units(p, promo) = base_units · (p/base_price)^ε · exp(promo_lift[promo])
    profit          = (p − cost) · units
    revenue         = p · units
"""
from __future__ import annotations

import math

from . import catalog
from .rules import PROMO_ORDER, Objective, PriceEnding, Policy

N_GRID = 60


# --------------------------------------------------------------------------- #
#  Демодель
# --------------------------------------------------------------------------- #
def demand(sku: dict, price: float, promo: str) -> float:
    lift = catalog.promo_lift_log().get(promo, 0.0)
    ratio = price / sku["base_price"]
    return sku["base_units"] * (ratio ** sku["elasticity"]) * math.exp(lift)


def profit(sku: dict, price: float, promo: str) -> float:
    return (price - sku["cost"]) * demand(sku, price, promo)


def revenue(sku: dict, price: float, promo: str) -> float:
    return price * demand(sku, price, promo)


# --------------------------------------------------------------------------- #
#  Округление цены под правило окончаний
# --------------------------------------------------------------------------- #
def _snap_ending(price: float, ending: PriceEnding) -> float:
    if ending == PriceEnding.none:
        return round(price, 2)
    if ending == PriceEnding.p99:
        allowed = [0.99]
    else:  # p49 → .49 и .99
        allowed = [0.49, 0.99]
    whole = math.floor(price)
    cands = []
    for w in (whole - 1, whole, whole + 1):
        for cents in allowed:
            cands.append(round(w + cents, 2))
    cands = [c for c in cands if c > 0]
    return min(cands, key=lambda c: abs(c - price))


# --------------------------------------------------------------------------- #
#  Границы цены под политику
# --------------------------------------------------------------------------- #
def price_window(sku: dict, promo: str, policy: Policy, current_price: float) -> dict:
    """Возвращает {floor, ceiling, floor_reason, ceiling_reason}."""
    cost = sku["cost"]
    bp = sku["base_price"]

    floor_candidates = [
        (cost * (1 + policy.min_margin), "min_margin"),
        (bp * (1 - policy.max_discount), "max_discount"),
        (current_price * (1 - policy.max_change_per_cycle), "max_change"),
    ]
    ceil_candidates = [
        (bp * (1 + policy.max_markup), "max_markup"),
        (current_price * (1 + policy.max_change_per_cycle), "max_change"),
    ]
    if policy.respect_bounds:
        b = (sku.get("bounds") or {}).get(promo)
        if b:
            floor_candidates.append((b["p05"], "hist_bounds"))
            ceil_candidates.append((b["p95"], "hist_bounds"))

    floor, floor_reason = max(floor_candidates, key=lambda x: x[0])
    ceiling, ceil_reason = min(ceil_candidates, key=lambda x: x[0])

    # Если коридор схлопнулся (floor > ceiling) — комбинация (цена×промо) недопустима
    # под текущей политикой. НЕ форсим точку вне реалистичного диапазона: помечаем
    # feasible=False, и такой вариант промо отбраковывается в _best_price_for_promo.
    return {
        "floor": round(floor, 2),
        "ceiling": round(ceiling, 2),
        "floor_reason": floor_reason,
        "ceiling_reason": ceil_reason,
        "feasible": floor <= ceiling + 1e-6,
    }


def _objective_value(sku: dict, price: float, promo: str, policy: Policy) -> float:
    if policy.objective == Objective.revenue:
        return revenue(sku, price, promo)
    if policy.objective == Objective.target_margin:
        margin = (price - sku["cost"]) / price if price > 0 else -1
        # чем ближе к целевой марже, тем лучше (максимизируем −|Δ|)
        return -abs(margin - policy.target_margin_value)
    return profit(sku, price, promo)  # profit по умолчанию


def _best_price_for_promo(sku: dict, promo: str, policy: Policy, current_price: float) -> dict | None:
    win = price_window(sku, promo, policy, current_price)
    if not win["feasible"]:
        return None  # правила несовместимы для этого промо → вариант недопустим
    lo, hi = win["floor"], win["ceiling"]
    if hi <= 0:
        return None
    if hi <= lo:
        grid = [lo]
    else:
        step = (hi - lo) / (N_GRID - 1)
        grid = [lo + i * step for i in range(N_GRID)]

    best = None
    seen = set()
    for raw in grid:
        p = _snap_ending(raw, policy.price_ending)
        p = min(max(p, lo), hi)
        p = round(p, 2)
        if p in seen:
            continue
        seen.add(p)
        val = _objective_value(sku, p, promo, policy)
        if best is None or val > best["obj"]:
            best = {"obj": val, "price": p}
    if best is None:
        return None
    p = best["price"]
    return _candidate(sku, p, promo, win, best["obj"])


def _candidate(sku: dict, p: float, promo: str, win: dict, obj: float) -> dict:
    return {
        "promo": promo,
        "price": round(p, 2),
        "units": round(demand(sku, p, promo), 2),
        "profit": round(profit(sku, p, promo), 2),
        "revenue": round(revenue(sku, p, promo), 2),
        "margin": round((p - sku["cost"]) / p, 4) if p > 0 else 0.0,
        "window": win,
        "obj": obj,
    }


def _noop_candidate(sku: dict, policy: Policy, cur_price: float, cur_promo: str) -> dict:
    """Гарантированный fallback «оставить как есть» — если политика несовместима ни с чем."""
    win = {"floor": cur_price, "ceiling": cur_price,
           "floor_reason": "no_change", "ceiling_reason": "no_change", "feasible": True}
    obj = _objective_value(sku, cur_price, cur_promo, policy)
    return _candidate(sku, cur_price, cur_promo, win, obj)


# --------------------------------------------------------------------------- #
#  Оптимизация одного SKU (без capacity — для детальной страницы)
# --------------------------------------------------------------------------- #
def optimize(sku: dict, policy: Policy, current_price: float | None = None,
             current_promo: str | None = None) -> dict:
    cur_price = current_price if current_price is not None else sku["current_price"]
    cur_promo = current_promo if current_promo is not None else sku["current_promo"]

    allowed = [p for p in PROMO_ORDER if p in policy.allowed_promos] or ["none"]
    candidates = [c for p in allowed if (c := _best_price_for_promo(sku, p, policy, cur_price))]
    candidates.append(_noop_candidate(sku, policy, cur_price, cur_promo))  # всегда есть fallback
    best = max(candidates, key=lambda c: c["obj"])

    base_units = demand(sku, cur_price, cur_promo)
    base_profit = (cur_price - sku["cost"]) * base_units
    base_revenue = cur_price * base_units

    profit_uplift = _pct(best["profit"], base_profit)
    revenue_uplift = _pct(best["revenue"], base_revenue)

    binding = _binding_rules(best["price"], best["window"])

    return {
        "upc": sku["upc"],
        "description": sku["description"],
        "category": sku["category"],
        "elasticity": sku["elasticity"],
        "elasticity_source": sku["elasticity_source"],
        "cost": sku["cost"],
        "base_price": sku["base_price"],
        "current_price": round(cur_price, 2),
        "current_promo": cur_promo,
        "recommended_price": best["price"],
        "recommended_promo": best["promo"],
        "price_change_pct": _pct(best["price"], cur_price),
        "expected_units": best["units"],
        "expected_profit": best["profit"],
        "expected_revenue": best["revenue"],
        "expected_margin": best["margin"],
        "baseline_profit": round(base_profit, 2),
        "baseline_revenue": round(base_revenue, 2),
        "profit_uplift_pct": profit_uplift,
        "revenue_uplift_pct": revenue_uplift,
        "window": best["window"],
        "binding_rules": binding,
    }


def profit_curve(sku: dict, promo: str, policy: Policy, current_price: float | None = None,
                 n: int = 40) -> list[dict]:
    """Кривая прибыли/выручки по цене для графика в UI."""
    cur = current_price if current_price is not None else sku["current_price"]
    win = price_window(sku, promo, policy, cur)
    b = (sku.get("bounds") or {}).get(promo)
    lo = min(win["floor"], b["p05"] if b else win["floor"]) * 0.9
    hi = max(win["ceiling"], b["p95"] if b else win["ceiling"]) * 1.1
    step = (hi - lo) / (n - 1)
    out = []
    for i in range(n):
        p = round(lo + i * step, 2)
        out.append({
            "price": p,
            "units": round(demand(sku, p, promo), 2),
            "profit": round(profit(sku, p, promo), 2),
            "revenue": round(revenue(sku, p, promo), 2),
            "feasible": win["floor"] <= p <= win["ceiling"],
        })
    return out


# --------------------------------------------------------------------------- #
#  Оптимизация всего каталога с capacity-жадным распределением промо
#  (перенос логики joint_optimize_constrained, Cell 7)
# --------------------------------------------------------------------------- #
def optimize_all(policy: Policy) -> list[dict]:
    skus = catalog.all_skus()
    allowed = [p for p in PROMO_ORDER if p in policy.allowed_promos] or ["none"]

    # для каждого SKU — лучшая цена/прибыль по КАЖДОМУ разрешённому промо
    per_sku_promo: list[dict] = []
    for sku in skus:
        cur_price = sku["current_price"]
        cur_promo = sku["current_promo"]
        base_units = demand(sku, cur_price, cur_promo)
        base_profit = (cur_price - sku["cost"]) * base_units
        best_by_promo = {}
        for p in allowed:
            r = _best_price_for_promo(sku, p, policy, cur_price)
            if r:
                best_by_promo[p] = r
        per_sku_promo.append({
            "sku": sku,
            "cur_price": cur_price,
            "cur_promo": cur_promo,
            "base_profit": base_profit,
            "base_units": base_units,
            "by_promo": best_by_promo,
        })

    n = len(skus)
    # capacity в слотах
    capacity_slots = {
        p: int(math.floor(policy.promo_capacity.get(p, 0.0) * n))
        for p in allowed if p != "none"
    }

    # старт: каждому SKU строго БЕЗ промо (репрайс при промо "none").
    # Промо-слоты раздаёт только жадный проход ниже — так capacity ограничивает
    # ОБЩЕЕ число SKU на каждом промо, включая исторически промотируемые.
    assignment: dict[int, dict] = {}
    for row in per_sku_promo:
        base = row["by_promo"].get("none")
        if base is None:
            # none недопустим под политикой → оставляем текущую цену, но без промо-слота
            base = _candidate(
                row["sku"], row["cur_price"], "none",
                {"floor": row["cur_price"], "ceiling": row["cur_price"],
                 "floor_reason": "no_change", "ceiling_reason": "no_change", "feasible": True},
                _objective_value(row["sku"], row["cur_price"], "none", policy),
            )
        assignment[row["sku"]["upc"]] = base

    # жадно раздаём промо-слоты по маржинальному uplift относительно текущего назначения
    for promo, slots in capacity_slots.items():
        if slots <= 0:
            continue
        gains = []
        for row in per_sku_promo:
            cand = row["by_promo"].get(promo)
            if cand is None:
                continue
            cur = assignment[row["sku"]["upc"]]
            gain = cand["profit"] - cur["profit"]
            if gain > 0:
                gains.append((gain, row["sku"]["upc"], cand))
        gains.sort(reverse=True, key=lambda x: x[0])
        for _, upc, cand in gains[:slots]:
            assignment[upc] = cand

    # собираем результат
    out = []
    for row in per_sku_promo:
        sku = row["sku"]
        best = assignment[sku["upc"]]
        base_profit = row["base_profit"]
        base_revenue = row["cur_price"] * row["base_units"]
        out.append({
            "upc": sku["upc"],
            "description": sku["description"],
            "category": sku["category"],
            "manufacturer": sku["manufacturer"],
            "elasticity": sku["elasticity"],
            "elasticity_source": sku["elasticity_source"],
            "cost": sku["cost"],
            "base_price": sku["base_price"],
            "current_price": round(row["cur_price"], 2),
            "current_promo": row["cur_promo"],
            "recommended_price": best["price"],
            "recommended_promo": best["promo"],
            "price_change_pct": _pct(best["price"], row["cur_price"]),
            "expected_units": best["units"],
            "expected_profit": best["profit"],
            "expected_revenue": best["revenue"],
            "expected_margin": best["margin"],
            "baseline_profit": round(base_profit, 2),
            "baseline_revenue": round(base_revenue, 2),
            "profit_uplift_pct": _pct(best["profit"], base_profit),
            "revenue_uplift_pct": _pct(best["revenue"], base_revenue),
            "binding_rules": _binding_rules(best["price"], best["window"]),
        })
    out.sort(key=lambda r: r["profit_uplift_pct"], reverse=True)
    return out


def kpi(rows: list[dict]) -> dict:
    if not rows:
        return {}
    n = len(rows)
    tot_base_p = sum(r["baseline_profit"] for r in rows)
    tot_opt_p = sum(r["expected_profit"] for r in rows)
    tot_base_r = sum(r["baseline_revenue"] for r in rows)
    tot_opt_r = sum(r["expected_revenue"] for r in rows)
    n_changed = sum(1 for r in rows if abs(r["price_change_pct"]) >= 0.5)
    n_promo = sum(1 for r in rows if r["recommended_promo"] != "none")
    avg_margin = sum(r["expected_margin"] for r in rows) / n
    return {
        "n_skus": n,
        "total_baseline_profit": round(tot_base_p, 2),
        "total_expected_profit": round(tot_opt_p, 2),
        "profit_uplift_pct": _pct(tot_opt_p, tot_base_p),
        "total_baseline_revenue": round(tot_base_r, 2),
        "total_expected_revenue": round(tot_opt_r, 2),
        "revenue_uplift_pct": _pct(tot_opt_r, tot_base_r),
        "avg_margin": round(avg_margin, 4),
        "n_price_changes": n_changed,
        "share_on_promo": round(n_promo / n, 3),
    }


# --------------------------------------------------------------------------- #
#  helpers
# --------------------------------------------------------------------------- #
def _pct(new: float, base: float) -> float:
    if base is None or abs(base) < 1e-9:
        return 0.0
    return round((new - base) / abs(base) * 100, 2)


def _binding_rules(price: float, window: dict) -> list[str]:
    binding = []
    if abs(price - window["floor"]) < 0.02:
        binding.append(window["floor_reason"])
    if abs(price - window["ceiling"]) < 0.02:
        binding.append(window["ceiling_reason"])
    return sorted(set(binding))
