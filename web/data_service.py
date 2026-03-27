"""
Web 层数据装配：竞彩 500、The Odds API、本地 JSON。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from football_odds.analysis import compare_bookmakers, load_matches_from_json
from football_odds.jc500 import Jc500MatchMeta, fetch_jc_matches
from football_odds.odds_api_client import fetch_odds_api_matches


def cst_today_str() -> str:
    """中国时区当日日期 YYYY-MM-DD（用于竞彩 date 参数与表单默认）。"""
    cst = timezone(timedelta(hours=8))
    return datetime.now(cst).strftime("%Y-%m-%d")


def load_rows_for_web(
    source: str,
    *,
    jc_date: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    """
    返回 (rows, error, info)。
    每个 row: match, compare, meta(Optional[Jc500MatchMeta as dict]), subtitle(Optional[str]).
    """
    source = (source or "jc500").strip().lower()
    info: dict[str, Any] = {"source": source}

    if source in ("file", "sample", "json"):
        root = Path(__file__).resolve().parent.parent
        default = root / "examples" / "matches_sample.json"
        path = Path(os.environ.get("FOOTBALL_ODDS_DATA", str(default)))
        if not path.is_file():
            return [], f"数据文件不存在: {path}", info
        matches = load_matches_from_json(path)
        info["path"] = str(path)
        rows = [{"match": m, "compare": compare_bookmakers(m), "meta": None, "subtitle": None} for m in matches]
        return rows, None, info

    if source in ("jc500", "jc", "jingcai", "500"):
        d = (jc_date or cst_today_str()).strip()
        info["jc_date"] = d
        try:
            pairs = fetch_jc_matches(d)
        except Exception as e:
            return [], f"拉取 500 网竞彩失败: {e}", info
        rows = []
        for m, meta in pairs:
            rows.append(
                {
                    "match": m,
                    "compare": compare_bookmakers(m),
                    "meta": {
                        "league": meta.league,
                        "kickoff": meta.kickoff,
                        "handicap": meta.handicap,
                        "ended": meta.ended,
                        "score_text": meta.score_text,
                        "fixture_id": meta.fixture_id,
                    },
                    "subtitle": "体彩官方开售 SP（页面快照）",
                }
            )
        return rows, None, info

    if source in ("odds_api", "api", "theodds"):
        try:
            max_n = int(os.environ.get("ODDS_MAX_MATCHES", "30"))
        except ValueError:
            max_n = 30
        try:
            matches = fetch_odds_api_matches()
        except Exception as e:
            return [], f"The Odds API 请求失败: {e}", info
        matches = matches[:max_n]
        info["max_matches"] = max_n
        info["sport_key"] = os.environ.get("ODDS_SPORT_KEY", "soccer_epl")
        rows = [
            {
                "match": m,
                "compare": compare_bookmakers(m),
                "meta": None,
                "subtitle": "The Odds API · 境外庄家 h2h（十进制）",
            }
            for m in matches
        ]
        return rows, None, info

    return [], f"未知数据源: {source}（可选: jc500, odds_api, file）", info
