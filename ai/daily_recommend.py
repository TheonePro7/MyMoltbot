"""
每日北单推荐：拉取当日北单比赛 → 匹配联赛 → 用联赛模型预测 → 生成串关推荐。

用法：python3 -m ai.daily_recommend
"""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ai.features import compute_features, _merge_odds_features
from ai.xgboost_model import MatchPredictor
from football_odds.bjdc import fetch_bjdc
from football_odds.history_db import connect_history
from football_odds.league_names import get_cn_name

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"

LEAGUE_CN_TO_CODE = {
    '英超': 'E0', '英冠': 'E1', '英甲': 'E2', '英乙': 'E3',
    '西甲': 'SP1', '西乙': 'SP2', '德甲': 'D1', '德乙': 'D2',
    '意甲': 'I1', '意乙': 'I2', '法甲': 'F1', '法乙': 'F2',
    '荷甲': 'N1', '比甲': 'B1', '葡超': 'P1', '土超': 'T1',
    '希腊超': 'G1', '苏超': 'SC0', '苏冠': 'SC1',
}


def get_daily_recommendations(expect: str | None = None,
                                min_confidence: float = 0.6) -> dict[str, Any]:
    """
    获取每日北单推荐。
    expect: 北单期号，None 则拉取当期。
    """
    with open(Path(__file__).resolve().parent.parent / "data" / "team_name_mapping.json", "r", encoding="utf-8") as f:
        mapping = json.load(f)

    # 拉取北单比赛
    bd_rows = fetch_bjdc(expect=expect)
    if not bd_rows:
        return {"error": "无北单比赛数据", "matches": [], "parlays": []}

    # 匹配联赛 + 预测
    predictors_cache: dict[str, MatchPredictor] = {}
    predictions = []

    with connect_history() as conn:
        for br in bd_rows:
            if not br.home_team or not br.away_team:
                continue

            league_code = LEAGUE_CN_TO_CODE.get(br.league)
            en_home = mapping.get(br.home_team)
            en_away = mapping.get(br.away_team)

            if not league_code or not en_home or not en_away:
                continue

            # 加载联赛模型
            if league_code not in predictors_cache:
                league_dir = MODEL_DIR / f'league_{league_code}'
                if not (league_dir / 'xgb_match_predictor.json').exists():
                    continue
                try:
                    predictors_cache[league_code] = MatchPredictor.load(league_dir)
                except Exception:
                    continue

            # 在联赛历史中找这支球队的最近比赛做特征
            en_match = conn.execute(
                """SELECT id FROM matches WHERE division=? AND home_team=? AND away_team=?
                   ORDER BY match_date DESC LIMIT 1""",
                (league_code, en_home, en_away)
            ).fetchone()

            if not en_match:
                en_match = conn.execute(
                    """SELECT id FROM matches WHERE division=? AND (home_team=? OR away_team=?)
                       ORDER BY match_date DESC LIMIT 1""",
                    (league_code, en_home, en_home)
                ).fetchone()

            if not en_match:
                continue

            mid = en_match['id']
            match_df = pd.read_sql_query(f"SELECT * FROM matches WHERE id={mid}", conn)
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

            pred_label = row['pred_label']
            label_map = {'H': '主胜', 'D': '平', 'A': '客胜'}

            sp_map = {'H': br.bd_sp_win, 'D': br.bd_sp_draw, 'A': br.bd_sp_lose}
            pred_sp = sp_map.get(pred_label)

            predictions.append({
                'match_num': br.match_num,
                'league': br.league,
                'league_code': league_code,
                'kickoff': br.kickoff,
                'home_team': br.home_team,
                'away_team': br.away_team,
                'handicap': br.handicap,
                'pred_label': pred_label,
                'pred_text': label_map.get(pred_label, pred_label),
                'confidence': float(row['confidence']),
                'prob_h': float(row['prob_home']),
                'prob_d': float(row['prob_draw']),
                'prob_a': float(row['prob_away']),
                'sp_h': br.bd_sp_win,
                'sp_d': br.bd_sp_draw,
                'sp_a': br.bd_sp_lose,
                'pred_sp': pred_sp,
                'score': br.score_text,
                'match_date': br.match_date,
            })

    predictions.sort(key=lambda x: x['confidence'], reverse=True)

    # 筛选高置信度
    high_conf = [p for p in predictions if p['confidence'] >= min_confidence]

    # 生成串关推荐
    parlays = {}
    for size, name in [(2, '2串1'), (3, '3串1'), (4, '4串1')]:
        if len(high_conf) >= size:
            top = high_conf[:max(size, 6)]
            combos = list(itertools.combinations(range(len(top)), size))[:5]
            parlay_list = []
            for combo in combos:
                legs = [top[i] for i in combo]
                total_odds = 1.0
                for leg in legs:
                    if leg.get('pred_sp') and leg['pred_sp'] > 0:
                        total_odds *= leg['pred_sp']
                parlay_list.append({
                    'legs': legs,
                    'total_odds': round(total_odds, 2),
                    'stake': 2.0,
                    'potential_payout': round(total_odds * 2, 2),
                })
            parlays[name] = parlay_list

    return {
        'total_matches': len(bd_rows),
        'predictable': len(predictions),
        'high_confidence': len(high_conf),
        'min_confidence': min_confidence,
        'predictions': predictions,
        'parlays': parlays,
        'expect': expect,
        'match_date': bd_rows[0].match_date if bd_rows else '',
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="每日北单推荐")
    parser.add_argument("--expect", type=str, default=None, help="北单期号")
    parser.add_argument("--confidence", type=float, default=0.6, help="最低置信度")
    args = parser.parse_args()

    def log(msg):
        print(msg, flush=True)

    log("=" * 60)
    log("  每日北单推荐")
    log("=" * 60)

    result = get_daily_recommendations(expect=args.expect, min_confidence=args.confidence)
    if 'error' in result:
        log(f"错误: {result['error']}")
        return 1

    log(f"北单总场数: {result['total_matches']}")
    log(f"可预测: {result['predictable']}")
    log(f"高置信(≥{args.confidence:.0%}): {result['high_confidence']}")
    log("")

    # 推荐列表
    log(f"{'场次':>4} {'联赛':>6} {'时间':>6} {'主队':>10} {'客队':>10} {'预测':>4} {'置信度':>6} {'SP':>6}")
    log("-" * 70)
    for p in result['predictions']:
        sp = f"{p['pred_sp']:.2f}" if p.get('pred_sp') else '-'
        conf = f"{p['confidence']:.0%}"
        marker = ' ★' if p['confidence'] >= args.confidence else ''
        log(f"{p['match_num']:>4} {p['league']:>6} {p['kickoff']:>6} {p['home_team']:>10} "
            f"{p['away_team']:>10} {p['pred_text']:>4} {conf:>6} {sp:>6}{marker}")

    # 串关推荐
    for name, parlays in result.get('parlays', {}).items():
        log(f"\n{'='*40}")
        log(f"  {name} 推荐方案")
        log(f"{'='*40}")
        for i, p in enumerate(parlays):
            log(f"\n方案 {i+1} (总赔率 {p['total_odds']}, 2元可得 ¥{p['potential_payout']}):")
            for leg in p['legs']:
                log(f"  {leg['league']:>6} {leg['home_team']:>10} vs {leg['away_team']:<10} "
                    f"→ {leg['pred_text']} (置信{leg['confidence']:.0%}, SP:{leg.get('pred_sp', '-')})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
