"""
500 彩票网竞彩足球列表页解析（胜平负 / 让球胜平负 SP）。
页面编码多为 GB2312，赛事行在 tr.bet-tb-tr，奖金在 p.betbtn 的 data-sp。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from football_odds.jc_rows import jc_rows_to_match_odds_pairs, parse_jc_rows
from football_odds.models import MatchOdds

# 列表页：让球胜平负（含两行：nspf 不让球 + spf 让球）
JC_BASE = "https://trade.500.com/jczq/"
DEFAULT_PARAMS = {"playid": "269", "g": "2"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Jc500MatchMeta:
    """单场展示用元数据（非核心分析字段）。"""

    league: str
    kickoff: str
    handicap: str
    ended: bool
    score_text: str | None
    fixture_id: str


def parse_jc_html(html: str) -> list[tuple[MatchOdds, Jc500MatchMeta]]:
    """解析竞彩列表页 HTML，返回 (MatchOdds, 展示元数据)。"""
    rows = parse_jc_rows(html)
    pairs = jc_rows_to_match_odds_pairs(rows)
    out: list[tuple[MatchOdds, Jc500MatchMeta]] = []
    for m, jr in pairs:
        meta = Jc500MatchMeta(
            league=jr.league,
            kickoff=jr.kickoff,
            handicap=jr.handicap,
            ended=jr.ended,
            score_text=jr.score_text,
            fixture_id=jr.fixture_id,
        )
        out.append((m, meta))
    return out


def fetch_jc_matches(date_yyyy_mm_dd: str, timeout: float = 20.0) -> list[tuple[MatchOdds, Jc500MatchMeta]]:
    """拉取指定日期的竞彩页面并解析。"""
    params = {**DEFAULT_PARAMS, "date": date_yyyy_mm_dd}
    url = f"{JC_BASE}?{urlencode(params)}"
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,*/*"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    text = r.content.decode("gb2312", errors="replace")
    return parse_jc_html(text)


def fetch_jc_rows(date_yyyy_mm_dd: str, timeout: float = 20.0) -> list[Any]:
    """拉取并返回结构化 JcRow 列表（供模拟投注选场）。"""
    params = {**DEFAULT_PARAMS, "date": date_yyyy_mm_dd}
    url = f"{JC_BASE}?{urlencode(params)}"
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,*/*"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    text = r.content.decode("gb2312", errors="replace")
    return parse_jc_rows(text)
