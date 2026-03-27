"""历史数据 API：比赛列表、详情、统计。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.schemas import (
    DashboardStats,
    LeagueStat,
    MatchDetail,
    MatchItem,
    MatchListResponse,
    OddsRecord,
    AsianOddsRecord,
    OURecord,
)
from football_odds.history_db import (
    connect_history,
    count_matches,
    get_match_with_odds,
    query_matches,
    summary_stats,
)

router = APIRouter(prefix="/api/history", tags=["历史数据"])


@router.get("/stats", response_model=DashboardStats)
def get_stats():
    """获取数据库统计概览。"""
    with connect_history() as conn:
        s = summary_stats(conn)
    return DashboardStats(
        total_matches=s["total_matches"],
        total_odds_records=s["total_odds_records"],
        total_asian_records=s["total_asian_records"],
        by_division=[LeagueStat(**d) for d in s["by_division"]],
    )


@router.get("/matches", response_model=MatchListResponse)
def list_matches(
    division: str | None = Query(None, description="联赛代码，如 E0"),
    season: str | None = Query(None, description="赛季代码，如 2526"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """分页查询历史比赛。"""
    with connect_history() as conn:
        total = count_matches(conn, division, season)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size
        raw = query_matches(conn, division, season, limit=page_size, offset=offset)

        items: list[MatchItem] = []
        for m in raw:
            row = conn.execute(
                "SELECT home_odds, draw_odds, away_odds FROM odds_1x2 "
                "WHERE match_id=? AND bookmaker='B365' AND is_closing=0",
                (m["id"],),
            ).fetchone()
            row2 = conn.execute(
                "SELECT home_odds, draw_odds, away_odds FROM odds_1x2 "
                "WHERE match_id=? AND bookmaker='PS' AND is_closing=0",
                (m["id"],),
            ).fetchone()
            ah = conn.execute(
                "SELECT handicap FROM odds_asian "
                "WHERE match_id=? AND bookmaker='B365' AND is_closing=0",
                (m["id"],),
            ).fetchone()

            items.append(MatchItem(
                match_id=m["id"],
                division=m["division"],
                season=m["season"],
                match_date=m["match_date"],
                home_team=m["home_team"],
                away_team=m["away_team"],
                fthg=m.get("fthg"),
                ftag=m.get("ftag"),
                ftr=m.get("ftr"),
                b365_h=row["home_odds"] if row else None,
                b365_d=row["draw_odds"] if row else None,
                b365_a=row["away_odds"] if row else None,
                ps_h=row2["home_odds"] if row2 else None,
                ps_d=row2["draw_odds"] if row2 else None,
                ps_a=row2["away_odds"] if row2 else None,
                ah_handicap=ah["handicap"] if ah else None,
            ))

    return MatchListResponse(matches=items, total=total, page=page, total_pages=total_pages)


@router.get("/matches/{match_id}", response_model=MatchDetail)
def get_match(match_id: int):
    """获取单场比赛完整数据（含全部庄家赔率）。"""
    with connect_history() as conn:
        m = get_match_with_odds(conn, match_id)
    if not m:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="比赛不存在")

    odds_1x2 = []
    for o in m.get("odds_1x2", []):
        overround = None
        if o.get("home_odds") and o.get("draw_odds") and o.get("away_odds"):
            overround = round((1/o["home_odds"] + 1/o["draw_odds"] + 1/o["away_odds"] - 1) * 100, 2)
        odds_1x2.append(OddsRecord(
            bookmaker=o["bookmaker"], is_closing=o["is_closing"],
            home_odds=o.get("home_odds"), draw_odds=o.get("draw_odds"),
            away_odds=o.get("away_odds"), overround=overround,
        ))

    return MatchDetail(
        match_id=m["id"], division=m["division"], season=m["season"],
        match_date=m["match_date"], match_time=m.get("match_time"),
        home_team=m["home_team"], away_team=m["away_team"],
        fthg=m.get("fthg"), ftag=m.get("ftag"), ftr=m.get("ftr"),
        hthg=m.get("hthg"), htag=m.get("htag"), referee=m.get("referee"),
        home_shots=m.get("home_shots"), away_shots=m.get("away_shots"),
        home_sot=m.get("home_sot"), away_sot=m.get("away_sot"),
        home_corners=m.get("home_corners"), away_corners=m.get("away_corners"),
        home_fouls=m.get("home_fouls"), away_fouls=m.get("away_fouls"),
        home_yellows=m.get("home_yellows"), away_yellows=m.get("away_yellows"),
        home_reds=m.get("home_reds"), away_reds=m.get("away_reds"),
        odds_1x2=odds_1x2,
        odds_asian=[AsianOddsRecord(**o) for o in m.get("odds_asian", [])],
        odds_ou25=[OURecord(**o) for o in m.get("odds_ou25", [])],
    )
