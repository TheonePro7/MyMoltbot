"""
训练脚本：一键完成特征构建→模型训练→回测→保存。
命令行入口：python3 -m ai.train
"""

from __future__ import annotations

import argparse
import sys
import time

from ai.backtest import backtest_summary, rolling_backtest
from ai.features import build_dataset, get_feature_columns
from ai.xgboost_model import MatchPredictor


def main() -> int:
    parser = argparse.ArgumentParser(description="训练足彩预测模型")
    parser.add_argument("--divisions", nargs="*", default=None,
                        help="联赛代码（默认全部有数据的联赛）")
    parser.add_argument("--min-season", default=None,
                        help="最早赛季（如 0607）")
    parser.add_argument("--n-rounds", type=int, default=500,
                        help="XGBoost 迭代轮数")
    parser.add_argument("--backtest", action="store_true",
                        help="执行滚动回测")
    parser.add_argument("--train-seasons", type=int, default=5,
                        help="回测训练窗口（赛季数）")
    parser.add_argument("--save", action="store_true", default=True,
                        help="保存模型（默认是）")
    args = parser.parse_args()

    print("=" * 60, flush=True)
    print("  MyMoltbot 足彩预测模型训练", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)

    # 1. 构建数据集
    print("1. 构建特征数据集...", flush=True)
    t0 = time.time()
    df = build_dataset(divisions=args.divisions, min_season=args.min_season)
    if df.empty:
        print("错误：无可用数据", flush=True)
        return 1
    feature_cols = get_feature_columns(df)
    t1 = time.time()
    print(f"   数据集: {len(df)} 场比赛, {len(feature_cols)} 个特征", flush=True)
    print(f"   赛季范围: {df['season'].min()} ~ {df['season'].max()}", flush=True)
    print(f"   联赛: {sorted(df['division'].unique())}", flush=True)
    print(f"   耗时: {t1-t0:.1f}s", flush=True)
    print(flush=True)

    # 2. 训练模型
    print("2. 训练 XGBoost 模型...", flush=True)
    t0 = time.time()
    predictor = MatchPredictor(n_rounds=args.n_rounds)
    result = predictor.train(df, feature_cols=feature_cols)
    t1 = time.time()
    print(f"   训练集: {result['train_size']} 场", flush=True)
    print(f"   验证集: {result['val_size']} 场", flush=True)
    print(f"   最佳迭代: {result['best_iteration']} 轮", flush=True)
    print(f"   验证集准确率: {result['val_accuracy']:.1%}", flush=True)
    print(f"   验证集 LogLoss: {result['val_logloss']:.4f}", flush=True)
    print(f"   耗时: {t1-t0:.1f}s", flush=True)
    print(flush=True)

    # 3. 特征重要性
    print("3. 特征重要性 Top 15:", flush=True)
    imp = predictor.feature_importance()
    for _, row in imp.head(15).iterrows():
        bar = "█" * int(row["importance"] / imp["importance"].max() * 30)
        print(f"   {row['feature']:>30}: {bar} ({row['importance']:.0f})", flush=True)
    print(flush=True)

    # 4. 分类报告
    report = result.get("val_report", {})
    print("4. 分类报告（验证集）:", flush=True)
    print(f"   {'类别':>10} {'精确率':>8} {'召回率':>8} {'F1':>8}", flush=True)
    for label in ["主胜(H)", "平(D)", "客胜(A)"]:
        if label in report:
            r = report[label]
            print(f"   {label:>10} {r['precision']:>8.1%} {r['recall']:>8.1%} {r['f1-score']:>8.1%}", flush=True)
    print(flush=True)

    # 5. 保存模型
    if args.save:
        path = predictor.save()
        print(f"5. 模型已保存到: {path.parent}", flush=True)
        print(flush=True)

    # 6. 滚动回测
    if args.backtest:
        print("6. 执行滚动回测...", flush=True)
        t0 = time.time()
        bt_results = rolling_backtest(
            df,
            train_seasons=args.train_seasons,
            confidence_threshold=0.0,
        )
        summary = backtest_summary(bt_results)
        t1 = time.time()

        print(f"   回测比赛数: {summary['total_matches']}", flush=True)
        print(f"   总命中率: {summary['accuracy']:.1%}", flush=True)
        print(f"   全下注 ROI: {summary['roi_pct']:.1f}%", flush=True)
        print(f"   高置信度(≥50%) ROI: {summary['high_conf_roi_pct']:.1f}%（{summary['high_conf_bets']} 注）", flush=True)
        print(flush=True)

        print("   按赛季:", flush=True)
        print(f"   {'赛季':>6} {'场数':>6} {'命中率':>8} {'ROI':>8}", flush=True)
        for s in summary["by_season"]:
            print(f"   {s['season']:>6} {s['matches']:>6} {s['accuracy']:>8.1%} {s['roi']:>7.1f}%", flush=True)
        print(flush=True)

        print("   按联赛:", flush=True)
        print(f"   {'联赛':>4} {'场数':>6} {'命中率':>8} {'ROI':>8}", flush=True)
        for d in summary["by_division"]:
            print(f"   {d['division']:>4} {d['matches']:>6} {d['accuracy']:>8.1%} {d['roi']:>7.1f}%", flush=True)
        print(flush=True)

        if summary.get("by_confidence"):
            print("   按置信度:", flush=True)
            print(f"   {'区间':>15} {'场数':>6} {'命中率':>8}", flush=True)
            for c in summary["by_confidence"]:
                print(f"   {str(c['conf_bin']):>15} {c['matches']:>6} {c['accuracy']:>8.1%}", flush=True)

        print(f"\n   回测耗时: {t1-t0:.1f}s", flush=True)

    print(flush=True)
    print("=" * 60, flush=True)
    print("  完成！", flush=True)
    print("=" * 60, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
