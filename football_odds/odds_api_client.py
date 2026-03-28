"""
The Odds API v4 客户端：拉取足球等赛事的 h2h（胜平负）十进制赔率，转为 MatchOdds 多庄结构。
文档：https://the-odds-api.com/liveapi/guides/v4/
需环境变量 ODDS_API_KEY。
"""

from __future__ import annotations

import os
from typing import Any

import requests

from football_odds.models import BookmakerLine, MatchOdds

API_HOST = "https://api.the-odds-api.com/v4/sports"


def _outcome_triple(
    home_team: str, away_team: str, outcomes: list[dict[str, Any]]
) -> tuple[float, float, float] | None:
    """从 h2h outcomes 提取主/平/客十进制赔率。"""
    by_name: dict[str, float] = {}
    for o in outcomes:
        name = str(o.get("name", "")).strip()
        price = o.get("price")
        if name and price is not None:
            try:
                by_name[name] = float(price)
            except (TypeError, ValueError):
                continue
    home = by_name.get(home_team)
    away = by_name.get(away_team)
    draw = by_name.get("Draw")
    if draw is None:
        for k, v in by_name.items():
            if k.lower() == "draw":
                draw = v
                break
    if home is None or draw is None or away is None:
        return None
    return home, draw, away


def fetch_odds_api_matches(
    sport_key: str | None = None,
    regions: str | None = None,
    timeout: float = 25.0,
) -> list[MatchOdds]:
    """
    请求 The Odds API，返回每场赛事一个 MatchOdds（含多家 bookmaker 的 h2h）。
    """
    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    if not api_key:
        raise ValueError("未设置环境变量 ODDS_API_KEY，无法请求 The Odds API")

    sk = (sport_key or os.environ.get("ODDS_SPORT_KEY", "soccer_epl")).strip()
    reg = (regions or os.environ.get("ODDS_REGIONS", "eu")).strip()

    url = f"{API_HOST}/{sk}/odds"
    params = {
        "apiKey": api_key,
        "regions": reg,
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    headers = {"User-Agent": "MyMoltbot/1.0 (+https://github.com)"}
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    events: list[Any] = r.json()
    if not isinstance(events, list):
        raise ValueError("The Odds API 返回格式异常")

    matches: list[MatchOdds] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        home_team = str(ev.get("home_team", "")).strip()
        away_team = str(ev.get("away_team", "")).strip()
        eid = str(ev.get("id", "")).strip() or "unknown"
        if not home_team or not away_team:
            continue
        lines: list[BookmakerLine] = []
        for bm in ev.get("bookmakers") or []:
            if not isinstance(bm, dict):
                continue
            title = str(bm.get("title") or bm.get("key") or "bookmaker").strip()
            for mk in bm.get("markets") or []:
                if not isinstance(mk, dict) or mk.get("key") != "h2h":
                    continue
                outs = mk.get("outcomes") or []
                if not isinstance(outs, list):
                    continue
                trip = _outcome_triple(home_team, away_team, outs)
                if trip is None:
                    continue
                h, d, a = trip
                try:
                    lines.append(BookmakerLine(title, h, d, a))
                except ValueError:
                    continue
                break
        if len(lines) >= 1:
            matches.append(
                MatchOdds(
                    match_id=eid,
                    home_team=home_team,
                    away_team=away_team,
                    lines=tuple(lines),
                )
            )
    return matches
