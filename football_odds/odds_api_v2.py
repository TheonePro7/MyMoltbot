"""
The Odds API v4 增强版客户端：拉取 54+ 庄家的欧赔、亚盘（spreads）、大小球（totals）。
支持多联赛、多区域、多市场一次性拉取，并直接写入历史数据库。

与原 odds_api_client.py 的区别：
- 原版只拉 h2h 单市场，转为 MatchOdds 供页面展示
- 本版拉取全市场（h2h + spreads + totals），存入 history.sqlite3 供分析
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

from football_odds.history_db import (
    connect_history,
    insert_match,
    insert_odds_1x2,
    insert_odds_asian,
    insert_odds_ou25,
)

API_HOST = "https://api.the-odds-api.com/v4"
USER_AGENT = "MyMoltbot/2.0"

LEAGUE_MAP: dict[str, tuple[str, str]] = {
    "soccer_epl": ("E0", "England"),
    "soccer_efl_champ": ("E1", "England"),
    "soccer_england_league1": ("E2", "England"),
    "soccer_england_league2": ("E3", "England"),
    "soccer_spain_la_liga": ("SP1", "Spain"),
    "soccer_spain_segunda_division": ("SP2", "Spain"),
    "soccer_germany_bundesliga": ("D1", "Germany"),
    "soccer_germany_bundesliga2": ("D2", "Germany"),
    "soccer_italy_serie_a": ("I1", "Italy"),
    "soccer_france_ligue_one": ("F1", "France"),
    "soccer_france_ligue_two": ("F2", "France"),
    "soccer_netherlands_eredivisie": ("N1", "Netherlands"),
    "soccer_belgium_first_div": ("B1", "Belgium"),
    "soccer_portugal_primeira_liga": ("P1", "Portugal"),
    "soccer_greece_super_league": ("G1", "Greece"),
    "soccer_spl": ("SC0", "Scotland"),
    "soccer_uefa_champs_league": ("UCL", "Europe"),
    "soccer_uefa_europa_league": ("UEL", "Europe"),
    "soccer_usa_mls": ("MLS", "USA"),
    "soccer_japan_j_league": ("J1", "Japan"),
    "soccer_korea_kleague1": ("K1", "Korea"),
    "soccer_china_superleague": ("CSL", "China"),
    "soccer_australia_aleague": ("A1", "Australia"),
    "soccer_brazil_campeonato": ("BR1", "Brazil"),
    "soccer_argentina_primera_division": ("AR1", "Argentina"),
    "soccer_mexico_ligamx": ("MX1", "Mexico"),
    "soccer_denmark_superliga": ("DK1", "Denmark"),
    "soccer_sweden_allsvenskan": ("SE1", "Sweden"),
    "soccer_norway_eliteserien": ("NO1", "Norway"),
    "soccer_switzerland_superleague": ("CH1", "Switzerland"),
    "soccer_austria_bundesliga": ("AT1", "Austria"),
}

TOP_LEAGUES = [
    "soccer_epl",
    "soccer_efl_champ",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
]

ALL_REGIONS = "us,uk,eu,au"


def _get_api_key() -> str:
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        raise ValueError("未设置环境变量 ODDS_API_KEY")
    return key


def _current_season() -> str:
    """根据当前月份推算赛季代码，如 '2526'。"""
    now = datetime.now(timezone.utc)
    y = now.year % 100
    if now.month >= 7:
        return f"{y:02d}{(y + 1):02d}"
    else:
        return f"{(y - 1):02d}{y:02d}"


def fetch_league_odds(
    sport_key: str,
    markets: str = "h2h,spreads,totals",
    regions: str = ALL_REGIONS,
    timeout: float = 30.0,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    拉取指定联赛的当前赔率（所有即将开赛的比赛）。
    返回 (events, quota_info)。
    quota_info = {"used": N, "remaining": N}
    """
    api_key = _get_api_key()
    url = f"{API_HOST}/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
    }
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()

    quota = {
        "used": int(r.headers.get("x-requests-used", 0)),
        "remaining": int(r.headers.get("x-requests-remaining", 0)),
    }

    events = r.json()
    if not isinstance(events, list):
        return [], quota
    return events, quota


def _extract_h2h(bookmaker_data: dict, home_team: str, away_team: str) -> tuple[float | None, float | None, float | None]:
    """从庄家数据提取 h2h（1X2）赔率。"""
    for mk in bookmaker_data.get("markets", []):
        if mk.get("key") != "h2h":
            continue
        by_name: dict[str, float] = {}
        for o in mk.get("outcomes", []):
            by_name[o["name"]] = o["price"]
        home = by_name.get(home_team)
        draw = by_name.get("Draw")
        away = by_name.get(away_team)
        return home, draw, away
    return None, None, None


def _extract_spreads(bookmaker_data: dict, home_team: str) -> tuple[float | None, float | None, float | None]:
    """从庄家数据提取 spreads（亚盘/让球）。返回 (handicap, home_odds, away_odds)。"""
    for mk in bookmaker_data.get("markets", []):
        if mk.get("key") != "spreads":
            continue
        outcomes = mk.get("outcomes", [])
        home_od = None
        away_od = None
        handicap = None
        for o in outcomes:
            if o.get("name") == home_team:
                home_od = o.get("price")
                handicap = o.get("point")
            else:
                away_od = o.get("price")
        return handicap, home_od, away_od
    return None, None, None


