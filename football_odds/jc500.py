"""
500 彩票网竞彩足球列表页解析（胜平负 / 让球胜平负 SP）。
页面编码多为 GB2312，赛事行在 tr.bet-tb-tr，奖金在 p.betbtn 的 data-sp。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from football_odds.models import BookmakerLine, MatchOdds

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


def _parse_sp_row(container, data_type: str) -> tuple[float, float, float] | None:
    """从一行 betbtn 解析主/平/客 SP。竞彩 data-value：3 主胜 1 平 0 客胜。"""
    home = draw = away = None
    for p in container.select(f'p.betbtn[data-type="{data_type}"]'):
        sp = p.get("data-sp")
        if not sp:
            continue
        try:
            price = float(sp)
        except ValueError:
            continue
        val = p.get("data-value")
        if val == "3":
            home = price
        elif val == "1":
            draw = price
        elif val == "0":
            away = price
    if home is None or draw is None or away is None:
        return None
    return home, draw, away


def _score_from_row(tr: Any) -> str | None:
    """已开赛/完场时尝试读取比分链接文本。"""
    a = tr.select_one("a.score")
    if a and a.string:
        t = a.string.strip()
        if re.match(r"^\d+:\d+$", t):
            return t
    return None


def parse_jc_html(html: str) -> list[tuple[MatchOdds, Jc500MatchMeta]]:
    """
    解析竞彩列表页 HTML，返回 (MatchOdds, 展示元数据)。
    每场可能生成两条 MatchOdds：不让球（胜平负）与让球胜平负（若均有 SP）。
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[MatchOdds, Jc500MatchMeta]] = []

    for tr in soup.select("tr.bet-tb-tr"):
        matchnum = (tr.get("data-matchnum") or "").strip()
        home = (tr.get("data-homesxname") or "").strip()
        away = (tr.get("data-awaysxname") or "").strip()
        league = (tr.get("data-simpleleague") or "").strip()
        mdate = (tr.get("data-matchdate") or "").strip()
        mtime = (tr.get("data-matchtime") or "").strip()
        rang = (tr.get("data-rangqiu") or "").strip()
        ended = (tr.get("data-isend") or "0") == "1"
        fid = (tr.get("data-fixtureid") or "").strip()
        kickoff = f"{mdate} {mtime}".strip()
        score = _score_from_row(tr)

        meta_base = Jc500MatchMeta(
            league=league,
            kickoff=kickoff,
            handicap=rang,
            ended=ended,
            score_text=score,
            fixture_id=fid,
        )

        row_nspf = tr.select_one("div.betbtn-row.itm-rangB1")
        row_spf = tr.select_one("div.betbtn-row.itm-rangB2")

        if row_nspf:
            triple = _parse_sp_row(row_nspf, "nspf")
            if triple:
                h, d, a = triple
                mid = f"{matchnum}-胜平负" if matchnum else f"{fid}-nspf"
                m = MatchOdds(
                    match_id=mid,
                    home_team=home,
                    away_team=away,
                    lines=(BookmakerLine("体彩竞彩·胜平负(官方SP)", h, d, a),),
                )
                out.append((m, meta_base))

        if row_spf:
            triple = _parse_sp_row(row_spf, "spf")
            if triple:
                h, d, a = triple
                label = f"让球{rang}" if rang else "让球"
                mid = f"{matchnum}-{label}" if matchnum else f"{fid}-spf"
                m = MatchOdds(
                    match_id=mid,
                    home_team=home,
                    away_team=away,
                    lines=(BookmakerLine(f"体彩竞彩·让球胜平负({label})·官方SP", h, d, a),),
                )
                out.append((m, meta_base))

    return out


def fetch_jc_matches(date_yyyy_mm_dd: str, timeout: float = 20.0) -> list[tuple[MatchOdds, Jc500MatchMeta]]:
    """拉取指定日期的竞彩页面并解析。"""
    params = {**DEFAULT_PARAMS, "date": date_yyyy_mm_dd}
    url = f"{JC_BASE}?{urlencode(params)}"
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,*/*"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    # 500 页多为 gb2312
    text = r.content.decode("gb2312", errors="replace")
    return parse_jc_html(text)
