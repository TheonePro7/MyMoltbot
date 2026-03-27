"""Pydantic 数据模型，供 FastAPI 路由使用。"""

from __future__ import annotations

from pydantic import BaseModel


class LeagueStat(BaseModel):
    division: str
    country: str | None = None
    league_name: str | None = None
    match_count: int
    first_season: str | None = None
    last_season: str | None = None


class DashboardStats(BaseModel):
    total_matches: int
    total_odds_records: int
    total_asian_records: int
    by_division: list[LeagueStat]


class MatchItem(BaseModel):
    match_id: int
    division: str
    season: str
    match_date: str
    home_team: str
    away_team: str
    fthg: int | None = None
    ftag: int | None = None
    ftr: str | None = None
    b365_h: float | None = None
    b365_d: float | None = None
    b365_a: float | None = None
    ps_h: float | None = None
    ps_d: float | None = None
    ps_a: float | None = None
    ah_handicap: float | None = None


class MatchListResponse(BaseModel):
    matches: list[MatchItem]
    total: int
    page: int
    total_pages: int


class OddsRecord(BaseModel):
    bookmaker: str
    is_closing: int
    home_odds: float | None = None
    draw_odds: float | None = None
    away_odds: float | None = None
    overround: float | None = None


class AsianOddsRecord(BaseModel):
    bookmaker: str
    is_closing: int
    handicap: float | None = None
    home_odds: float | None = None
    away_odds: float | None = None


class OURecord(BaseModel):
    bookmaker: str
    is_closing: int
    over_odds: float | None = None
    under_odds: float | None = None


class MatchDetail(BaseModel):
    match_id: int
    division: str
    season: str
    match_date: str
    match_time: str | None = None
    home_team: str
    away_team: str
    fthg: int | None = None
    ftag: int | None = None
    ftr: str | None = None
    hthg: int | None = None
    htag: int | None = None
    referee: str | None = None
    home_shots: int | None = None
    away_shots: int | None = None
    home_sot: int | None = None
    away_sot: int | None = None
    home_corners: int | None = None
    away_corners: int | None = None
    home_fouls: int | None = None
    away_fouls: int | None = None
    home_yellows: int | None = None
    away_yellows: int | None = None
    home_reds: int | None = None
    away_reds: int | None = None
    odds_1x2: list[OddsRecord] = []
    odds_asian: list[AsianOddsRecord] = []
    odds_ou25: list[OURecord] = []


class PredictionItem(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    match_date: str
    division: str
    prob_home: float
    prob_draw: float
    prob_away: float
    pred_label: str
    confidence: float
