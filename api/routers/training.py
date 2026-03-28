"""训练成长大屏 API：展示模型的自我训练历史和准确率变化。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter

from ai.evaluate import list_evaluations, EVAL_DB_PATH

router = APIRouter(prefix="/api/training", tags=["训练成长"])

SIM_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sim_results.sqlite3"


@router.get("/history")
def get_training_history():
    """获取所有评估历史记录（含准确率变化）。"""
    records = list_evaluations()
    records.reverse()
    return {
        "records": records,
        "total_runs": len(records),
        "best_accuracy": max((r["accuracy"] for r in records), default=0),
        "latest_accuracy": records[-1]["accuracy"] if records else 0,
    }


@router.get("/growth")
def get_growth_data():
    """获取准确率成长曲线数据。"""
    records = list_evaluations()
    records.reverse()

    timeline = []
    best_so_far = 0
    for i, r in enumerate(records):
        acc = r["accuracy"]
        if acc > best_so_far:
            best_so_far = acc
        timeline.append({
            "run_index": i + 1,
            "run_id": r["id"],
            "run_at": r["run_at"],
            "description": r.get("description", ""),
            "accuracy": round(acc * 100, 2),
            "accuracy_home": round(r.get("accuracy_home", 0) * 100, 2),
            "accuracy_draw": round(r.get("accuracy_draw", 0) * 100, 2),
            "accuracy_away": round(r.get("accuracy_away", 0) * 100, 2),
            "high_conf_accuracy": round(r.get("high_conf_accuracy", 0) * 100, 2),
            "n_matches": r.get("n_matches", 0),
            "best_so_far": round(best_so_far * 100, 2),
        })

    improvement = 0
    if len(timeline) >= 2:
        improvement = timeline[-1]["accuracy"] - timeline[0]["accuracy"]

    return {
        "timeline": timeline,
        "total_runs": len(timeline),
        "improvement": round(improvement, 2),
        "best_accuracy": round(best_so_far * 100, 2),
    }


@router.get("/league-comparison")
def get_league_comparison():
    """获取各联赛模型准确率对比。"""
    if not EVAL_DB_PATH.exists():
        return {"leagues": []}

    conn = sqlite3.connect(str(EVAL_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT details_json FROM eval_runs WHERE details_json IS NOT NULL ORDER BY run_at DESC LIMIT 1"
    ).fetchone()
    conn.close()

    if not rows:
        return {"leagues": []}

    details = json.loads(rows["details_json"])
    by_div = details.get("by_division", [])

    from football_odds.league_names import get_cn_name
    leagues = []
    for d in by_div:
        leagues.append({
            "division": d.get("division", ""),
            "name": get_cn_name(d.get("division", "")),
            "matches": d.get("matches", 0),
            "accuracy": round(d.get("accuracy", 0) * 100, 2),
        })
    leagues.sort(key=lambda x: x["accuracy"], reverse=True)

    return {"leagues": leagues}


@router.get("/sim-history")
def get_sim_history():
    """获取模拟下单历史。"""
    if not SIM_DB_PATH.exists():
        return {"runs": []}

    conn = sqlite3.connect(str(SIM_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, run_at, description, n_bets, n_wins, total_staked, total_payout, profit, roi_pct, win_rate FROM sim_runs ORDER BY run_at DESC"
    ).fetchall()
    conn.close()

    return {"runs": [dict(r) for r in rows]}
