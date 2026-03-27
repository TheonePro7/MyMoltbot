"""
历史赔率数据库：SQLite 存储来自 football-data.co.uk 的历史比赛与赔率。
包含欧赔（多庄家）、亚盘、大小球、比赛统计、终盘赔率。
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def default_history_db_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data / "history.sqlite3"


def get_history_db_path() -> Path:
    p = os.environ.get("HISTORY_DB")
    return Path(p) if p else default_history_db_path()


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS leagues (
    code        TEXT PRIMARY KEY,   -- 如 E0, SP1, D1, I1, F1
    country     TEXT NOT NULL,
    name        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    division        TEXT NOT NULL,          -- 联赛代码 E0/SP1/...
    season          TEXT NOT NULL,          -- 如 '2526' 表示 2025/2026
    match_date      TEXT NOT NULL,          -- YYYY-MM-DD
    match_time      TEXT,                   -- HH:MM（部分赛季无此字段）
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    fthg            INTEGER,               -- 全场主队进球
    ftag            INTEGER,               -- 全场客队进球
    ftr             TEXT,                   -- H/D/A 全场结果
    hthg            INTEGER,               -- 半场主队进球
    htag            INTEGER,               -- 半场客队进球
    htr             TEXT,                   -- 半场结果
    referee         TEXT,
    -- 比赛统计
    home_shots      INTEGER,
    away_shots      INTEGER,
    home_sot        INTEGER,               -- 射正
    away_sot        INTEGER,
    home_corners    INTEGER,
    away_corners    INTEGER,
    home_fouls      INTEGER,
    away_fouls      INTEGER,
    home_yellows    INTEGER,
    away_yellows    INTEGER,
    home_reds       INTEGER,
    away_reds       INTEGER,
    UNIQUE(division, season, match_date, home_team, away_team)
);

CREATE TABLE IF NOT EXISTS odds_1x2 (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    bookmaker   TEXT NOT NULL,      -- 庄家缩写：B365, PS, WH, BW, Max, Avg 等
    is_closing  INTEGER NOT NULL DEFAULT 0,   -- 0=初盘 1=终盘
    home_odds   REAL,
    draw_odds   REAL,
    away_odds   REAL,
    UNIQUE(match_id, bookmaker, is_closing)
);

CREATE TABLE IF NOT EXISTS odds_ou25 (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    bookmaker   TEXT NOT NULL,
    is_closing  INTEGER NOT NULL DEFAULT 0,
    over_odds   REAL,
    under_odds  REAL,
    UNIQUE(match_id, bookmaker, is_closing)
);

CREATE TABLE IF NOT EXISTS odds_asian (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    bookmaker   TEXT NOT NULL,
    is_closing  INTEGER NOT NULL DEFAULT 0,
    handicap    REAL,               -- 让球值（主队视角）
    home_odds   REAL,
    away_odds   REAL,
    UNIQUE(match_id, bookmaker, is_closing)
);

CREATE TABLE IF NOT EXISTS import_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    division    TEXT NOT NULL,
    season      TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    rows_count  INTEGER NOT NULL,
    UNIQUE(division, season)
);

CREATE INDEX IF NOT EXISTS idx_matches_div_season ON matches(division, season);
CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team, away_team);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_odds_1x2_match ON odds_1x2(match_id);
CREATE INDEX IF NOT EXISTS idx_odds_ou25_match ON odds_ou25(match_id);
CREATE INDEX IF NOT EXISTS idx_odds_asian_match ON odds_asian(match_id);
"""

_LEAGUE_SEED = [
    ("E0", "England", "Premier League"),
    ("E1", "England", "Championship"),
    ("E2", "England", "League 1"),
    ("E3", "England", "League 2"),
    ("EC", "England", "Conference"),
    ("SP1", "Spain", "La Liga"),
    ("SP2", "Spain", "La Liga 2"),
    ("D1", "Germany", "Bundesliga"),
    ("D2", "Germany", "Bundesliga 2"),
    ("I1", "Italy", "Serie A"),
    ("I2", "Italy", "Serie B"),
    ("F1", "France", "Ligue 1"),
    ("F2", "France", "Ligue 2"),
    ("N1", "Netherlands", "Eredivisie"),
    ("B1", "Belgium", "Jupiler League"),
    ("P1", "Portugal", "Liga I"),
    ("T1", "Turkey", "Super Lig"),
    ("G1", "Greece", "Super League"),
    ("SC0", "Scotland", "Premiership"),
    ("SC1", "Scotland", "Championship"),
    ("UCL", "Europe", "UEFA Champions League"),
    ("UEL", "Europe", "UEFA Europa League"),
    ("MLS", "USA", "MLS"),
    ("J1", "Japan", "J League"),
    ("K1", "Korea", "K League 1"),
    ("CSL", "China", "Chinese Super League"),
    ("A1", "Australia", "A-League"),
    ("BR1", "Brazil", "Serie A"),
    ("AR1", "Argentina", "Primera Division"),
    ("MX1", "Mexico", "Liga MX"),
    ("DK1", "Denmark", "Superliga"),
    ("SE1", "Sweden", "Allsvenskan"),
    ("NO1", "Norway", "Eliteserien"),
    ("CH1", "Switzerland", "Super League"),
    ("AT1", "Austria", "Bundesliga"),
]


def init_history_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    for code, country, name in _LEAGUE_SEED:
        conn.execute(
            "INSERT OR IGNORE INTO leagues (code, country, name) VALUES (?, ?, ?)",
            (code, country, name),
        )
    conn.commit()


@contextmanager
def connect_history() -> Iterator[sqlite3.Connection]:
    path = get_history_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        init_history_db(conn)
        yield conn
    finally:
        conn.close()