def _extract_totals(bookmaker_data: dict) -> tuple[float | None, float | None, float | None]:
    """从庄家数据提取 totals（大小球）。返回 (line, over_odds, under_odds)。"""
    for mk in bookmaker_data.get("markets", []):
        if mk.get("key") != "totals":
            continue
        over_od = None
        under_od = None
        line = None
        for o in mk.get("outcomes", []):
            if o.get("name") == "Over":
                over_od = o.get("price")
                line = o.get("point")
            elif o.get("name") == "Under":
                under_od = o.get("price")
        return line, over_od, under_od
    return None, None, None


def store_events_to_db(events: list[dict[str, Any]], sport_key: str) -> int:
    """
    将 The Odds API 返回的 events 写入历史数据库。
    返回成功写入的比赛数。
    """
    div_code, _ = LEAGUE_MAP.get(sport_key, (sport_key, "Unknown"))
    season = _current_season()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = 0

    with connect_history() as conn:
        for ev in events:
            home_team = ev.get("home_team", "").strip()
            away_team = ev.get("away_team", "").strip()
            if not home_team or not away_team:
                continue

            start_time = ev.get("commence_time", "")
            match_date = start_time[:10] if start_time else now_iso
            match_time = start_time[11:16] if len(start_time) > 15 else None

            match_data = {
                "division": div_code,
                "season": season,
                "match_date": match_date,
                "match_time": match_time,
                "home_team": home_team,
                "away_team": away_team,
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

            match_id = insert_match(conn, match_data)
            if match_id <= 0:
                continue

            bookmakers = ev.get("bookmakers", [])
            for bm in bookmakers:
                bm_name = (bm.get("title") or bm.get("key") or "unknown").strip()

                h, d, a = _extract_h2h(bm, home_team, away_team)
                if h is not None:
                    insert_odds_1x2(conn, match_id, bm_name, 0, h, d, a)

                handicap, sp_h, sp_a = _extract_spreads(bm, home_team)
                if sp_h is not None:
                    insert_odds_asian(conn, match_id, bm_name, 0, handicap, sp_h, sp_a)

                line, ov, un = _extract_totals(bm)
                if ov is not None:
                    insert_odds_ou25(conn, match_id, bm_name, 0, ov, un)

            count += 1

        conn.commit()

    return count


def snapshot_all_leagues(
    leagues: list[str] | None = None,
    markets: str = "h2h,spreads,totals",
    progress_fn=None,
) -> dict[str, Any]:
    """
    对多个联赛执行一次赔率快照，存入数据库。
    返回统计摘要。
    """
    target = leagues or TOP_LEAGUES
    total_matches = 0
    total_bookmakers = 0
    results: list[dict] = []
    quota_info = {"used": 0, "remaining": 0}

    for sport_key in target:
        div_code, country = LEAGUE_MAP.get(sport_key, (sport_key, "?"))
        if progress_fn:
            progress_fn(f"拉取 {sport_key} ({div_code}) ...")

        try:
            events, qi = fetch_league_odds(sport_key, markets=markets)
            quota_info = qi
        except Exception as e:
            if progress_fn:
                progress_fn(f"  错误: {e}")
            results.append({"league": sport_key, "div": div_code, "error": str(e)})
            continue

        if not events:
            if progress_fn:
                progress_fn(f"  无比赛数据")
            results.append({"league": sport_key, "div": div_code, "matches": 0, "bookmakers": 0})
            continue

        bm_count = sum(len(ev.get("bookmakers", [])) for ev in events)
        n = store_events_to_db(events, sport_key)
        total_matches += n
        total_bookmakers += bm_count

        if progress_fn:
            progress_fn(f"  {n} 场比赛，{bm_count} 条庄家赔率")

        results.append({
            "league": sport_key,
            "div": div_code,
            "matches": n,
            "bookmakers": bm_count,
        })

        time.sleep(0.5)

    return {
        "total_matches": total_matches,
        "total_bookmaker_records": total_bookmakers,
        "quota": quota_info,
        "details": results,
    }


def main() -> None:
    """命令行入口：执行一次全联赛赔率快照。"""
    import argparse

    parser = argparse.ArgumentParser(description="The Odds API 多庄家赔率快照")
    parser.add_argument("--leagues", nargs="*", default=None,
                        help="联赛 key 列表（默认为六大联赛）")
    parser.add_argument("--all-leagues", action="store_true",
                        help="拉取所有支持的联赛")
    parser.add_argument("--markets", default="h2h,spreads,totals",
                        help="市场类型（默认 h2h,spreads,totals）")
    parser.add_argument("--list-leagues", action="store_true",
                        help="列出所有支持的联赛")
    args = parser.parse_args()

    if args.list_leagues:
        print(f"{'Key':>40}  {'代码':>4}  {'国家/地区'}")
        for k, (code, country) in sorted(LEAGUE_MAP.items()):
            print(f"{k:>40}  {code:>4}  {country}")
        return

    leagues = list(LEAGUE_MAP.keys()) if args.all_leagues else args.leagues

    def log(msg: str) -> None:
        print(msg, flush=True)

    log("开始赔率快照...")
    result = snapshot_all_leagues(leagues=leagues, markets=args.markets, progress_fn=log)
    log("")
    log(f"完成！{result['total_matches']} 场比赛，{result['total_bookmaker_records']} 条庄家记录")
    log(f"API 额度：已用 {result['quota']['used']}，剩余 {result['quota']['remaining']}")


if __name__ == "__main__":
    main()
