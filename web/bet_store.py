"""
模拟投注 SQLite 存储：方案单、赛果、结算。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from football_odds.parlay import build_subbet_lines, settle_lines

CST = timezone.utc  # 存 UTC ISO；展示可用本地


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_db_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data / "sim_bets.sqlite3"


def get_db_path() -> Path:
    import os

    p = os.environ.get("SIM_BET_DB")
    return Path(p) if p else default_db_path()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS results (
            fixture_id TEXT PRIMARY KEY,
            home_goals INTEGER NOT NULL,
            away_goals INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS slips (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            jc_date TEXT NOT NULL,
            selections_json TEXT NOT NULL,
            combo_types_json TEXT NOT NULL,
            dan_ids_json TEXT NOT NULL,
            multiplier INTEGER NOT NULL DEFAULT 1,
            stake_per_line REAL NOT NULL DEFAULT 2.0,
            subbets_json TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            total_stake REAL,
            total_payout REAL,
            profit REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
        """
    )


def get_or_create_default_session(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT id FROM sessions ORDER BY created_at LIMIT 1").fetchone()
    if row:
        return str(row["id"])
    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (id, name, created_at) VALUES (?, ?, ?)",
        (sid, "默认账本", _now_iso()),
    )
    return sid


def list_sessions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT id, name, created_at FROM sessions ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def create_session(conn: sqlite3.Connection, name: str) -> str:
    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (id, name, created_at) VALUES (?, ?, ?)",
        (sid, name.strip() or "未命名", _now_iso()),
    )
    return sid


def set_result(conn: sqlite3.Connection, fixture_id: str, home_goals: int, away_goals: int) -> None:
    conn.execute(
        """INSERT INTO results (fixture_id, home_goals, away_goals, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(fixture_id) DO UPDATE SET
             home_goals=excluded.home_goals,
             away_goals=excluded.away_goals,
             updated_at=excluded.updated_at""",
        (fixture_id, int(home_goals), int(away_goals), _now_iso()),
    )


def get_results_map(conn: sqlite3.Connection) -> dict[str, tuple[int, int]]:
    rows = conn.execute("SELECT fixture_id, home_goals, away_goals FROM results").fetchall()
    return {str(r["fixture_id"]): (int(r["home_goals"]), int(r["away_goals"])) for r in rows}


def create_slip(
    conn: sqlite3.Connection,
    session_id: str,
    jc_date: str,
    selections: list[dict[str, Any]],
    combo_types: list[str],
    dan_ids: list[str],
    multiplier: int = 1,
    stake_per_line: float = 2.0,
) -> str:
    if not selections:
        raise ValueError("请至少选择一场比赛选项")
    lines = build_subbet_lines(selections, combo_types, set(dan_ids))
    per = float(stake_per_line) * int(multiplier)
    total_stake = per * len(lines)
    slip_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO slips (
            id, session_id, created_at, jc_date, selections_json, combo_types_json,
            dan_ids_json, multiplier, stake_per_line, subbets_json, status,
            total_stake, total_payout, profit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL)""",
        (
            slip_id,
            session_id,
            _now_iso(),
            jc_date,
            json.dumps(selections, ensure_ascii=False),
            json.dumps(combo_types, ensure_ascii=False),
            json.dumps(dan_ids, ensure_ascii=False),
            int(multiplier),
            float(stake_per_line),
            json.dumps(lines, ensure_ascii=False, default=str),
            total_stake,
        ),
    )
    return slip_id


def settle_slip(conn: sqlite3.Connection, slip_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM slips WHERE id = ?", (slip_id,)).fetchone()
    if not row:
        raise ValueError("方案不存在")
    if row["status"] == "settled":
        return dict(row)
    results = get_results_map(conn)
    lines_raw = json.loads(row["subbets_json"] or "[]")
    stake_per = float(row["stake_per_line"])
    mult = int(row["multiplier"])
    settled, payout, profit = settle_lines(lines_raw, results, stake_per, mult)
    conn.execute(
        """UPDATE slips SET status='settled', subbets_json=?, total_payout=?, profit=?
           WHERE id=?""",
        (json.dumps(settled, ensure_ascii=False, default=str), payout, profit, slip_id),
    )
    r2 = conn.execute("SELECT * FROM slips WHERE id = ?", (slip_id,)).fetchone()
    return dict(r2) if r2 else {}


def settle_pending_for_session(conn: sqlite3.Connection, session_id: str) -> int:
    rows = conn.execute(
        "SELECT id FROM slips WHERE session_id=? AND status='pending'", (session_id,)
    ).fetchall()
    n = 0
    for r in rows:
        settle_slip(conn, str(r["id"]))
        n += 1
    return n


def list_slips(conn: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM slips WHERE session_id=? ORDER BY created_at DESC", (session_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def session_summary(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    rows = conn.execute(
        """SELECT
            COUNT(*) as cnt,
            COALESCE(SUM(total_stake),0) as sum_stake,
            COALESCE(SUM(CASE WHEN status='settled' THEN total_payout ELSE 0 END),0) as sum_payout,
            COALESCE(SUM(CASE WHEN status='settled' THEN profit ELSE 0 END),0) as sum_profit,
            SUM(CASE WHEN status='settled' THEN 1 ELSE 0 END) as settled_cnt,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending_cnt
           FROM slips WHERE session_id=?""",
        (session_id,),
    ).fetchone()
    return dict(rows) if rows else {}
