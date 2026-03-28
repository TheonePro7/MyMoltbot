"""
500 竞彩列表解析：结构化行 + 可选投注项（供模拟投注表单）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator

from bs4 import BeautifulSoup

from football_odds.models import BookmakerLine, MatchOdds


@dataclass(frozen=True)
class JcRow:
    """单场一行（含胜平负与让球两行 SP）。"""

    fixture_id: str
    matchnum: str
    home_team: str
    away_team: str
    league: str
    kickoff: str
    handicap: str
    ended: bool
    score_text: str | None
    nspf: tuple[tuple[str, float], ...] | None  # (data-value, sp)
    spf: tuple[tuple[str, float], ...] | None


def _parse_sp_tuples(container: Any, data_type: str) -> tuple[tuple[str, float], ...] | None:
    items: list[tuple[str, float]] = []
    for p in container.select(f'p.betbtn[data-type="{data_type}"]'):
        sp = p.get("data-sp")
        val = p.get("data-value")
        if not sp or val is None:
            continue
        try:
            items.append((str(val), float(sp)))
        except ValueError:
            continue
    if len(items) != 3:
        return None
    return tuple(sorted(items, key=lambda x: x[0]))


def _score_from_row(tr: Any) -> str | None:
    a = tr.select_one("a.score")
    if a and a.string:
        t = a.string.strip()
        if re.match(r"^\d+:\d+$", t):
            return t
    return None


def parse_jc_rows(html: str) -> list[JcRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[JcRow] = []
    for tr in soup.select("tr.bet-tb-tr"):
        fid = (tr.get("data-fixtureid") or "").strip()
        matchnum = (tr.get("data-matchnum") or "").strip()
        home = (tr.get("data-homesxname") or "").strip()
        away = (tr.get("data-awaysxname") or "").strip()
        league = (tr.get("data-simpleleague") or "").strip()
        mdate = (tr.get("data-matchdate") or "").strip()
        mtime = (tr.get("data-matchtime") or "").strip()
        rang = (tr.get("data-rangqiu") or "").strip()
        ended = (tr.get("data-isend") or "0") == "1"
        kickoff = f"{mdate} {mtime}".strip()
        score = _score_from_row(tr)
        row_nspf = tr.select_one("div.betbtn-row.itm-rangB1")
        row_spf = tr.select_one("div.betbtn-row.itm-rangB2")
        nspf = _parse_sp_tuples(row_nspf, "nspf") if row_nspf else None
        spf = _parse_sp_tuples(row_spf, "spf") if row_spf else None
        rows.append(
            JcRow(
                fixture_id=fid,
                matchnum=matchnum,
                home_team=home,
                away_team=away,
                league=league,
                kickoff=kickoff,
                handicap=rang,
                ended=ended,
                score_text=score,
                nspf=nspf,
                spf=spf,
            )
        )
    return rows


def jc_rows_to_match_odds_pairs(rows: list[JcRow]) -> list[tuple[MatchOdds, JcRow]]:
    """兼容原有多庄分析：每场生成 MatchOdds + 元数据（用最后一行 JcRow）。"""
    out: list[tuple[MatchOdds, JcRow]] = []
    for jr in rows:
        if jr.nspf:
            h = next(sp for v, sp in jr.nspf if v == "3")
            d = next(sp for v, sp in jr.nspf if v == "1")
            a = next(sp for v, sp in jr.nspf if v == "0")
            mid = f"{jr.matchnum}-胜平负" if jr.matchnum else f"{jr.fixture_id}-nspf"
            m = MatchOdds(
                match_id=mid,
                home_team=jr.home_team,
                away_team=jr.away_team,
                lines=(BookmakerLine("体彩竞彩·胜平负(官方SP)", h, d, a),),
            )
            out.append((m, jr))
        if jr.spf:
            h = next(sp for v, sp in jr.spf if v == "3")
            d = next(sp for v, sp in jr.spf if v == "1")
            a = next(sp for v, sp in jr.spf if v == "0")
            label = f"让球{jr.handicap}" if jr.handicap else "让球"
            mid = f"{jr.matchnum}-{label}" if jr.matchnum else f"{jr.fixture_id}-spf"
            m = MatchOdds(
                match_id=mid,
                home_team=jr.home_team,
                away_team=jr.away_team,
                lines=(BookmakerLine(f"体彩竞彩·让球胜平负({label})·官方SP", h, d, a),),
            )
            out.append((m, jr))
    return out


def iter_selections(row: JcRow) -> Iterator[dict[str, Any]]:
    """展开为可勾选投注项（字典供模板/JSON）。"""
    labels = {"3": "主胜", "1": "平", "0": "客胜"}
    if row.nspf:
        for val, sp in row.nspf:
            sid = f"{row.fixture_id}-nspf-{val}"
            yield {
                "selection_id": sid,
                "fixture_id": row.fixture_id,
                "matchnum": row.matchnum,
                "home_team": row.home_team,
                "away_team": row.away_team,
                "league": row.league,
                "kickoff": row.kickoff,
                "market": "nspf",
                "market_label": "胜平负",
                "handicap": "",
                "outcome": val,
                "outcome_label": labels[val],
                "odds": sp,
                "ended": row.ended,
                "score_text": row.score_text,
            }
    if row.spf:
        hl = f"让球{row.handicap}" if row.handicap else "让球"
        for val, sp in row.spf:
            sid = f"{row.fixture_id}-spf-{val}"
            yield {
                "selection_id": sid,
                "fixture_id": row.fixture_id,
                "matchnum": row.matchnum,
                "home_team": row.home_team,
                "away_team": row.away_team,
                "league": row.league,
                "kickoff": row.kickoff,
                "market": "spf",
                "market_label": hl,
                "handicap": row.handicap,
                "outcome": val,
                "outcome_label": labels[val],
                "odds": sp,
                "ended": row.ended,
                "score_text": row.score_text,
            }
