"""北单串关回测 API。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Query

RESULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "parlay_backtest.sqlite3"

router = APIRouter(prefix="/api/parlay", tags=["串关回测"])


@router.get("/results")
def get_parlay_results():
    """获取所有串关回测汇总。"""
    if not RESULT_DB.exists():
        return {"runs": []}
    conn = sqlite3.connect(str(RESULT_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM parlay_runs ORDER BY run_at DESC"
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        item = dict(r)
        if item.get('details_json'):
            try:
                item['details'] = json.loads(item['details_json'])
            except:
                item['details'] = None
            del item['details_json']
        results.append(item)
    return {"runs": results}


@router.get("/details")
def get_parlay_details(
    parlay_type: str = Query("2串1", description="串关类型：2串1/3串1/4串1"),
    min_confidence: int = Query(60, description="最低置信度百分比：50/60/70"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    only_wins: bool = Query(False, description="只看命中"),
):
    """获取串关详细投注列表。"""
    if not RESULT_DB.exists():
        return {"details": [], "total": 0}

    conn = sqlite3.connect(str(RESULT_DB))
    conn.row_factory = sqlite3.Row

    type_key = f"{parlay_type}_conf{min_confidence}"
    where = f"run_id LIKE '%{type_key}'"
    if only_wins:
        where += " AND is_win=1"

    total = conn.execute(f"SELECT COUNT(*) as c FROM parlay_details WHERE {where}").fetchone()
    rows = conn.execute(
        f"""SELECT * FROM parlay_details WHERE {where}
            ORDER BY parlay_date DESC, parlay_index
            LIMIT ? OFFSET ?""",
        (page_size, (page - 1) * page_size)
    ).fetchall()
    conn.close()

    details = []
    for r in rows:
        item = dict(r)
        item['legs'] = json.loads(item.get('legs_json', '[]'))
        del item['legs_json']
        details.append(item)

    return {
        "details": details,
        "total": total["c"] if total else 0,
        "page": page,
        "total_pages": max(1, (total["c"] + page_size - 1) // page_size) if total else 1,
    }


@router.get("/run-backtest")
def run_backtest(
    matches: int = Query(3000, ge=500, le=5000),
    stake: float = Query(2.0, ge=1),
):
    """运行一次串关回测。"""
    from ai.parlay_backtest import run_full_backtest
    result = run_full_backtest(n_matches=matches, stake=stake, log_fn=print)
    return result
