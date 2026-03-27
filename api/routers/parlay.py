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
    """获取所有串关回测结果。"""
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


@router.get("/run-backtest")
def run_backtest(
    matches: int = Query(3000, ge=500, le=5000),
    stake: float = Query(2.0, ge=1),
):
    """运行一次串关回测。"""
    from ai.parlay_backtest import run_full_backtest
    result = run_full_backtest(n_matches=matches, stake=stake, log_fn=print)
    return result
