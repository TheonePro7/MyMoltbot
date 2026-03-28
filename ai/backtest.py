"""
回测引擎：在历史数据上验证预测模型的真实表现。
支持按赛季滚动训练、命中率统计、ROI 计算、分联赛分析。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ai.features import build_dataset, compute_features, get_feature_columns
from ai.xgboost_model import LABEL_MAP, MatchPredictor


def rolling_backtest(
    df: pd.DataFrame,
    train_seasons: int = 5,
    min_train_size: int = 2000,
    confidence_threshold: float = 0.0,
    stake: float = 1.0,
) -> pd.DataFrame:
    """
    滚动回测：用前 N 个赛季训练，预测下一个赛季。

    参数：
    - train_seasons: 训练窗口（赛季数）
    - confidence_threshold: 只在置信度超过阈值时下注
    - stake: 每注金额

    返回每场预测的详细 DataFrame。
    """
    feature_cols = get_feature_columns(df)
    seasons = sorted(df["season"].unique())

    all_results: list[pd.DataFrame] = []

    for i in range(train_seasons, len(seasons)):
        test_season = seasons[i]
        train_seasons_list = seasons[max(0, i - train_seasons): i]

        train_df = df[df["season"].isin(train_seasons_list)]
        test_df = df[df["season"] == test_season]

        if len(train_df) < min_train_size or len(test_df) == 0:
            continue

        predictor = MatchPredictor(n_rounds=300)
        predictor.train(train_df, feature_cols=feature_cols, eval_ratio=0.1)

        preds = predictor.predict(test_df)
        preds["actual"] = test_df["ftr"].values
        preds["season"] = test_season
        preds["correct"] = (preds["pred_label"] == preds["actual"]).astype(int)

        # B365 初盘赔率（用于计算 ROI）
        for col in ["home_b365_open", "draw_b365_open", "away_b365_open"]:
            if col in test_df.columns:
                preds[col] = test_df[col].values

        # 计算每注收益
        preds["bet_placed"] = (preds["confidence"] >= confidence_threshold).astype(int)
        preds["payout"] = 0.0
        for idx, row in preds.iterrows():
            if not row["bet_placed"]:
                continue
            pred = row["pred_label"]
            actual = row["actual"]
            if pred == actual:
                if pred == "H" and "home_b365_open" in preds.columns:
                    preds.at[idx, "payout"] = row.get("home_b365_open", 0) * stake
                elif pred == "D" and "draw_b365_open" in preds.columns:
                    preds.at[idx, "payout"] = row.get("draw_b365_open", 0) * stake
                elif pred == "A" and "away_b365_open" in preds.columns:
                    preds.at[idx, "payout"] = row.get("away_b365_open", 0) * stake

        all_results.append(preds)

    if not all_results:
        return pd.DataFrame()

    return pd.concat(all_results, ignore_index=True)


def backtest_summary(results: pd.DataFrame) -> dict[str, Any]:
    """从回测结果计算汇总统计。"""
    if results.empty:
        return {}

    total = len(results)
    correct = results["correct"].sum()
    accuracy = correct / total

    bets_placed = results["bet_placed"].sum()
    total_staked = bets_placed * 1.0
    total_payout = results["payout"].sum()
    profit = total_payout - total_staked
    roi = (profit / total_staked * 100) if total_staked > 0 else 0

    # 按赛季统计
    by_season = results.groupby("season").agg(
        matches=("correct", "count"),
        correct=("correct", "sum"),
        bets=("bet_placed", "sum"),
        payout=("payout", "sum"),
    ).reset_index()
    by_season["accuracy"] = by_season["correct"] / by_season["matches"]
    by_season["roi"] = ((by_season["payout"] - by_season["bets"]) / by_season["bets"] * 100).fillna(0)

    # 按联赛统计
    by_div = results.groupby("division").agg(
        matches=("correct", "count"),
        correct=("correct", "sum"),
        bets=("bet_placed", "sum"),
        payout=("payout", "sum"),
    ).reset_index()
    by_div["accuracy"] = by_div["correct"] / by_div["matches"]
    by_div["roi"] = ((by_div["payout"] - by_div["bets"]) / by_div["bets"] * 100).fillna(0)

    # 按置信度区间统计
    results_copy = results.copy()
    results_copy["conf_bin"] = pd.cut(results_copy["confidence"], bins=[0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0])
    by_conf = results_copy.groupby("conf_bin", observed=True).agg(
        matches=("correct", "count"),
        correct=("correct", "sum"),
    ).reset_index()
    by_conf["accuracy"] = by_conf["correct"] / by_conf["matches"]

    # 只赌高置信度的 ROI
    high_conf = results[results["confidence"] >= 0.5]
    hc_bets = len(high_conf)
    hc_payout = high_conf["payout"].sum()
    hc_roi = ((hc_payout - hc_bets) / hc_bets * 100) if hc_bets > 0 else 0

    return {
        "total_matches": total,
        "accuracy": accuracy,
        "total_bets": int(bets_placed),
        "total_staked": total_staked,
        "total_payout": total_payout,
        "profit": profit,
        "roi_pct": roi,
        "high_conf_bets": hc_bets,
        "high_conf_roi_pct": hc_roi,
        "by_season": by_season.to_dict("records"),
        "by_division": by_div.to_dict("records"),
        "by_confidence": by_conf.to_dict("records") if not by_conf.empty else [],
    }
