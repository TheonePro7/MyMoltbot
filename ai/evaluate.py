"""
模型评估系统：对最近 N 场已结束比赛做"假装不知道结果"的预测，计算准确率。
每次评估结果保存到 SQLite，支持历史对比。

用法：python3 -m ai.evaluate --matches 2000
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

from ai.features import compute_features, get_feature_columns, load_raw_dataset, _merge_odds_features
from ai.xgboost_model import LABEL_MAP, MatchPredictor
from football_odds.history_db import connect_history

EVAL_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "evaluations.sqlite3"


def _init_eval_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            description TEXT,
            n_matches INTEGER,
            accuracy REAL,
            accuracy_home REAL,
            accuracy_draw REAL,
            accuracy_away REAL,
            high_conf_accuracy REAL,
            high_conf_count INTEGER,
            details_json TEXT
        );
    """)


def evaluate_recent(
    n_matches: int = 2000,
    description: str = "",
    train_cutoff_seasons: int = 5,
) -> dict[str, Any]:
    """
    对最近 n_matches 场已结束比赛做评估。

    方法：用这些比赛之前的数据训练模型，然后对这些比赛做预测，对比实际结果。
    这模拟了"真实使用场景"——模型只用过去的数据。
    """
    with connect_history() as conn:
        # 取出最近的 n_matches 场已结束比赛
        test_matches = pd.read_sql_query(
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

        if test_matches.empty:
            return {"error": "无可用数据"}

        # 找到测试集最早日期，用它之前的数据训练
        earliest_test_date = test_matches["match_date"].min()

        train_matches = pd.read_sql_query(
            """SELECT m.id as match_id, m.division, m.season, m.match_date,
                      m.home_team, m.away_team, m.fthg, m.ftag, m.ftr,
                      m.hthg, m.htag, m.htr, m.home_shots, m.away_shots,
                      m.home_sot, m.away_sot, m.home_corners, m.away_corners,
                      m.home_fouls, m.away_fouls, m.home_yellows, m.away_yellows,
                      m.home_reds, m.away_reds
               FROM matches m
               WHERE m.ftr IS NOT NULL AND m.match_date < ?
               ORDER BY m.match_date, m.id""",
            conn,
            params=(earliest_test_date,),
        )

        all_ids = train_matches["match_id"].tolist() + test_matches["match_id"].tolist()
        id_str = ",".join(str(i) for i in all_ids)

        odds_1x2 = pd.read_sql_query(
            f"SELECT match_id, bookmaker, is_closing, home_odds, draw_odds, away_odds FROM odds_1x2 WHERE match_id IN ({id_str})",
            conn,
        )
        odds_ah = pd.read_sql_query(
            f"SELECT match_id, bookmaker, is_closing, handicap, home_odds, away_odds FROM odds_asian WHERE match_id IN ({id_str})",
            conn,
        )
        odds_ou = pd.read_sql_query(
            f"SELECT match_id, bookmaker, is_closing, over_odds, under_odds FROM odds_ou25 WHERE match_id IN ({id_str})",
            conn,
        )

    # 构建特征
    train_df = _merge_odds_features(train_matches, odds_1x2, odds_ah, odds_ou)
    train_df = compute_features(train_df)

    test_df = _merge_odds_features(test_matches, odds_1x2, odds_ah, odds_ou)
    test_df = compute_features(test_df)

    feature_cols = get_feature_columns(train_df)

    # 过滤掉没有赔率数据的比赛（关键特征全缺失的不预测）
    key_odds_cols = [c for c in feature_cols if "b365" in c or "odds_mean" in c or "ip_" in c or "fp_" in c]
    available_key = [c for c in key_odds_cols if c in test_df.columns]
    if available_key:
        test_df["has_odds"] = test_df[available_key].notna().any(axis=1)
        n_no_odds = (~test_df["has_odds"]).sum()
        test_df = test_df[test_df["has_odds"]].copy()
    else:
        n_no_odds = 0

    if test_df.empty:
        return {"error": "测试集中无有效赔率数据"}

    # 训练
    predictor = MatchPredictor(n_rounds=300)
    predictor.train(train_df, feature_cols=feature_cols, eval_ratio=0.1)

    # 预测
    preds = predictor.predict(test_df)
    preds["actual"] = test_df["ftr"].values

    # 计算准确率
    preds["correct"] = preds["pred_label"] == preds["actual"]
    total = len(preds)
    correct = preds["correct"].sum()
    accuracy = correct / total if total > 0 else 0

    # 分结果统计
    acc_by_result = {}
    for label in ["H", "D", "A"]:
        sub = preds[preds["actual"] == label]
        if len(sub) > 0:
            acc_by_result[label] = sub["correct"].mean()
        else:
            acc_by_result[label] = 0

    # 高置信度
    high_conf = preds[preds["confidence"] >= 0.5]
    hc_acc = high_conf["correct"].mean() if len(high_conf) > 0 else 0

    # 按联赛统计
    by_div = preds.groupby("division").agg(
        matches=("correct", "count"),
        correct=("correct", "sum"),
    ).reset_index()
    by_div["accuracy"] = by_div["correct"] / by_div["matches"]

    # 按置信度区间
    preds["conf_bin"] = pd.cut(preds["confidence"], bins=[0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0])
    by_conf = preds.groupby("conf_bin", observed=True).agg(
        matches=("correct", "count"),
        correct=("correct", "sum"),
    ).reset_index()
    by_conf["accuracy"] = by_conf["correct"] / by_conf["matches"]

    result = {
        "n_matches": total,
        "n_skipped_no_odds": int(n_no_odds),
        "train_size": len(train_df),
        "test_date_range": f"{test_df['match_date'].min()} ~ {test_df['match_date'].max()}",
        "accuracy": float(accuracy),
        "accuracy_home": float(acc_by_result.get("H", 0)),
        "accuracy_draw": float(acc_by_result.get("D", 0)),
        "accuracy_away": float(acc_by_result.get("A", 0)),
        "high_conf_accuracy": float(hc_acc),
        "high_conf_count": int(len(high_conf)),
        "by_division": by_div.to_dict("records"),
        "by_confidence": [
            {"bin": str(r["conf_bin"]), "matches": int(r["matches"]), "accuracy": float(r["accuracy"])}
            for _, r in by_conf.iterrows()
        ],
        "pred_distribution": preds["pred_label"].value_counts().to_dict(),
        "actual_distribution": preds["actual"].value_counts().to_dict(),
    }

    return result


def save_evaluation(result: dict[str, Any], description: str = "") -> str:
    """保存评估结果到数据库，返回记录 ID。"""
    EVAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(EVAL_DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_eval_db(conn)

    run_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO eval_runs (id, run_at, description, n_matches, accuracy,
           accuracy_home, accuracy_draw, accuracy_away,
           high_conf_accuracy, high_conf_count, details_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, now, description,
            result.get("n_matches", 0),
            result.get("accuracy", 0),
            result.get("accuracy_home", 0),
            result.get("accuracy_draw", 0),
            result.get("accuracy_away", 0),
            result.get("high_conf_accuracy", 0),
            result.get("high_conf_count", 0),
            json.dumps(result, ensure_ascii=False, default=str),
        ),
    )
    conn.commit()
    conn.close()
    return run_id


def list_evaluations() -> list[dict]:
    """列出所有历史评估记录。"""
    if not EVAL_DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(EVAL_DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_eval_db(conn)
    rows = conn.execute(
        "SELECT id, run_at, description, n_matches, accuracy, accuracy_home, accuracy_draw, accuracy_away, high_conf_accuracy, high_conf_count FROM eval_runs ORDER BY run_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="模型评估：对最近 N 场比赛做预测并计算准确率")
    parser.add_argument("--matches", type=int, default=2000, help="评估比赛数量（默认 2000）")
    parser.add_argument("--desc", type=str, default="", help="本次评估的描述（如：'基线模型' 或 '新增亚盘特征'）")
    parser.add_argument("--history", action="store_true", help="只查看历史评估记录")
    args = parser.parse_args()

    if args.history:
        records = list_evaluations()
        if not records:
            print("暂无评估记录", flush=True)
            return 0
        print(f"{'ID':>8} {'时间':>20} {'场数':>6} {'准确率':>8} {'主胜':>8} {'平':>8} {'客胜':>8} {'高置信':>8} {'描述'}", flush=True)
        print("-" * 100, flush=True)
        for r in records:
            print(f"{r['id']:>8} {r['run_at'][:19]:>20} {r['n_matches']:>6} "
                  f"{r['accuracy']:>7.1%} {r['accuracy_home']:>7.1%} {r['accuracy_draw']:>7.1%} "
                  f"{r['accuracy_away']:>7.1%} {r['high_conf_accuracy']:>7.1%} {r['description'] or ''}", flush=True)
        return 0

    print(f"评估最近 {args.matches} 场比赛...", flush=True)
    print(flush=True)

    t0 = time.time()
    result = evaluate_recent(n_matches=args.matches, description=args.desc)
    t1 = time.time()

    if "error" in result:
        print(f"错误: {result['error']}", flush=True)
        return 1

    run_id = save_evaluation(result, description=args.desc)

    print(f"评估完成（{t1 - t0:.1f}s）", flush=True)
    print(f"记录 ID: {run_id}", flush=True)
    print(f"描述: {args.desc or '(无)'}", flush=True)
    print(flush=True)
    print(f"测试集: {result['n_matches']} 场（跳过 {result['n_skipped_no_odds']} 场无赔率）", flush=True)
    print(f"训练集: {result['train_size']} 场", flush=True)
    print(f"日期范围: {result['test_date_range']}", flush=True)
    print(flush=True)
    print(f"  总准确率:     {result['accuracy']:.1%}", flush=True)
    print(f"  主胜准确率:   {result['accuracy_home']:.1%}", flush=True)
    print(f"  平局准确率:   {result['accuracy_draw']:.1%}", flush=True)
    print(f"  客胜准确率:   {result['accuracy_away']:.1%}", flush=True)
    print(f"  高置信(≥50%): {result['high_conf_accuracy']:.1%}（{result['high_conf_count']} 场）", flush=True)
    print(flush=True)

    print("预测分布 vs 实际分布:", flush=True)
    pd_dist = result.get("pred_distribution", {})
    ad_dist = result.get("actual_distribution", {})
    for label in ["H", "D", "A"]:
        label_name = {"H": "主胜", "D": "平", "A": "客胜"}[label]
        print(f"  {label_name}: 预测 {pd_dist.get(label, 0)} 场, 实际 {ad_dist.get(label, 0)} 场", flush=True)
    print(flush=True)

    print("按联赛:", flush=True)
    print(f"  {'联赛':>4} {'场数':>6} {'准确率':>8}", flush=True)
    for d in result.get("by_division", []):
        print(f"  {d['division']:>4} {d['matches']:>6} {d['accuracy']:>8.1%}", flush=True)
    print(flush=True)

    print("按置信度:", flush=True)
    print(f"  {'区间':>15} {'场数':>6} {'准确率':>8}", flush=True)
    for c in result.get("by_confidence", []):
        print(f"  {c['bin']:>15} {c['matches']:>6} {c['accuracy']:>8.1%}", flush=True)
    print(flush=True)

    # 跟上次对比
    records = list_evaluations()
    if len(records) >= 2:
        prev = records[1]
        diff = result["accuracy"] - prev["accuracy"]
        arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
        print(f"与上次对比: {prev['accuracy']:.1%} → {result['accuracy']:.1%} ({arrow} {abs(diff):.2%})", flush=True)
        if prev.get("description"):
            print(f"  上次描述: {prev['description']}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
