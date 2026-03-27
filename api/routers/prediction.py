"""预测 API：加载已训练模型，对即将开赛的比赛做预测。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.schemas import PredictionItem
from ai.features import build_dataset, compute_features, get_feature_columns
from ai.xgboost_model import MatchPredictor
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


@router.get("/upcoming", response_model=list[PredictionItem])
def predict_upcoming():
    """对数据库中尚无比赛结果的比赛做预测。"""
    predictor = _get_predictor()

    with connect_history() as conn:
        import pandas as pd
        matches = pd.read_sql_query(
            """SELECT m.id as match_id, m.division, m.season, m.match_date,
                      m.home_team, m.away_team, m.fthg, m.ftag, m.ftr,
                      m.hthg, m.htag, m.htr, m.home_shots, m.away_shots,
                      m.home_sot, m.away_sot, m.home_corners, m.away_corners,
                      m.home_fouls, m.away_fouls, m.home_yellows, m.away_yellows,
                      m.home_reds, m.away_reds
               FROM matches m
               WHERE m.ftr IS NULL
               ORDER BY m.match_date, m.id""",
            conn,
        )

        if matches.empty:
            return []

        match_ids = matches["match_id"].tolist()
        id_str = ",".join(str(i) for i in match_ids)

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

    from ai.features import _merge_odds_features
    df = _merge_odds_features(matches, odds_1x2, odds_ah, odds_ou)
    df = compute_features(df)

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


@router.get("/model-info")
def model_info():
    """获取当前模型的元数据。"""
    predictor = _get_predictor()
    return predictor.metadata
