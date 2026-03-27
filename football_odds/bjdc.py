"""
500 彩票网北京单场解析。
页面地址：https://trade.500.com/bjdc/
北单包含竞彩所有比赛，但让球和赔率(SP)不同于竞彩。

每行字段：
  td[0]: 场次编号
  td[1]: 联赛
  td[2]: 开赛时间
  td[3]: 主队（可能带排名如 [3]）
  td[4]: 让球（+1/-1/0）
  td[5]: 客队
  td[6]: 北单 SP（胜/平/负 三个 span）+ 亚盘描述文字
  td[7]: 比分 或 "析亚欧" 链接（含 500.com 分析页链接）
  td[8-10]: 竞彩 SP（胜/平/负，如果开售）
  td[11]: 操作
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup

BJDC_URL = "https://trade.500.com/bjdc/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass
class BjdcRow:
    """北单单场比赛数据。"""
    match_num: str
    league: str
    kickoff: str
    home_team: str
    away_team: str
    handicap: str
    # 北单 SP（让球胜平负）
    bd_sp_win: float | None
    bd_sp_draw: float | None
    bd_sp_lose: float | None
    # 竞彩 SP（不让球胜平负，可能为空）
    jc_sp_win: float | None
    jc_sp_draw: float | None
    jc_sp_lose: float | None
    # 比分（已完场）
    score_text: str | None
    # 500.com 分析页 ID
    match_id_500: str | None
    # 亚盘描述文字
    asian_desc: str | None
    # 日期
    match_date: str | None


def _safe_float(s: str | None) -> float | None:
    if not s or s.strip() in ("", "--", "—"):
        return None
    try:
        return float(s.strip())
    except ValueError:
        return None


def _extract_team_name(td) -> str:
    """提取球队名，去掉排名标注如 [3]。"""
    # 找 a 标签里的文字
    a = td.select_one("a")
    if a:
        text = a.get_text(strip=True)
    else:
        text = td.get_text(strip=True)
    # 去掉 [数字] 或 [世数字] 排名
    text = re.sub(r'\[.*?\]', '', text).strip()
    return text


def _extract_match_id(td) -> str | None:
    """从分析链接提取 500.com 的比赛 ID。"""
    for a in td.select("a"):
        href = a.get("href", "")
        m = re.search(r'shuju-(\d+)', href)
        if m:
            return m.group(1)
    return None


def parse_bjdc_html(html: str) -> list[BjdcRow]:
    """解析北单页面 HTML。"""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table.dc_table")
    if len(tables) < 2:
        return []

    table = tables[1]
    rows: list[BjdcRow] = []
    current_date = ""

    for tr in table.select("tr"):
        tds = tr.select("td")

        # 日期行（只有1个 td）
        if len(tds) == 1:
            date_text = tds[0].get_text(strip=True)
            m = re.match(r'(\d{4}-\d{2}-\d{2})', date_text)
            if m:
                current_date = m.group(1)
            continue

        if len(tds) < 8:
            continue

        match_num = tds[0].get_text(strip=True)
        league = tds[1].get_text(strip=True)
        kickoff = tds[2].get_text(strip=True)
        home_team = _extract_team_name(tds[3])
        handicap = tds[4].get_text(strip=True)
        away_team = _extract_team_name(tds[5])

        # 北单 SP（td[6] 内的 span）
        sp_spans = tds[6].select("span")
        bd_sps = [_safe_float(s.get_text(strip=True)) for s in sp_spans[:3]]
        while len(bd_sps) < 3:
            bd_sps.append(None)

        # 亚盘描述
        td6_text = tds[6].get_text(strip=True)
        asian_desc = None
        for pattern in ["受", "平手", "半球", "一球", "球半", "两球"]:
            if pattern in td6_text:
                # 取最后出现的亚盘描述
                parts = re.split(r'[\d.]+', td6_text)
                for p in reversed(parts):
                    p = p.strip().strip("-")
                    if p and any(k in p for k in ["受", "平手", "半球", "一球", "球半", "两球"]):
                        asian_desc = p
                        break
                break

        # 比分 或 分析链接
        td7_text = tds[7].get_text(strip=True)
        score_text = None
        if re.match(r'^\d+:\d+$', td7_text):
            score_text = td7_text
        match_id_500 = _extract_match_id(tds[7])

        # 竞彩 SP（td[8-10]，可能为空）
        jc_win = _safe_float(tds[8].get_text(strip=True)) if len(tds) > 8 else None
        jc_draw = _safe_float(tds[9].get_text(strip=True)) if len(tds) > 9 else None
        jc_lose = _safe_float(tds[10].get_text(strip=True)) if len(tds) > 10 else None

        rows.append(BjdcRow(
            match_num=match_num,
            league=league,
            kickoff=kickoff,
            home_team=home_team,
            away_team=away_team,
            handicap=handicap,
            bd_sp_win=bd_sps[0],
            bd_sp_draw=bd_sps[1],
            bd_sp_lose=bd_sps[2],
            jc_sp_win=jc_win,
            jc_sp_draw=jc_draw,
            jc_sp_lose=jc_lose,
            score_text=score_text,
            match_id_500=match_id_500,
            asian_desc=asian_desc,
            match_date=current_date,
        ))

    return rows


def fetch_bjdc(timeout: float = 20.0) -> list[BjdcRow]:
    """拉取当日北单数据。"""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,*/*"}
    r = requests.get(BJDC_URL, headers=headers, timeout=timeout)
    r.raise_for_status()
    text = r.content.decode("gb2312", errors="replace")
    return parse_bjdc_html(text)