def is_imported(conn: sqlite3.Connection, division: str, season: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM import_log WHERE division=? AND season=?",
        (division, season),
    ).fetchone()
    return row is not None


def mark_imported(conn: sqlite3.Connection, division: str, season: str, rows_count: int) -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO import_log (division, season, imported_at, rows_count) VALUES (?, ?, ?, ?)",
        (division, season, now, rows_count),
    )
    conn.commit()


def insert_match(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    cur = conn.execute(
        """INSERT OR IGNORE INTO matches (
            division, season, match_date, match_time, home_team, away_team,
            fthg, ftag, ftr, hthg, htag, htr, referee,
            home_shots, away_shots, home_sot, away_sot,
            home_corners, away_corners, home_fouls, away_fouls,
            home_yellows, away_yellows, home_reds, away_reds
        ) VALUES (
            :division, :season, :match_date, :match_time, :home_team, :away_team,
            :fthg, :ftag, :ftr, :hthg, :htag, :htr, :referee,
            :home_shots, :away_shots, :home_sot, :away_sot,
            :home_corners, :away_corners, :home_fouls, :away_fouls,
            :home_yellows, :away_yellows, :home_reds, :away_reds
        )""",
        data,
    )
    if cur.lastrowid and cur.rowcount:
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM matches WHERE division=? AND season=? AND match_date=? AND home_team=? AND away_team=?",
        (data["division"], data["season"], data["match_date"], data["home_team"], data["away_team"]),
    ).fetchone()
    return int(row["id"]) if row else 0


def insert_odds_1x2(conn: sqlite3.Connection, match_id: int, bookmaker: str,
                     is_closing: int, home: float | None, draw: float | None, away: float | None) -> None:
    if home is None and draw is None and away is None:
        return
    conn.execute(
        """INSERT OR IGNORE INTO odds_1x2 (match_id, bookmaker, is_closing, home_odds, draw_odds, away_odds)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (match_id, bookmaker, is_closing, home, draw, away),
    )


def insert_odds_ou25(conn: sqlite3.Connection, match_id: int, bookmaker: str,
                      is_closing: int, over_odds: float | None, under_odds: float | None) -> None:
    if over_odds is None and under_odds is None:
        return
    conn.execute(
        """INSERT OR IGNORE INTO odds_ou25 (match_id, bookmaker, is_closing, over_odds, under_odds)
           VALUES (?, ?, ?, ?, ?)""",
        (match_id, bookmaker, is_closing, over_odds, under_odds),
    )


def insert_odds_asian(conn: sqlite3.Connection, match_id: int, bookmaker: str,
                       is_closing: int, handicap: float | None,
                       home_odds: float | None, away_odds: float | None) -> None:
    if home_odds is None and away_odds is None:
        return
    conn.execute(
        """INSERT OR IGNORE INTO odds_asian (match_id, bookmaker, is_closing, handicap, home_odds, away_odds)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (match_id, bookmaker, is_closing, handicap, home_odds, away_odds),
    )


def query_matches(conn: sqlite3.Connection, division: str | None = None,
                   season: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    clauses = []
    params: list[Any] = []
    if division:
        clauses.append("m.division = ?")
        params.append(division)
    if season:
        clauses.append("m.season = ?")
        params.append(season)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT m.*, l.country, l.name as league_name
        FROM matches m
        LEFT JOIN leagues l ON l.code = m.division
        {where}
        ORDER BY m.match_date DESC, m.id DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_matches(conn: sqlite3.Connection, division: str | None = None,
                   season: str | None = None) -> int:
    clauses = []
    params: list[Any] = []
    if division:
        clauses.append("division = ?")
        params.append(division)
    if season:
        clauses.append("season = ?")
        params.append(season)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    row = conn.execute(f"SELECT COUNT(*) as cnt FROM matches {where}", params).fetchone()
    return int(row["cnt"]) if row else 0


def get_match_with_odds(conn: sqlite3.Connection, match_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if not row:
        return None
    m = dict(row)
    m["odds_1x2"] = [dict(r) for r in conn.execute(
        "SELECT * FROM odds_1x2 WHERE match_id = ? ORDER BY is_closing, bookmaker", (match_id,)
    ).fetchall()]
    m["odds_ou25"] = [dict(r) for r in conn.execute(
        "SELECT * FROM odds_ou25 WHERE match_id = ? ORDER BY is_closing, bookmaker", (match_id,)
    ).fetchall()]
    m["odds_asian"] = [dict(r) for r in conn.execute(
        "SELECT * FROM odds_asian WHERE match_id = ? ORDER BY is_closing, bookmaker", (match_id,)
    ).fetchall()]
    return m


def get_import_status(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM import_log ORDER BY division, season"
    ).fetchall()
    return [dict(r) for r in rows]


def summary_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()
    by_div = conn.execute(
        """SELECT m.division, l.country, l.name as league_name,
                  COUNT(*) as match_count, MIN(m.season) as first_season, MAX(m.season) as last_season
           FROM matches m LEFT JOIN leagues l ON l.code = m.division
           GROUP BY m.division ORDER BY match_count DESC"""
    ).fetchall()
    odds_count = conn.execute("SELECT COUNT(*) as c FROM odds_1x2").fetchone()
    ah_count = conn.execute("SELECT COUNT(*) as c FROM odds_asian").fetchone()
    return {
        "total_matches": int(total["c"]) if total else 0,
        "total_odds_records": int(odds_count["c"]) if odds_count else 0,
        "total_asian_records": int(ah_count["c"]) if ah_count else 0,
        "by_division": [dict(r) for r in by_div],
    }
