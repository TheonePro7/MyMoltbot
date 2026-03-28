"""
模拟下单系统：对有盘口数据但未开赛的比赛做模拟投注，评估盈利能力。
也可对已结束比赛做回测模拟投注。

用法：python3 -m ai.sim_bet
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ai.features import compute_features, get_feature_columns, _merge_odds_features, load_raw_dataset
from ai.xgboost_model import MatchPredictor
from football_odds.history_db import connect_history

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"
SIM_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sim_results.sqlite3"


def _init_sim_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sim_runs (
            id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            description TEXT,
            mode TEXT,
            n_bets INTEGER,
            n_wins INTEGER,
            total_staked REAL,
            total_payout REAL,
            profit REAL,
            roi_pct REAL,
            win_rate REAL,
            details_json TEXT
        );
    """)


def _load_predictor(division: str | None = None) -> MatchPredictor:
    """加载模型：优先联赛专属模型，没有则用通用模型。"""
    if division:
        league_dir = MODEL_DIR / f"league_{division}"
        if (league_dir / "xgb_match_predictor.json").exists():
            return MatchPredictor.load(league_dir)
    return MatchPredictor.load(MODEL_DIR)


def simulate_bets(
    n_matches: int = 1000,
    min_confidence: float = 0.5,
    stake: float = 100.0,
    description: str = "",
) -> dict[str, Any]:
    """
    对最近 n_matches 场已结束比赛做模拟投注。

    策略：只在模型置信度 >= min_confidence 时下注。
    赔率：使用 B365 初盘赔率计算回报。
    """
    with connect_history() as conn:
        test_df_raw = pd.read_sql_query(
            f"""SELECT m.id as match_id, m.division, m.season, m.match_date,
                       m.home_team, m.away_team, m.fthg, m.ftag, m.ftr,
                       m.hthg, m.htag, m.htr, m.home_shots, m.away_shots,
                       m.home_sot, m.away_sot, m.home_corners, m.away_corners,
                       m.home_fouls, m.away_fouls, m.home_yellows, m.away_yellows,
                       m.home_reds, m.away_reds
                FROM matches m
                WHERE m.ftr IS NOT NULL
                ORDER BY m.match_date DESC, m.id DESC
                LIMIT {n_matches}""",
            conn,
        )

        if test_df_raw.empty:
            return {"error": "无可用数据"}

        ids = test_df_raw["match_id"].tolist()
        id_str = ",".join(str(i) for i in ids)
        odds_1x2 = pd.read_sql_query(
            f"SELECT match_id, bookmaker, is_closing, home_odds, draw_odds, away_odds FROM odds_1x2 WHERE match_id IN ({id_str})", conn)
        odds_ah = pd.read_sql_query(
            f"SELECT match_id, bookmaker, is_closing, handicap, home_odds, away_odds FROM odds_asian WHERE match_id IN ({id_str})", conn)
        odds_ou = pd.read_sql_query(
            f"SELECT match_id, bookmaker, is_closing, over_odds, under_odds FROM odds_ou25 WHERE match_id IN ({id_str})", conn)

    df = _merge_odds_features(test_df_raw, odds_1x2, odds_ah, odds_ou)
    df = compute_features(df)

    # 按联赛分别用模型预测
    all_preds = []
    for div in df["division"].unique():
        div_df = df[df["division"] == div].copy()
        try:
            predictor = _load_predictor(div)
            preds = predictor.predict(div_df)
            preds["actual"] = div_df["ftr"].values
            # 获取 B365 赔率
            for col in ["home_b365_open", "draw_b365_open", "away_b365_open"]:
                if col in div_df.columns:
                    preds[col] = div_df[col].values
            all_preds.append(preds)
        except Exception:
            predictor = _load_predictor(None)
            preds = predictor.predict(div_df)
            preds["actual"] = div_df["ftr"].values
            for col in ["home_b365_open", "draw_b365_open", "away_b365_open"]:
                if col in div_df.columns:
                    preds[col] = div_df[col].values
            all_preds.append(preds)

    if not all_preds:
        return {"error": "无预测结果"}

    results = pd.concat(all_preds, ignore_index=True)

    # 模拟下注
    results["bet"] = results["confidence"] >= min_confidence
    results["payout"] = 0.0
    results["profit_per_bet"] = 0.0

    for idx, row in results.iterrows():
        if not row["bet"]:
            continue
        pred = row["pred_label"]
        actual = row["actual"]
        odds = None
        if pred == "H":
            odds = row.get("home_b365_open")
        elif pred == "D":
            odds = row.get("draw_b365_open")
        elif pred == "A":
            odds = row.get("away_b365_open")

        if odds and not pd.isna(odds) and odds > 1:
            if pred == actual:
                results.at[idx, "payout"] = odds * stake
                results.at[idx, "profit_per_bet"] = (odds - 1) * stake
            else:
                results.at[idx, "payout"] = 0
                results.at[idx, "profit_per_bet"] = -stake

    bets = results[results["bet"]]
    n_bets = len(bets)
    n_wins = int((bets["payout"] > 0).sum())
    total_staked = n_bets * stake
    total_payout = float(bets["payout"].sum())
    profit = total_payout - total_staked
    roi = (profit / total_staked * 100) if total_staked > 0 else 0
    win_rate = n_wins / n_bets if n_bets > 0 else 0

    # 按联赛
    by_div = bets.groupby("division").agg(
        n_bets=("bet", "count"),
        n_wins=("payout", lambda x: (x > 0).sum()),
        total_payout=("payout", "sum"),
    ).reset_index()
    by_div["staked"] = by_div["n_bets"] * stake
    by_div["profit"] = by_div["total_payout"] - by_div["staked"]
    by_div["roi"] = (by_div["profit"] / by_div["staked"] * 100).fillna(0)
    by_div["win_rate"] = by_div["n_wins"] / by_div["n_bets"]

    # 按置信度
    bets_copy = bets.copy()
    bets_copy["conf_bin"] = pd.cut(bets_copy["confidence"], bins=[0.5, 0.6, 0.7, 0.8, 1.0])
    by_conf = bets_copy.groupby("conf_bin", observed=True).agg(
        n_bets=("bet", "count"),
        n_wins=("payout", lambda x: (x > 0).sum()),
        total_payout=("payout", "sum"),
    ).reset_index()
    by_conf["staked"] = by_conf["n_bets"] * stake
    by_conf["roi"] = ((by_conf["total_payout"] - by_conf["staked"]) / by_conf["staked"] * 100).fillna(0)

    summary = {
        "n_matches": len(results),
        "min_confidence": min_confidence,
        "stake": stake,
        "n_bets": n_bets,
        "n_wins": n_wins,
        "win_rate": float(win_rate),
        "total_staked": total_staked,
        "total_payout": total_payout,
        "profit": profit,
        "roi_pct": roi,
        "by_division": by_div.to_dict("records"),
        "by_confidence": [
            {"bin": str(r["conf_bin"]), "n_bets": int(r["n_bets"]),
             "roi": float(r["roi"]), "n_wins": int(r["n_wins"])}
            for _, r in by_conf.iterrows()
        ],
    }

    # 保存到数据库
    SIM_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    sconn = sqlite3.connect(str(SIM_DB_PATH))
    _init_sim_db(sconn)
    run_id = str(uuid.uuid4())[:8]
    sconn.execute(
        """INSERT INTO sim_runs (id, run_at, description, mode, n_bets, n_wins,
           total_staked, total_payout, profit, roi_pct, win_rate, details_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, datetime.now(timezone.utc).isoformat(), description, "backtest",
         n_bets, n_wins, total_staked, total_payout, profit, roi, win_rate,
         json.dumps(summary, ensure_ascii=False, default=str)),
    )
    sconn.commit()
    sconn.close()

    summary["run_id"] = run_id
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="模拟下单回测")
    parser.add_argument("--matches", type=int, default=1000, help="回测比赛数")
    parser.add_argument("--confidence", type=float, default=0.5, help="最低置信度阈值")
    parser.add_argument("--stake", type=float, default=100.0, help="每注金额")
    parser.add_argument("--desc", type=str, default="", help="描述")
    args = parser.parse_args()

    def log(msg):
        print(msg, flush=True)

    log(f"模拟下单回测: {args.matches} 场, 置信度≥{args.confidence:.0%}, 每注 ¥{args.stake:.0f}")
    log("")

    result = simulate_bets(
        n_matches=args.matches,
        min_confidence=args.confidence,
        stake=args.stake,
        description=args.desc,
    )

    if "error" in result:
        log(f"错误: {result['error']}")
        return 1

    log(f"记录 ID: {result['run_id']}")
    log(f"比赛总数: {result['n_matches']}")
    log(f"下注场数: {result['n_bets']}（置信度≥{args.confidence:.0%}）")
    log(f"命中场数: {result['n_wins']}")
    log(f"命中率:   {result['win_rate']:.1%}")
    log(f"总投入:   ¥{result['total_staked']:,.0f}")
    log(f"总回报:   ¥{result['total_payout']:,.0f}")
    log(f"净利润:   ¥{result['profit']:,.0f}")
    log(f"ROI:      {result['roi_pct']:.1f}%")
    log("")

    log("按联赛:")
    log(f"  {'联赛':>4} {'注数':>6} {'命中':>6} {'命中率':>8} {'ROI':>8}")
    for d in result.get("by_division", []):
        log(f"  {d['division']:>4} {d['n_bets']:>6} {d['n_wins']:>6} {d['win_rate']:>8.1%} {d['roi']:>7.1f}%")
    log("")

    log("按置信度:")
    log(f"  {'区间':>15} {'注数':>6} {'命中':>6} {'ROI':>8}")
    for c in result.get("by_confidence", []):
        log(f"  {c['bin']:>15} {c['n_bets']:>6} {c['n_wins']:>6} {c['roi']:>7.1f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
