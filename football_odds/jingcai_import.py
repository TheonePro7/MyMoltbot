"""
竞彩 + 北单数据导入：从 500.com 采集当日比赛数据，写入历史数据库。
与五大联赛历史数据关联（通过球队名匹配）。

同时支持对导入的比赛做模型预测。

用法：
  python3 -m football_odds.jingcai_import           # 导入当日竞彩+北单
  python3 -m football_odds.jingcai_import --predict  # 导入并预测
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from football_odds.bjdc import BjdcRow, fetch_bjdc
from football_odds.jc500 import fetch_jc_rows
from football_odds.jc_rows import JcRow
from football_odds.history_db import (
    connect_history,
    insert_match,
    insert_odds_1x2,
    insert_odds_asian,
)


def _current_season() -> str:
    now = datetime.now(timezone.utc)
    y = now.year % 100
    if now.month >= 7:
        return f"{y:02d}{(y + 1):02d}"
    else:
        return f"{(y - 1):02d}{y:02d}"


def _parse_handicap_float(s: str) -> float | None:
    """解析让球字符串为浮点数。"""
    s = s.strip()
    if not s or s == "0":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def import_jingcai(date_str: str | None = None, log_fn=None) -> dict[str, Any]:
    """
    导入竞彩（jczq）当日比赛到历史数据库。
    """
    def log(msg):
        if log_fn: log_fn(msg)

    from web.data_service import cst_today_str
    date = date_str or cst_today_str()
    season = _current_season()

    log(f"竞彩导入: {date}")

    try:
        jc_rows = fetch_jc_rows(date)
    except Exception as e:
        log(f"  竞彩抓取失败: {e}")
        return {"error": str(e), "jc_count": 0}

    if not jc_rows:
        log("  竞彩无比赛数据")
        return {"jc_count": 0}

    count = 0
    with connect_history() as conn:
        for jr in jc_rows:
            if not jr.home_team or not jr.away_team:
                continue

            match_data = {
                "division": "JC",
                "season": season,
                "match_date": date,
                "match_time": jr.kickoff.split(" ")[-1] if " " in jr.kickoff else jr.kickoff,
                "home_team": jr.home_team,
                "away_team": jr.away_team,
                "fthg": None, "ftag": None, "ftr": None,
                "hthg": None, "htag": None, "htr": None,
                "referee": None,
                "home_shots": None, "away_shots": None,
                "home_sot": None, "away_sot": None,
                "home_corners": None, "away_corners": None,
                "home_fouls": None, "away_fouls": None,
                "home_yellows": None, "away_yellows": None,
                "home_reds": None, "away_reds": None,
            }

            # 如果有比分
            if jr.score_text and re.match(r'^\d+:\d+$', jr.score_text):
                parts = jr.score_text.split(":")
                hg, ag = int(parts[0]), int(parts[1])
                match_data["fthg"] = hg
                match_data["ftag"] = ag
                match_data["ftr"] = "H" if hg > ag else ("D" if hg == ag else "A")

            match_id = insert_match(conn, match_data)
            if match_id <= 0:
                continue

            # 竞彩不让球胜平负 SP
            if jr.nspf:
                h = next((sp for v, sp in jr.nspf if v == "3"), None)
                d = next((sp for v, sp in jr.nspf if v == "1"), None)
                a = next((sp for v, sp in jr.nspf if v == "0"), None)
                if h is not None:
                    insert_odds_1x2(conn, match_id, "竞彩SP", 0, h, d, a)

            # 竞彩让球胜平负 SP
            if jr.spf:
                h = next((sp for v, sp in jr.spf if v == "3"), None)
                d = next((sp for v, sp in jr.spf if v == "1"), None)
                a = next((sp for v, sp in jr.spf if v == "0"), None)
                handicap = _parse_handicap_float(jr.handicap)
                if h is not None:
                    insert_odds_1x2(conn, match_id, "竞彩让球SP", 0, h, d, a)
                    if handicap is not None:
                        insert_odds_asian(conn, match_id, "竞彩", 0, handicap, h, a)

            count += 1

        conn.commit()

    log(f"  竞彩导入: {count} 场比赛")
    return {"jc_count": count}


def import_bjdc(log_fn=None) -> dict[str, Any]:
    """导入北京单场当日比赛到历史数据库。"""
    def log(msg):
        if log_fn: log_fn(msg)

    season = _current_season()

    log("北单导入...")
    try:
        bd_rows = fetch_bjdc()
    except Exception as e:
        log(f"  北单抓取失败: {e}")
        return {"error": str(e), "bd_count": 0}

    if not bd_rows:
        log("  北单无比赛数据")
        return {"bd_count": 0}

    count = 0
    with connect_history() as conn:
        for br in bd_rows:
            if not br.home_team or not br.away_team:
                continue

            date = br.match_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

            match_data = {
                "division": "BD",
                "season": season,
                "match_date": date,
                "match_time": br.kickoff,
                "home_team": br.home_team,
                "away_team": br.away_team,
                "fthg": None, "ftag": None, "ftr": None,
                "hthg": None, "htag": None, "htr": None,
                "referee": None,
                "home_shots": None, "away_shots": None,
                "home_sot": None, "away_sot": None,
                "home_corners": None, "away_corners": None,
                "home_fouls": None, "away_fouls": None,
                "home_yellows": None, "away_yellows": None,
                "home_reds": None, "away_reds": None,
            }

            if br.score_text and re.match(r'^\d+:\d+$', br.score_text):
                parts = br.score_text.split(":")
                hg, ag = int(parts[0]), int(parts[1])
                match_data["fthg"] = hg
                match_data["ftag"] = ag
                match_data["ftr"] = "H" if hg > ag else ("D" if hg == ag else "A")

            match_id = insert_match(conn, match_data)
            if match_id <= 0:
                continue

            # 北单 SP（让球胜平负）
            if br.bd_sp_win is not None:
                insert_odds_1x2(conn, match_id, "北单SP", 0,
                                br.bd_sp_win, br.bd_sp_draw, br.bd_sp_lose)
                handicap = _parse_handicap_float(br.handicap)
                if handicap is not None:
                    insert_odds_asian(conn, match_id, "北单", 0,
                                      handicap, br.bd_sp_win, br.bd_sp_lose)

            # 竞彩 SP（不让球，如果有）
            if br.jc_sp_win is not None:
                insert_odds_1x2(conn, match_id, "竞彩SP", 0,
                                br.jc_sp_win, br.jc_sp_draw, br.jc_sp_lose)

            count += 1

        conn.commit()

    log(f"  北单导入: {count} 场比赛")
    return {"bd_count": count}


def predict_jingcai(log_fn=None) -> list[dict]:
    """对竞彩/北单中有赔率的比赛做预测。"""
    def log(msg):
        if log_fn: log_fn(msg)

    import pandas as pd
    from ai.features import compute_features, _merge_odds_features
    from ai.xgboost_model import MatchPredictor

    model_dir = Path(__file__).resolve().parent.parent / "data" / "models"

    with connect_history() as conn:
        matches = pd.read_sql_query(
            """SELECT m.id as match_id, m.division, m.season, m.match_date,
                      m.home_team, m.away_team, m.fthg, m.ftag, m.ftr,
                      m.hthg, m.htag, m.htr, m.home_shots, m.away_shots,
                      m.home_sot, m.away_sot, m.home_corners, m.away_corners,
                      m.home_fouls, m.away_fouls, m.home_yellows, m.away_yellows,
                      m.home_reds, m.away_reds
               FROM matches m
               WHERE m.division IN ('JC', 'BD') AND m.ftr IS NULL
               ORDER BY m.match_date DESC, m.id DESC""",
            conn,
        )

        if matches.empty:
            log("  无待预测的竞彩/北单比赛")
            return []

        ids = matches["match_id"].tolist()
        id_str = ",".join(str(i) for i in ids)
        odds_1x2 = pd.read_sql_query(
            f"SELECT match_id, bookmaker, is_closing, home_odds, draw_odds, away_odds FROM odds_1x2 WHERE match_id IN ({id_str})", conn)
        odds_ah = pd.read_sql_query(
            f"SELECT match_id, bookmaker, is_closing, handicap, home_odds, away_odds FROM odds_asian WHERE match_id IN ({id_str})", conn)
        odds_ou = pd.DataFrame()

    df = _merge_odds_features(matches, odds_1x2, odds_ah, odds_ou)
    df = compute_features(df)

    # 过滤无赔率的
    odds_cols = [c for c in df.columns if any(k in c for k in ["sp", "odds", "ip_", "fp_"])]
    if odds_cols:
        has_data = df[odds_cols].notna().any(axis=1)
        df = df[has_data].copy()

    if df.empty:
        log("  所有比赛均无赔率数据，无法预测")
        return []

    # 用通用模型预测
    try:
        predictor = MatchPredictor.load(model_dir)
    except Exception as e:
        log(f"  模型加载失败: {e}")
        return []

    preds = predictor.predict(df)

    results = []
    label_map = {"H": "主胜", "D": "平", "A": "客胜"}
    for _, row in preds.iterrows():
        results.append({
            "match_id": int(row["match_id"]),
            "division": row["division"],
            "match_date": row["match_date"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "prob_home": round(float(row["prob_home"]), 4),
            "prob_draw": round(float(row["prob_draw"]), 4),
            "prob_away": round(float(row["prob_away"]), 4),
            "pred_label": row["pred_label"],
            "pred_text": label_map.get(row["pred_label"], row["pred_label"]),
            "confidence": round(float(row["confidence"]), 4),
        })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    log(f"  预测完成: {len(results)} 场比赛")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="竞彩 + 北单数据导入与预测")
    parser.add_argument("--date", type=str, default=None, help="竞彩日期（默认今天）")
    parser.add_argument("--predict", action="store_true", help="导入后做预测")
    parser.add_argument("--only-predict", action="store_true", help="只做预测（不导入）")
    parser.add_argument("--bjdc", action="store_true", default=True, help="导入北单（默认是）")
    parser.add_argument("--jc", action="store_true", default=True, help="导入竞彩（默认是）")
    args = parser.parse_args()

    def log(msg):
        print(msg, flush=True)

    log("=" * 50)
    log("  竞彩 + 北单 数据导入")
    log("=" * 50)

    if not args.only_predict:
        # 导入竞彩
        jc_result = import_jingcai(date_str=args.date, log_fn=log)
        # 导入北单
        bd_result = import_bjdc(log_fn=log)

        log("")
        log(f"导入汇总: 竞彩 {jc_result.get('jc_count', 0)} 场, 北单 {bd_result.get('bd_count', 0)} 场")

    if args.predict or args.only_predict:
        log("")
        log("=" * 50)
        log("  竞彩/北单 智能预测")
        log("=" * 50)
        preds = predict_jingcai(log_fn=log)
        if preds:
            log("")
            log(f"{'来源':>4} {'日期':>12} {'主队':>12} {'客队':>12} {'预测':>4} {'置信度':>6}")
            log("-" * 65)
            for p in preds:
                conf_pct = f"{p['confidence']:.0%}"
                log(f"{p['division']:>4} {p['match_date']:>12} {p['home_team']:>12} {p['away_team']:>12} "
                    f"{p['pred_text']:>4} {conf_pct:>6}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
