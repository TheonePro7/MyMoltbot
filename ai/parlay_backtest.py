"""
北单串关模拟回测：2串1 / 3串1 / 4串1。
用联赛模型预测北单已完场比赛，按置信度筛选后做串关组合，计算 ROI。

用法：python3 -m ai.parlay_backtest
"""

from __future__ import annotations

import argparse
import itertools
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

from ai.features import compute_features, get_feature_columns, _merge_odds_features
from ai.xgboost_model import MatchPredictor
from football_odds.history_db import connect_history
from football_odds.league_names import get_cn_name

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"
RESULT_DB = Path(__file__).resolve().parent.parent / "data" / "parlay_backtest.sqlite3"

LEAGUE_CN_TO_CODE = {
    '英超': 'E0', '英冠': 'E1', '英甲': 'E2', '英乙': 'E3',
    '西甲': 'SP1', '西乙': 'SP2', '德甲': 'D1', '德乙': 'D2',
    '意甲': 'I1', '意乙': 'I2', '法甲': 'F1', '法乙': 'F2',
    '荷甲': 'N1', '比甲': 'B1', '葡超': 'P1', '土超': 'T1',
    '希腊超': 'G1', '苏超': 'SC0', '苏冠': 'SC1',
}


def _init_result_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS parlay_runs (
            id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            description TEXT,
            parlay_type TEXT,
            min_confidence REAL,
            stake REAL,
            n_parlays INTEGER,
            n_wins INTEGER,
            total_staked REAL,
            total_payout REAL,
            profit REAL,
            roi_pct REAL,
            details_json TEXT
        );
    """)


def predict_beidan_matches(n_matches: int = 3000, min_confidence: float = 0.5) -> pd.DataFrame:
    """
    预测最近 N 场可匹配联赛的北单比赛。
    返回包含预测结果和赔率的 DataFrame。
    """
    with open(Path(__file__).resolve().parent.parent / "data" / "team_name_mapping.json", "r", encoding="utf-8") as f:
        mapping = json.load(f)

    with connect_history() as conn:
        bd_all = conn.execute(f'''
            SELECT id, home_team, away_team, fthg, ftag, ftr, match_date, 
                   match_time_bj, referee as league_cn
            FROM matches WHERE division='BD' AND ftr IS NOT NULL AND referee IS NOT NULL
            ORDER BY match_date DESC LIMIT {n_matches}
        ''').fetchall()

        results = []
        predictors_cache: dict[str, MatchPredictor] = {}

        for m in bd_all:
            league_code = LEAGUE_CN_TO_CODE.get(m['league_cn'])
            en_home = mapping.get(m['home_team'])
            en_away = mapping.get(m['away_team'])
            if not league_code or not en_home or not en_away:
                continue

            # 找联赛数据库中的同一场比赛
            en_match = conn.execute(
                'SELECT id FROM matches WHERE division=? AND home_team=? AND away_team=? AND match_date=?',
                (league_code, en_home, en_away, m['match_date'])
            ).fetchone()
            if not en_match:
                continue

            # 加载赔率
            mid = en_match['id']
            odds = conn.execute(
                'SELECT bookmaker, home_odds, draw_odds, away_odds FROM odds_1x2 WHERE match_id=? AND is_closing=0 AND bookmaker="B365"',
                (mid,)
            ).fetchone()

            if not odds or not odds['home_odds']:
                continue

            # 加载模型
            if league_code not in predictors_cache:
                league_dir = MODEL_DIR / f'league_{league_code}'
                try:
                    predictors_cache[league_code] = MatchPredictor.load(league_dir)
                except Exception:
                    continue

            # 构建特征做预测
            match_df = pd.read_sql_query(
                f"SELECT * FROM matches WHERE id={mid}", conn)
            match_df = match_df.rename(columns={'id': 'match_id'})
            o1x2 = pd.read_sql_query(f"SELECT * FROM odds_1x2 WHERE match_id={mid}", conn)
            oah = pd.read_sql_query(f"SELECT * FROM odds_asian WHERE match_id={mid}", conn)
            oou = pd.read_sql_query(f"SELECT * FROM odds_ou25 WHERE match_id={mid}", conn)

            df = _merge_odds_features(match_df, o1x2, oah, oou)
            df = compute_features(df, add_team_features=False)
            df = df.replace([np.inf, -np.inf], np.nan)

            predictor = predictors_cache[league_code]
            try:
                pred = predictor.predict(df)
                row = pred.iloc[0]
            except Exception:
                continue

            # 北单 SP 赔率
            bd_odds = conn.execute(
                "SELECT home_odds, draw_odds, away_odds FROM odds_1x2 WHERE match_id=? AND bookmaker='北单SP'",
                (m['id'],)
            ).fetchone()

            sp_h = bd_odds['home_odds'] if bd_odds else odds['home_odds']
            sp_d = bd_odds['draw_odds'] if bd_odds else odds['draw_odds']
            sp_a = bd_odds['away_odds'] if bd_odds else odds['away_odds']

            pred_label = row['pred_label']
            if pred_label == 'H':
                pred_odds = sp_h
            elif pred_label == 'D':
                pred_odds = sp_d
            else:
                pred_odds = sp_a

            results.append({
                'bd_id': m['id'],
                'match_date': m['match_date'],
                'match_time_bj': m['match_time_bj'],
                'home_cn': m['home_team'],
                'away_cn': m['away_team'],
                'league_cn': m['league_cn'],
                'league_code': league_code,
                'actual': m['ftr'],
                'fthg': m['fthg'],
                'ftag': m['ftag'],
                'pred_label': pred_label,
                'confidence': float(row['confidence']),
                'prob_h': float(row['prob_home']),
                'prob_d': float(row['prob_draw']),
                'prob_a': float(row['prob_away']),
                'sp_h': sp_h,
                'sp_d': sp_d,
                'sp_a': sp_a,
                'pred_odds': pred_odds,
                'correct': pred_label == m['ftr'],
            })

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('match_date').reset_index(drop=True)
    return df


def simulate_parlays(preds: pd.DataFrame, parlay_size: int = 2,
                      min_confidence: float = 0.6, stake: float = 2.0,
                      max_parlays_per_day: int = 5) -> dict[str, Any]:
    """
    模拟串关投注。
    parlay_size: 2=2串1, 3=3串1, 4=4串1
    只选当天的高置信度比赛做串关。
    """
    preds = preds[preds['confidence'] >= min_confidence].copy()
    if preds.empty:
        return {"error": "无符合条件的比赛"}

    # 按日期分组
    by_date = preds.groupby('match_date')
    all_parlays = []

    for date, day_preds in by_date:
        if len(day_preds) < parlay_size:
            continue

        # 按置信度排序，取前 N 场做串关组合
        day_sorted = day_preds.sort_values('confidence', ascending=False)
        top_n = min(len(day_sorted), max(parlay_size, 8))
        candidates = day_sorted.head(top_n)

        # 生成所有 C(top_n, parlay_size) 组合
        combos = list(itertools.combinations(candidates.index, parlay_size))
        combos = combos[:max_parlays_per_day]

        for combo in combos:
            legs = preds.loc[list(combo)]
            all_correct = all(legs['correct'])
            total_odds = legs['pred_odds'].prod()
            payout = stake * total_odds if all_correct else 0

            all_parlays.append({
                'date': date,
                'legs': [{
                    'home': row['home_cn'],
                    'away': row['away_cn'],
                    'league': row['league_cn'],
                    'pred': row['pred_label'],
                    'actual': row['actual'],
                    'score': f"{row['fthg']}:{row['ftag']}",
                    'correct': row['correct'],
                    'odds': row['pred_odds'],
                    'confidence': row['confidence'],
                } for _, row in legs.iterrows()],
                'total_odds': float(total_odds),
                'all_correct': all_correct,
                'stake': stake,
                'payout': payout,
            })

    if not all_parlays:
        return {"error": "无法组成串关"}

    n_parlays = len(all_parlays)
    n_wins = sum(1 for p in all_parlays if p['all_correct'])
    total_staked = n_parlays * stake
    total_payout = sum(p['payout'] for p in all_parlays)
    profit = total_payout - total_staked
    roi = (profit / total_staked * 100) if total_staked > 0 else 0

    # 按月统计
    by_month = {}
    for p in all_parlays:
        month = p['date'][:7]
        if month not in by_month:
            by_month[month] = {'parlays': 0, 'wins': 0, 'staked': 0, 'payout': 0}
        by_month[month]['parlays'] += 1
        by_month[month]['wins'] += 1 if p['all_correct'] else 0
        by_month[month]['staked'] += stake
        by_month[month]['payout'] += p['payout']

    monthly = []
    for month, stats in sorted(by_month.items()):
        stats['month'] = month
        stats['profit'] = stats['payout'] - stats['staked']
        stats['roi'] = (stats['profit'] / stats['staked'] * 100) if stats['staked'] > 0 else 0
        monthly.append(stats)

    return {
        'parlay_type': f'{parlay_size}串1',
        'min_confidence': min_confidence,
        'stake': stake,
        'n_parlays': n_parlays,
        'n_wins': n_wins,
        'win_rate': n_wins / n_parlays if n_parlays > 0 else 0,
        'total_staked': total_staked,
        'total_payout': total_payout,
        'profit': profit,
        'roi_pct': roi,
        'avg_odds': np.mean([p['total_odds'] for p in all_parlays]),
        'monthly': monthly,
        'sample_wins': [p for p in all_parlays if p['all_correct']][:10],
        'sample_losses': [p for p in all_parlays if not p['all_correct']][:5],
    }


def run_full_backtest(n_matches: int = 3000, stake: float = 2.0, log_fn=None) -> dict:
    """运行完整回测：单关 + 2串1 + 3串1 + 4串1。"""
    def log(msg):
        if log_fn: log_fn(msg)

    log("预测北单比赛...")
    preds = predict_beidan_matches(n_matches=n_matches)
    if preds.empty:
        return {"error": "无可预测比赛"}

    log(f"可预测: {len(preds)} 场, 日期范围: {preds['match_date'].min()} ~ {preds['match_date'].max()}")
    log(f"总准确率: {preds['correct'].mean():.1%}")

    all_results = {}

    # 不同置信度阈值 × 不同串关类型
    for min_conf in [0.5, 0.6, 0.7]:
        filtered = preds[preds['confidence'] >= min_conf]
        log(f"\n置信度 ≥{min_conf:.0%}: {len(filtered)} 场, 准确率 {filtered['correct'].mean():.1%}")

        # 单关
        singles = filtered.copy()
        n_bets = len(singles)
        n_wins = singles['correct'].sum()
        total_staked = n_bets * stake
        total_payout = sum(row['pred_odds'] * stake for _, row in singles.iterrows() if row['correct'])
        profit = total_payout - total_staked
        roi = (profit / total_staked * 100) if total_staked > 0 else 0
        key = f"单关_conf{int(min_conf*100)}"
        all_results[key] = {
            'type': '单关', 'min_confidence': min_conf,
            'n_bets': n_bets, 'n_wins': int(n_wins),
            'win_rate': float(n_wins / n_bets) if n_bets > 0 else 0,
            'total_staked': total_staked, 'total_payout': total_payout,
            'profit': profit, 'roi_pct': roi,
        }
        log(f"  单关: {n_bets}注, 命中{int(n_wins)}, 率{n_wins/n_bets:.1%}, ROI{roi:.1f}%")

        # 串关
        for parlay_size in [2, 3, 4]:
            result = simulate_parlays(preds, parlay_size=parlay_size,
                                       min_confidence=min_conf, stake=stake)
            if 'error' in result:
                log(f"  {parlay_size}串1: {result['error']}")
                continue
            key = f"{parlay_size}串1_conf{int(min_conf*100)}"
            all_results[key] = result
            log(f"  {parlay_size}串1: {result['n_parlays']}注, 命中{result['n_wins']}, "
                f"率{result['win_rate']:.1%}, ROI{result['roi_pct']:.1f}%")

    # 保存结果
    RESULT_DB.parent.mkdir(parents=True, exist_ok=True)
    sconn = sqlite3.connect(str(RESULT_DB))
    _init_result_db(sconn)
    run_id = str(uuid.uuid4())[:8]
    for key, result in all_results.items():
        sconn.execute(
            """INSERT INTO parlay_runs (id, run_at, description, parlay_type, min_confidence,
               stake, n_parlays, n_wins, total_staked, total_payout, profit, roi_pct, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"{run_id}_{key}", datetime.now(timezone.utc).isoformat(), key,
             result.get('type', key.split('_')[0]),
             result.get('min_confidence', 0),
             stake,
             result.get('n_parlays', result.get('n_bets', 0)),
             result.get('n_wins', 0),
             result.get('total_staked', 0),
             result.get('total_payout', 0),
             result.get('profit', 0),
             result.get('roi_pct', 0),
             json.dumps(result, ensure_ascii=False, default=str)),
        )
    sconn.commit()
    sconn.close()

    return {'run_id': run_id, 'results': all_results, 'total_predictions': len(preds)}


def main() -> int:
    parser = argparse.ArgumentParser(description="北单串关模拟回测")
    parser.add_argument("--matches", type=int, default=3000, help="回测比赛数")
    parser.add_argument("--stake", type=float, default=2.0, help="每注金额")
    args = parser.parse_args()

    def log(msg):
        print(msg, flush=True)

    log("=" * 60)
    log("  北单串关模拟回测")
    log("=" * 60)

    result = run_full_backtest(n_matches=args.matches, stake=args.stake, log_fn=log)
    if 'error' in result:
        log(f"错误: {result['error']}")
        return 1

    log(f"\n记录 ID: {result['run_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
