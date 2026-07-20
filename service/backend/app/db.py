"""SQLite: активная политика (версионируется) + аудит изменений цен."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .rules import Policy, default_policy

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "service.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS policy (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts TEXT NOT NULL,
                   data TEXT NOT NULL)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS price_events (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts TEXT NOT NULL,
                   upc INTEGER NOT NULL,
                   description TEXT,
                   store INTEGER,
                   old_price REAL,
                   new_price REAL,
                   old_promo TEXT,
                   new_promo TEXT,
                   uplift_pct REAL,
                   reason TEXT)"""
        )
        # затравка политики по умолчанию
        cur = c.execute("SELECT COUNT(*) AS n FROM policy").fetchone()
        if cur["n"] == 0:
            save_policy(default_policy(), conn=c)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_policy(policy: Policy, conn: sqlite3.Connection | None = None) -> None:
    own = conn is None
    c = conn or _conn()
    c.execute(
        "INSERT INTO policy (ts, data) VALUES (?, ?)",
        (_now(), policy.model_dump_json()),
    )
    if own:
        c.commit()
        c.close()


def get_policy() -> Policy:
    with _conn() as c:
        row = c.execute("SELECT data FROM policy ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return default_policy()
    return Policy.model_validate_json(row["data"])


def add_price_event(**kw) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO price_events
               (ts, upc, description, store, old_price, new_price, old_promo, new_promo, uplift_pct, reason)
               VALUES (:ts, :upc, :description, :store, :old_price, :new_price,
                       :old_promo, :new_promo, :uplift_pct, :reason)""",
            {"ts": _now(), **kw},
        )


def list_price_events(limit: int = 200) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM price_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
