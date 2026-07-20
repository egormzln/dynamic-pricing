"""
Сборка compact-каталога для serving-сервиса ценообразования.

Читает сырые CSV (data/csv/*) и сохранённые коэффициенты модели
(data/artifacts/{elasticity_by_sku.csv, promo_lift.json}) и собирает
единый data/catalog.json, который backend грузит в память.

Экономика воспроизводит ноутбук 06_02_optimizer.ipynb:
    units(p, promo) = base_units · (p/base_price)^ε · exp(promo_lift[promo])
    profit          = (p − cost) · units

Запуск:
    python scripts/build_catalog.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# --- пути ---
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
PROJECT = BACKEND.parent.parent            # .../dynamic-pricing
CSV = PROJECT / "data" / "csv"
ARTIFACTS = PROJECT / "data" / "artifacts"
OUT = BACKEND / "data" / "catalog.json"

PROMO_ORDER = ["none", "tpr", "display", "feature", "feature_display"]
GLOBAL_ELASTICITY = -2.0                    # фолбэк, если нет ни per-sku, ни category


def promo_type(row) -> str:
    if row["FEATURE"] == 1 and row["DISPLAY"] == 1:
        return "feature_display"
    if row["FEATURE"] == 1:
        return "feature"
    if row["DISPLAY"] == 1:
        return "display"
    if row["TPR_ONLY"] == 1:
        return "tpr"
    return "none"


def within_sku_elasticity(g: pd.DataFrame) -> float | None:
    """log-log OLS log_units ~ log_price с деминингом по SKU (within-estimator).

    Возвращает наклон (эластичность) или None, если данных мало / вырожденно.
    """
    d = g[(g["UNITS"] > 0) & (g["PRICE"] > 0)].copy()
    if len(d) < 50:
        return None
    x = np.log(d["PRICE"].to_numpy())
    y = np.log(d["UNITS"].to_numpy())
    # деминг внутри UPC, чтобы убрать межтоварные различия уровней
    for key in ("UPC",):
        means_x = d.groupby(key)["PRICE"].transform(lambda s: np.log(s).mean()).to_numpy()
        means_y = d.groupby(key)["UNITS"].transform(lambda s: np.log(s).mean()).to_numpy()
        x = x - means_x
        y = y - means_y
    var = np.var(x)
    if var < 1e-8:
        return None
    slope = float(np.cov(x, y)[0, 1] / var)
    # обрезаем неадекватные значения (шум редких SKU)
    if not np.isfinite(slope) or slope > -0.1 or slope < -8:
        return None
    return slope


def main() -> None:
    print("Загрузка CSV…")
    products = pd.read_csv(CSV / "products.csv")
    stores = pd.read_csv(CSV / "stores.csv")
    tx = pd.read_csv(CSV / "transactions.csv", parse_dates=["WEEK_END_DATE"])
    print(f"  products={len(products)}  stores={len(stores)}  transactions={len(tx)}")

    tx = tx[(tx["UNITS"] > 0) & (tx["PRICE"] > 0) & (tx["BASE_PRICE"] > 0)].copy()
    tx["promo_type"] = tx.apply(promo_type, axis=1)

    # --- эластичность по-SKU (cereal) из артефакта модели ---
    el_sku = pd.read_csv(ARTIFACTS / "elasticity_by_sku.csv")
    per_sku_elasticity = dict(zip(el_sku["UPC"], el_sku["mean_elasticity"]))
    print(f"  per-SKU эластичность из модели: {len(per_sku_elasticity)} SKU")

    # --- категорийная эластичность (для не-cereal) ---
    upc_to_cat = dict(zip(products["UPC"], products["CATEGORY"]))
    tx["CATEGORY"] = tx["UPC"].map(upc_to_cat)
    category_elasticity: dict[str, float] = {}
    for cat, g in tx.groupby("CATEGORY"):
        e = within_sku_elasticity(g)
        if e is not None:
            category_elasticity[cat] = round(e, 3)
    print(f"  категорийная эластичность: {category_elasticity}")

    # --- promo lift ---
    with open(ARTIFACTS / "promo_lift.json") as f:
        promo_lift_log = json.load(f)
    promo_lift_mult = {k: float(np.exp(v)) for k, v in promo_lift_log.items()}

    # --- cost per UPC = p02 * 0.95 (как Cell 9) ---
    cost = (tx.groupby("UPC")["PRICE"].quantile(0.02) * 0.95).to_dict()

    # --- per (UPC, store): base_price, base_units ---
    # base_price = медиана BASE_PRICE; base_units = медиана UNITS без промо
    grp_ps = tx.groupby(["UPC", "STORE_NUM"])
    base_price_ps = grp_ps["BASE_PRICE"].median()
    no_promo = tx[tx["promo_type"] == "none"]
    base_units_ps = no_promo.groupby(["UPC", "STORE_NUM"])["UNITS"].median()
    # fallback base_units — медиана units по всем наблюдениям SKU-store
    base_units_all = grp_ps["UNITS"].median()

    # --- price bounds per (UPC, promo): p05/p95/n ---
    bounds = (
        tx.groupby(["UPC", "promo_type"])["PRICE"]
        .agg(p05=lambda s: s.quantile(0.05), p95=lambda s: s.quantile(0.95), n="count")
        .reset_index()
    )
    bounds_dict: dict[tuple, dict] = {}
    for _, r in bounds.iterrows():
        bounds_dict[(r["UPC"], r["promo_type"])] = {
            "p05": round(float(r["p05"]), 2),
            "p95": round(float(r["p95"]), 2),
            "n": int(r["n"]),
        }

    # --- метаданные магазинов ---
    store_meta = {
        int(r["STORE_ID"]): {
            "name": str(r["STORE_NAME"]),
            "city": str(r["ADDRESS_CITY_NAME"]),
            "state": str(r["ADDRESS_STATE_PROV_CODE"]),
            "segment": str(r["SEG_VALUE_NAME"]),
        }
        for _, r in stores.iterrows()
    }

    # --- собираем SKU (агрегируем по SKU, репрезентативный магазин = самый крупный по объёму) ---
    # Для serving берём один "флагманский" магазин на SKU, чтобы каталог был обозримым,
    # но сохраняем список доступных магазинов.
    prod_meta = {int(r["UPC"]): r for _, r in products.iterrows()}
    vol_by_ps = tx.groupby(["UPC", "STORE_NUM"])["UNITS"].sum()

    skus = []
    for upc, pr in prod_meta.items():
        if upc not in cost:
            continue  # нет транзакций
        cat = pr["CATEGORY"]
        # эластичность + источник
        if upc in per_sku_elasticity:
            elasticity = round(float(per_sku_elasticity[upc]), 3)
            el_source = "per_sku"
        elif cat in category_elasticity:
            elasticity = category_elasticity[cat]
            el_source = "category"
        else:
            elasticity = GLOBAL_ELASTICITY
            el_source = "global"

        # флагманский магазин
        try:
            flagship = int(vol_by_ps.loc[upc].idxmax())
        except KeyError:
            continue
        bp = base_price_ps.get((upc, flagship))
        if bp is None or not np.isfinite(bp):
            continue
        bu = base_units_ps.get((upc, flagship))
        if bu is None or not np.isfinite(bu):
            bu = base_units_all.get((upc, flagship), np.nan)
        if not np.isfinite(bu):
            continue

        # текущая цена = последняя наблюдаемая цена в флагманском магазине
        last = tx[(tx["UPC"] == upc) & (tx["STORE_NUM"] == flagship)].sort_values("WEEK_END_DATE")
        current_price = round(float(last["PRICE"].iloc[-1]), 2)
        current_promo = str(last["promo_type"].iloc[-1])

        # bounds по промо для этого SKU
        sku_bounds = {p: bounds_dict.get((upc, p)) for p in PROMO_ORDER if (upc, p) in bounds_dict}

        # список доступных магазинов
        stores_avail = sorted(int(s) for s in tx[tx["UPC"] == upc]["STORE_NUM"].unique())

        skus.append({
            "upc": int(upc),
            "description": str(pr["DESCRIPTION"]).strip(),
            "manufacturer": str(pr["MANUFACTURER"]).strip(),
            "category": str(cat),
            "sub_category": str(pr["SUB_CATEGORY"]).strip(),
            "size": str(pr["PRODUCT_SIZE"]).strip(),
            "cost": round(float(cost[upc]), 4),
            "elasticity": elasticity,
            "elasticity_source": el_source,
            "flagship_store": flagship,
            "base_price": round(float(bp), 2),
            "base_units": round(float(bu), 2),
            "current_price": current_price,
            "current_promo": current_promo,
            "bounds": sku_bounds,
            "stores": stores_avail,
        })

    skus.sort(key=lambda s: (s["category"], -abs(s["elasticity"])))
    print(f"  собрано SKU: {len(skus)}")

    # --- seed истории цен: последние 52 недели по флагманскому магазину каждого SKU ---
    history = []
    for s in skus:
        upc, flagship = s["upc"], s["flagship_store"]
        h = (
            tx[(tx["UPC"] == upc) & (tx["STORE_NUM"] == flagship)]
            .sort_values("WEEK_END_DATE")
            .tail(52)
        )
        for _, r in h.iterrows():
            history.append({
                "upc": int(upc),
                "store": int(flagship),
                "date": r["WEEK_END_DATE"].strftime("%Y-%m-%d"),
                "price": round(float(r["PRICE"]), 2),
                "base_price": round(float(r["BASE_PRICE"]), 2),
                "units": int(r["UNITS"]),
                "promo": str(r["promo_type"]),
            })

    catalog = {
        "meta": {
            "dataset": "dunnhumby Breakfast at the Frat",
            "n_skus": len(skus),
            "promo_order": PROMO_ORDER,
            "promo_lift_log": promo_lift_log,
            "promo_lift_mult": {k: round(v, 4) for k, v in promo_lift_mult.items()},
            "category_elasticity": category_elasticity,
            "global_elasticity": GLOBAL_ELASTICITY,
        },
        "stores": store_meta,
        "skus": skus,
        "history": history,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    print(f"Сохранено → {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
