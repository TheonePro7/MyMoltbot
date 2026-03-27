"""预测 API：加载已训练模型，对比赛做预测；评估系统 API。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api.schemas import PredictionItem
from ai.features import compute_features, get_feature_columns, _merge_odds_features
from ai.xgboost_model import MatchPredictor
from ai.evaluate import evaluate_recent, save_evaluation, list_evaluations
from football_odds.history_db import connect_history

router = APIRouter(prefix="/api/prediction", tags=["智能预测"])

_predictor: MatchPredictor | None = None

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"


def _get_predictor() -> MatchPredictor:
    global _predictor
    if _predictor is None:
        model_file = MODEL_DIR / "xgb_match_predictor.json"
        if not model_file.exists():
            raise HTTPException(status_code=503, detail="模型尚未训练，请先运行 python3 -m ai.train")
        _predictor = MatchPredictor.load(MODEL_DIR)
    return _predictor


def _load_matches_with_odds(conn, where_clause: str, params=None):
    """通用方法：加载比赛并合并赔率数据。"""
    matches = pd.read_sql_query(
        f"""SELECT m.id as match_id, m.division, m.season, m.match_date,
                   m.home_team, m.away_team, m.fthg, m.ftag, m.ftr,
                   m.hthg, m.htag, m.htr, m.home_shots, m.away_shots,
                   m.home_sot, m.away_sot, m.home_corners, m.away_corners,
                   m.home_fouls, m.away_fouls, m.home_yellows, m.away_yellows,
                   m.home_reds, m.away_reds
            FROM matches m WHERE {where_clause}
            ORDER BY m.match_date DESC, m.id DESC""",
        conn,
        params=params or [],
    )
    if matches.empty:
        return matches

    match_ids = matches["match_id"].tolist()
    id_str = ",".join(str(i) for i in match_ids)

    odds_1x2 = pd.read_sql_query(
        f"SELECT match_id, bookmaker, is_closing, home_odds, draw_odds, away_odds FROM odds_1x2 WHERE match_id IN ({id_str})", conn)
    odds_ah = pd.read_sql_query(
        f"SELECT match_id, bookmaker, is_closing, handicap, home_odds, away_odds FROM odds_asian WHERE match_id IN ({id_str})", conn)
    odds_ou = pd.read_sql_query(
        f"SELECT match_id, bookmaker, is_closing, over_odds, under_odds FROM odds_ou25 WHERE match_id IN ({id_str})", conn)

    df = _merge_odds_features(matches, odds_1x2, odds_ah, odds_ou)
    return compute_features(df)


def _has_real_odds(df: pd.DataFrame) -> pd.Series:
    """判断每行是否有真实赔率数据（非全缺失）。"""
    odds_cols = [c for c in df.columns if any(k in c for k in ["b365", "ps_", "odds_mean", "ip_", "fp_"])]
    if not odds_cols:
        return pd.Series(False, index=df.index)
    return df[odds_cols].notna().any(axis=1)


@router.get("/upcoming", response_model=list[PredictionItem])
def predict_upcoming():
    """对有赔率数据的未赛比赛做预测。没有赔率的比赛不预测。"""
    predictor = _get_predictor()

    with connect_history() as conn:
        df = _load_matches_with_odds(conn, "m.ftr IS NULL")

    if df.empty:
        return []

    # 过滤掉没有赔率数据的比赛
    df = df[_has_real_odds(df)].copy()
    if df.empty:
        return []

    preds = predictor.predict(df)
    items: list[PredictionItem] = []
    for _, row in preds.iterrows():
        items.append(PredictionItem(
            match_id=int(row["match_id"]),
            home_team=row["home_team"],
            away_team=row["away_team"],
            match_date=row["match_date"],
            division=row["division"],
            prob_home=round(float(row["prob_home"]), 4),
            prob_draw=round(float(row["prob_draw"]), 4),
            prob_away=round(float(row["prob_away"]), 4),
            pred_label=row["pred_label"],
            confidence=round(float(row["confidence"]), 4),
        ))

    items.sort(key=lambda x: x.confidence, reverse=True)
    return items


@router.get("/evaluate")
def run_evaluation(
    matches: int = Query(2000, ge=100, le=5000, description="评估比赛数量"),
    desc: str = Query("", description="本次评估描述"),
):
    """对最近 N 场已结束比赛做预测，计算准确率并保存记录。"""
    result = evaluate_recent(n_matches=matches, description=desc)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    run_id = save_evaluation(result, description=desc)
    result["run_id"] = run_id
    return result


@router.get("/eval-history")
def get_eval_history():
    """获取所有历史评估记录。"""
    return list_evaluations()


@router.get("/model-info")
def model_info():
    """获取当前模型的元数据。"""
    predictor = _get_predictor()
    return predictor.metadata
