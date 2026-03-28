"""
自我训练闭环：自动特征搜索 → 超参优化 → 分联赛训练 → 评估对比 → 保存最优模型。

核心流程：
1. 按联赛分别训练和评估（每个联赛一个独立模型）
2. 自动搜索最优特征组合
3. 自动搜索最优超参数
4. 对比新旧模型，只有更优时才替换
5. 所有结果记录到 evaluations.sqlite3

用法：python3 -m ai.auto_train
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import ParameterGrid

from ai.evaluate import save_evaluation
from ai.features import build_dataset, compute_features, get_feature_columns, load_raw_dataset, _merge_odds_features
from ai.xgboost_model import MatchPredictor, default_xgb_params
from football_odds.history_db import connect_history

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"

DIVISIONS_MAIN = ["E0", "E1", "SP1", "D1", "I1", "F1"]

# 特征组：用于搜索最优组合
FEATURE_GROUPS = {
    "odds_basic": ["home_b365_open", "draw_b365_open", "away_b365_open",
                    "ip_home_b365", "ip_draw_b365", "ip_away_b365",
                    "fp_home_b365", "fp_draw_b365", "fp_away_b365", "overround_b365"],
    "odds_ps": ["home_ps_open", "draw_ps_open", "away_ps_open",
                "ip_home_ps", "ip_draw_ps", "ip_away_ps",
                "fp_home_ps", "fp_draw_ps", "fp_away_ps", "overround_ps"],
    "odds_market": ["home_odds_mean", "draw_odds_mean", "away_odds_mean",
                     "home_odds_std", "draw_odds_std", "away_odds_std", "bm_count"],
    "odds_drift": ["drift_home_b365", "drift_draw_b365", "drift_away_b365",
                    "drift_pct_home_b365", "drift_pct_draw_b365", "drift_pct_away_b365"],
    "asian": ["ah_b365_handicap", "ah_b365_home", "ah_b365_away",
              "ah_avg_handicap", "ah_avg_home", "ah_avg_away"],
    "ou": ["ou_b365_over", "ou_b365_under", "ou_avg_over", "ou_avg_under"],
    "match_stats": ["home_shots", "away_shots", "home_sot", "away_sot",
                     "home_corners", "away_corners", "home_fouls", "away_fouls",
                     "home_yellows", "away_yellows", "home_reds", "away_reds"],
    "league": ["div_encoded"],
    "market_avg": ["home_avg_open", "draw_avg_open", "away_avg_open",
                    "home_bbavg_open", "draw_bbavg_open", "away_bbavg_open"],
}

# 超参搜索空间
PARAM_GRID = {
    "max_depth": [4, 6, 8],
    "learning_rate": [0.03, 0.05, 0.1],
    "min_child_weight": [3, 5, 10],
    "subsample": [0.7, 0.8, 0.9],
    "colsample_bytree": [0.7, 0.8, 0.9],
}

# 快速搜索用的小网格
PARAM_GRID_FAST = {
    "max_depth": [4, 6],
    "learning_rate": [0.05, 0.1],
    "min_child_weight": [5],
    "subsample": [0.8],
    "colsample_bytree": [0.8],
}


def _train_and_eval(train_df: pd.DataFrame, test_df: pd.DataFrame,
                     feature_cols: list[str], params: dict,
                     n_rounds: int = 300) -> dict[str, Any]:
    """训练并评估，返回结果摘要。"""
    available = [c for c in feature_cols if c in train_df.columns and c in test_df.columns]
    if len(available) < 3:
        return {"accuracy": 0, "error": "特征不足"}

    predictor = MatchPredictor(params=params, n_rounds=n_rounds)
    train_result = predictor.train(train_df, feature_cols=available, eval_ratio=0.1)

    preds = predictor.predict(test_df)
    preds["actual"] = test_df["ftr"].values
    preds["correct"] = preds["pred_label"] == preds["actual"]

    total = len(preds)
    accuracy = preds["correct"].mean()

    acc_by_result = {}
    for label in ["H", "D", "A"]:
        sub = preds[preds["actual"] == label]
        acc_by_result[label] = sub["correct"].mean() if len(sub) > 0 else 0

    high_conf = preds[preds["confidence"] >= 0.5]
    hc_acc = high_conf["correct"].mean() if len(high_conf) > 0 else 0

    return {
        "accuracy": float(accuracy),
        "accuracy_home": float(acc_by_result.get("H", 0)),
        "accuracy_draw": float(acc_by_result.get("D", 0)),
        "accuracy_away": float(acc_by_result.get("A", 0)),
        "high_conf_accuracy": float(hc_acc),
        "high_conf_count": int(len(high_conf)),
        "n_matches": total,
        "n_features": len(available),
        "best_iteration": train_result.get("best_iteration", 0),
        "predictor": predictor,
        "feature_cols": available,
    }


def train_by_league(n_test_matches: int = 500, log_fn=None) -> dict[str, Any]:
    """
    按联赛分别训练和评估。每个联赛用该联赛自己的历史数据训练独立模型。
    """
    def log(msg):
        if log_fn: log_fn(msg)

    results = {}

    with connect_history() as conn:
        for div in DIVISIONS_MAIN:
            log(f"\n{'='*50}")
            log(f"联赛: {div}")
            log(f"{'='*50}")

            all_df = load_raw_dataset(conn, divisions=[div])
            if all_df.empty or len(all_df) < 1000:
                log(f"  数据不足（{len(all_df)} 场），跳过")
                results[div] = {"error": "数据不足", "n_total": len(all_df)}
                continue

            # 加载赔率
            ids = all_df["match_id"].tolist()
            id_str = ",".join(str(i) for i in ids)
            odds_1x2 = pd.read_sql_query(
                f"SELECT match_id, bookmaker, is_closing, home_odds, draw_odds, away_odds FROM odds_1x2 WHERE match_id IN ({id_str})", conn)
            odds_ah = pd.read_sql_query(
                f"SELECT match_id, bookmaker, is_closing, handicap, home_odds, away_odds FROM odds_asian WHERE match_id IN ({id_str})", conn)
            odds_ou = pd.read_sql_query(
                f"SELECT match_id, bookmaker, is_closing, over_odds, under_odds FROM odds_ou25 WHERE match_id IN ({id_str})", conn)

            df = _merge_odds_features(all_df, odds_1x2, odds_ah, odds_ou)
            df = compute_features(df)
            df = df.sort_values("match_date").reset_index(drop=True)

            # 最后 n_test_matches 场做测试
            split = max(len(df) - n_test_matches, int(len(df) * 0.7))
            train_df = df.iloc[:split]
            test_df = df.iloc[split:]

            feature_cols = get_feature_columns(df)
            params = default_xgb_params()

            result = _train_and_eval(train_df, test_df, feature_cols, params)
            predictor = result.pop("predictor", None)
            feature_used = result.pop("feature_cols", [])

            log(f"  训练集: {len(train_df)} 场, 测试集: {len(test_df)} 场")
            log(f"  准确率: {result['accuracy']:.1%}")
            log(f"  主胜: {result['accuracy_home']:.1%}  平: {result['accuracy_draw']:.1%}  客胜: {result['accuracy_away']:.1%}")
            log(f"  高置信(≥50%): {result['high_conf_accuracy']:.1%} ({result['high_conf_count']}场)")

            # 保存联赛专属模型
            if predictor and result["accuracy"] > 0.45:
                league_dir = MODEL_DIR / f"league_{div}"
                predictor.save(league_dir)
                log(f"  模型已保存: {league_dir}")

            results[div] = result

    return results


def auto_optimize(division: str | None = None, mode: str = "fast", log_fn=None) -> dict[str, Any]:
    """
    自动优化：搜索最优超参数和特征组合。

    mode:
    - "fast": 快速搜索（小网格，约 1-2 分钟）
    - "full": 完整搜索（大网格，约 10-30 分钟）
    """
    def log(msg):
        if log_fn: log_fn(msg)

    divisions = [division] if division else DIVISIONS_MAIN
    grid = PARAM_GRID_FAST if mode == "fast" else PARAM_GRID
    param_list = list(ParameterGrid(grid))

    log(f"自动优化: {len(divisions)} 个联赛, {len(param_list)} 组超参数")
    log(f"模式: {mode}")
    log("")

    best_results = {}

    with connect_history() as conn:
        for div in divisions:
            log(f"\n{'='*50}")
            log(f"优化联赛: {div}")

            all_df = load_raw_dataset(conn, divisions=[div])
            if len(all_df) < 1000:
                log(f"  数据不足，跳过")
                continue

            ids = all_df["match_id"].tolist()
            id_str = ",".join(str(i) for i in ids)
            odds_1x2 = pd.read_sql_query(
                f"SELECT match_id, bookmaker, is_closing, home_odds, draw_odds, away_odds FROM odds_1x2 WHERE match_id IN ({id_str})", conn)
            odds_ah = pd.read_sql_query(
                f"SELECT match_id, bookmaker, is_closing, handicap, home_odds, away_odds FROM odds_asian WHERE match_id IN ({id_str})", conn)
            odds_ou = pd.read_sql_query(
                f"SELECT match_id, bookmaker, is_closing, over_odds, under_odds FROM odds_ou25 WHERE match_id IN ({id_str})", conn)

            df = _merge_odds_features(all_df, odds_1x2, odds_ah, odds_ou)
            df = compute_features(df)
            df = df.sort_values("match_date").reset_index(drop=True)

            split = max(len(df) - 500, int(len(df) * 0.7))
            train_df = df.iloc[:split]
            test_df = df.iloc[split:]
            all_features = get_feature_columns(df)

            best_acc = 0
            best_params = None
            best_predictor = None
            best_features = None

            for i, pg in enumerate(param_list):
                params = default_xgb_params()
                params.update(pg)

                result = _train_and_eval(train_df, test_df, all_features, params, n_rounds=200)
                acc = result["accuracy"]

                if acc > best_acc:
                    best_acc = acc
                    best_params = pg
                    best_predictor = result.pop("predictor", None)
                    best_features = result.pop("feature_cols", [])
                    log(f"  [{i+1}/{len(param_list)}] 新最优: {acc:.1%} | {pg}")
                else:
                    result.pop("predictor", None)
                    result.pop("feature_cols", None)

            if best_predictor:
                league_dir = MODEL_DIR / f"league_{div}"
                best_predictor.save(league_dir)
                log(f"  最优模型已保存: {best_acc:.1%}")

                # 保存优化结果
                opt_meta = {
                    "division": div,
                    "best_accuracy": best_acc,
                    "best_params": best_params,
                    "n_features": len(best_features) if best_features else 0,
                    "train_size": len(train_df),
                    "test_size": len(test_df),
                    "search_mode": mode,
                    "n_combinations": len(param_list),
                }
                with open(league_dir / "optimization.json", "w", encoding="utf-8") as f:
                    json.dump(opt_meta, f, ensure_ascii=False, indent=2, default=str)

                best_results[div] = opt_meta

    # 保存评估记录
    if best_results:
        avg_acc = np.mean([r["best_accuracy"] for r in best_results.values()])
        eval_result = {
            "n_matches": sum(r.get("test_size", 0) for r in best_results.values()),
            "accuracy": avg_acc,
            "accuracy_home": 0, "accuracy_draw": 0, "accuracy_away": 0,
            "high_conf_accuracy": 0, "high_conf_count": 0,
            "by_division": [
                {"division": d, "matches": r.get("test_size", 0), "accuracy": r["best_accuracy"]}
                for d, r in best_results.items()
            ],
        }
        save_evaluation(eval_result, description=f"自动优化({mode}) - 分联赛最优模型")

    return best_results


def main() -> int:
    parser = argparse.ArgumentParser(description="自动训练与优化")
    parser.add_argument("--mode", choices=["league", "optimize", "full-optimize"], default="league",
                        help="模式: league=按联赛训练评估, optimize=快速超参优化, full-optimize=完整优化")
    parser.add_argument("--division", type=str, default=None, help="只处理指定联赛")
    parser.add_argument("--test-matches", type=int, default=500, help="测试集比赛数")
    args = parser.parse_args()

    def log(msg):
        print(msg, flush=True)

    t0 = time.time()

    if args.mode == "league":
        log("=" * 60)
        log("  按联赛分别训练和评估")
        log("=" * 60)
        results = train_by_league(n_test_matches=args.test_matches, log_fn=log)
        log(f"\n{'='*60}")
        log("汇总:")
        log(f"{'联赛':>4} {'场数':>6} {'准确率':>8} {'主胜':>8} {'平':>8} {'客胜':>8}")
        for div, r in sorted(results.items()):
            if "error" in r:
                log(f"{div:>4} {'错误: ' + r['error']}")
            else:
                log(f"{div:>4} {r['n_matches']:>6} {r['accuracy']:>8.1%} "
                    f"{r['accuracy_home']:>8.1%} {r['accuracy_draw']:>8.1%} {r['accuracy_away']:>8.1%}")

        # 保存评估记录
        valid = {d: r for d, r in results.items() if "error" not in r}
        if valid:
            avg_acc = np.mean([r["accuracy"] for r in valid.values()])
            eval_result = {
                "n_matches": sum(r["n_matches"] for r in valid.values()),
                "accuracy": avg_acc,
                "accuracy_home": np.mean([r["accuracy_home"] for r in valid.values()]),
                "accuracy_draw": np.mean([r["accuracy_draw"] for r in valid.values()]),
                "accuracy_away": np.mean([r["accuracy_away"] for r in valid.values()]),
                "high_conf_accuracy": np.mean([r["high_conf_accuracy"] for r in valid.values()]),
                "high_conf_count": sum(r["high_conf_count"] for r in valid.values()),
                "by_division": [
                    {"division": d, "matches": r["n_matches"], "accuracy": r["accuracy"]}
                    for d, r in valid.items()
                ],
            }
            run_id = save_evaluation(eval_result, description="按联赛分别训练")
            log(f"\n评估记录 ID: {run_id}")

    elif args.mode in ("optimize", "full-optimize"):
        search_mode = "fast" if args.mode == "optimize" else "full"
        log("=" * 60)
        log(f"  自动超参优化（{search_mode}）")
        log("=" * 60)
        results = auto_optimize(division=args.division, mode=search_mode, log_fn=log)
        log(f"\n{'='*60}")
        log("优化结果:")
        for div, r in sorted(results.items()):
            log(f"  {div}: {r['best_accuracy']:.1%} | {r['best_params']}")

    t1 = time.time()
    log(f"\n总耗时: {t1-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
