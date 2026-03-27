"""
football-data.co.uk CSV 下载与解析。
支持 20 个赛季 × 多联赛的批量下载，并解析为结构化数据导入 SQLite。
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://www.football-data.co.uk/mmz4281"
USER_AGENT = "MyMoltbot/1.0 (+https://github.com/TheonePro7/MyMoltbot)"

MAIN_LEAGUES: dict[str, list[str]] = {
    "England": ["E0", "E1"],
    "Spain": ["SP1"],
    "Germany": ["D1"],
    "Italy": ["I1"],
    "France": ["F1"],
}

ALL_LEAGUES: dict[str, list[str]] = {
    "England": ["E0", "E1", "E2", "E3"],
    "Spain": ["SP1", "SP2"],
    "Germany": ["D1", "D2"],
    "Italy": ["I1", "I2"],
    "France": ["F1", "F2"],
    "Netherlands": ["N1"],
    "Belgium": ["B1"],
    "Portugal": ["P1"],
    "Turkey": ["T1"],
    "Greece": ["G1"],
    "Scotland": ["SC0", "SC1"],
}


def season_code_range(n_seasons: int = 20) -> list[str]:
    """
    生成赛季代码列表，从 2025/2026 (2526) 向前 n_seasons 个赛季。
    返回如 ['2526', '2425', '2324', ..., '0607']
    """
    codes = []
    end_year = 25
    for i in range(n_seasons):
        y1 = end_year - i
        y2 = y1 + 1
        code = f"{y1:02d}{y2:02d}"
        codes.append(code)
    return codes


def csv_url(season: str, division: str) -> str:
    return f"{BASE_URL}/{season}/{division}.csv"


def default_cache_dir() -> Path:
    root = Path(__file__).resolve().parent.parent
    d = root / "data" / "csv_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def download_csv(season: str, division: str, cache_dir: Path | None = None,
                  timeout: float = 30.0, force: bool = False) -> str | None:
    """
    下载 CSV 文件，缓存到本地。返回 CSV 文本内容；如果404则返回 None。
    """
    cdir = cache_dir or default_cache_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    cache_file = cdir / f"{division}_{season}.csv"

    if cache_file.exists() and not force:
        return cache_file.read_text(encoding="utf-8", errors="replace")

    url = csv_url(season, division)
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 404:
            return None
        r.raise_for_status()
    except requests.RequestException:
        return None

    text = r.content.decode("utf-8", errors="replace")
    if not text.strip():
        return None

    cache_file.write_text(text, encoding="utf-8")
    return text


def _safe_int(val: Any) -> int | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None


def _parse_date(date_str: str) -> str:
    """
    将 football-data.co.uk 的日期格式转为 YYYY-MM-DD。
    支持 dd/mm/yy 和 dd/mm/yyyy 两种格式。
    """
    date_str = date_str.strip()
    if not date_str:
        return ""
    parts = date_str.split("/")
    if len(parts) != 3:
        return date_str
    day, month, year = parts
    if len(year) == 2:
        y = int(year)
        year = str(2000 + y) if y < 50 else str(1900 + y)
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


_BOOKMAKER_1X2_COLUMNS: list[tuple[str, str, str, str]] = [
    ("B365", "B365H", "B365D", "B365A"),
    ("BW", "BWH", "BWD", "BWA"),
    ("IW", "IWH", "IWD", "IWA"),
    ("PS", "PSH", "PSD", "PSA"),
    ("WH", "WHH", "WHD", "WHA"),
    ("VC", "VCH", "VCD", "VCA"),
    ("LB", "LBH", "LBD", "LBA"),
    ("BF", "BFH", "BFD", "BFA"),
    ("BFD", "BFDH", "BFDD", "BFDA"),
    ("BMGM", "BMGMH", "BMGMD", "BMGMA"),
    ("BV", "BVH", "BVD", "BVA"),
    ("CL", "CLH", "CLD", "CLA"),
    ("SB", "SBH", "SBD", "SBA"),
    ("SJ", "SJH", "SJD", "SJA"),
    ("GB", "GBH", "GBD", "GBA"),
    ("BS", "BSH", "BSD", "BSA"),
    ("SO", "SOH", "SOD", "SOA"),
    ("SY", "SYH", "SYD", "SYA"),
    ("1XB", "1XBH", "1XBD", "1XBA"),
    ("Max", "MaxH", "MaxD", "MaxA"),
    ("Avg", "AvgH", "AvgD", "AvgA"),
    ("BbMax", "BbMxH", "BbMxD", "BbMxA"),
    ("BbAvg", "BbAvH", "BbAvD", "BbAvA"),
    ("BFE", "BFEH", "BFED", "BFEA"),
]

_BOOKMAKER_1X2_CLOSING: list[tuple[str, str, str, str]] = [
    ("B365", "B365CH", "B365CD", "B365CA"),
    ("BW", "BWCH", "BWCD", "BWCA"),
    ("PS", "PSCH", "PSCD", "PSCA"),
    ("WH", "WHCH", "WHCD", "WHCA"),
    ("LB", "LBCH", "LBCD", "LBCA"),
    ("BFD", "BFDCH", "BFDCD", "BFDCA"),
    ("BMGM", "BMGMCH", "BMGMCD", "BMGMCA"),
    ("BV", "BVCH", "BVCD", "BVCA"),
    ("CL", "CLCH", "CLCD", "CLCA"),
    ("Max", "MaxCH", "MaxCD", "MaxCA"),
    ("Avg", "AvgCH", "AvgCD", "AvgCA"),
    ("BFE", "BFECH", "BFECD", "BFECA"),
]

_OU25_COLUMNS: list[tuple[str, str, str]] = [
    ("B365", "B365>2.5", "B365<2.5"),
    ("PS", "P>2.5", "P<2.5"),
    ("GB", "GB>2.5", "GB<2.5"),
    ("Max", "Max>2.5", "Max<2.5"),
    ("Avg", "Avg>2.5", "Avg<2.5"),
    ("BbMax", "BbMx>2.5", "BbMx<2.5"),
    ("BbAvg", "BbAv>2.5", "BbAv<2.5"),
    ("BFE", "BFE>2.5", "BFE<2.5"),
]

_OU25_CLOSING: list[tuple[str, str, str]] = [
    ("B365", "B365C>2.5", "B365C<2.5"),
    ("PS", "PC>2.5", "PC<2.5"),
    ("Max", "MaxC>2.5", "MaxC<2.5"),
    ("Avg", "AvgC>2.5", "AvgC<2.5"),
    ("BFE", "BFEC>2.5", "BFEC<2.5"),
]

_ASIAN_COLUMNS: list[tuple[str, str, str, str | None]] = [
    ("B365", "B365AHH", "B365AHA", "B365AH"),
    ("PS", "PAHH", "PAHA", None),
    ("LB", "LBAHH", "LBAHA", "LBAH"),
    ("GB", "GBAHH", "GBAHA", "GBAH"),
    ("Max", "MaxAHH", "MaxAHA", None),
    ("Avg", "AvgAHH", "AvgAHA", None),
    ("BbMax", "BbMxAHH", "BbMxAHA", None),
    ("BbAvg", "BbAvAHH", "BbAvAHA", None),
    ("BFE", "BFEAHH", "BFEAHA", None),
]

_ASIAN_CLOSING: list[tuple[str, str, str, str | None]] = [
    ("B365", "B365CAHH", "B365CAHA", None),
    ("PS", "PCAHH", "PCAHA", None),
    ("Max", "MaxCAHH", "MaxCAHA", None),
    ("Avg", "AvgCAHH", "AvgCAHA", None),
    ("BFE", "BFECAHH", "BFECAHA", None),
]


def parse_csv_rows(csv_text: str, season: str) -> list[dict[str, Any]]:
    """
    解析 CSV 文本为结构化行列表。
    每行包含 match 基本信息 + odds_1x2 + odds_ou25 + odds_asian 子列表。
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return []

    fields = set(reader.fieldnames)
    results: list[dict[str, Any]] = []

    for row in reader:
        home = (row.get("HomeTeam") or "").strip()
        away = (row.get("AwayTeam") or "").strip()
        if not home or not away:
            continue

        date_raw = (row.get("Date") or "").strip()
        if not date_raw:
            continue

        match_date = _parse_date(date_raw)
        match_time = (row.get("Time") or "").strip() or None
        division = (row.get("Div") or "").strip()

        fthg = _safe_int(row.get("FTHG") or row.get("HG"))
        ftag = _safe_int(row.get("FTAG") or row.get("AG"))
        ftr = (row.get("FTR") or row.get("Res") or "").strip() or None

        match_data = {
            "division": division,
            "season": season,
            "match_date": match_date,
            "match_time": match_time,
            "home_team": home,
            "away_team": away,
            "fthg": fthg,
            "ftag": ftag,
            "ftr": ftr,
            "hthg": _safe_int(row.get("HTHG")),
            "htag": _safe_int(row.get("HTAG")),
            "htr": (row.get("HTR") or "").strip() or None,
            "referee": (row.get("Referee") or "").strip() or None,
            "home_shots": _safe_int(row.get("HS")),
            "away_shots": _safe_int(row.get("AS")),
            "home_sot": _safe_int(row.get("HST")),
            "away_sot": _safe_int(row.get("AST")),
            "home_corners": _safe_int(row.get("HC")),
            "away_corners": _safe_int(row.get("AC")),
            "home_fouls": _safe_int(row.get("HF")),
            "away_fouls": _safe_int(row.get("AF")),
            "home_yellows": _safe_int(row.get("HY")),
            "away_yellows": _safe_int(row.get("AY")),
            "home_reds": _safe_int(row.get("HR")),
            "away_reds": _safe_int(row.get("AR")),
        }

        # 通用亚盘盘口值
        handicap_general = _safe_float(row.get("AHh") or row.get("BbAHh"))
        handicap_closing = _safe_float(row.get("AHCh"))

        # 欧赔（初盘）
        odds_1x2: list[dict] = []
        for bm, hcol, dcol, acol in _BOOKMAKER_1X2_COLUMNS:
            if hcol in fields or dcol in fields or acol in fields:
                h = _safe_float(row.get(hcol))
                d = _safe_float(row.get(dcol))
                a = _safe_float(row.get(acol))
                if h is not None or d is not None or a is not None:
                    odds_1x2.append({"bookmaker": bm, "is_closing": 0, "home": h, "draw": d, "away": a})

        # 欧赔（终盘）
        for bm, hcol, dcol, acol in _BOOKMAKER_1X2_CLOSING:
            if hcol in fields or dcol in fields or acol in fields:
                h = _safe_float(row.get(hcol))
                d = _safe_float(row.get(dcol))
                a = _safe_float(row.get(acol))
                if h is not None or d is not None or a is not None:
                    odds_1x2.append({"bookmaker": bm, "is_closing": 1, "home": h, "draw": d, "away": a})

        # 大小球（初盘）
        odds_ou25: list[dict] = []
        for bm, ocol, ucol in _OU25_COLUMNS:
            if ocol in fields or ucol in fields:
                o = _safe_float(row.get(ocol))
                u = _safe_float(row.get(ucol))
                if o is not None or u is not None:
                    odds_ou25.append({"bookmaker": bm, "is_closing": 0, "over": o, "under": u})

        # 大小球（终盘）
        for bm, ocol, ucol in _OU25_CLOSING:
            if ocol in fields or ucol in fields:
                o = _safe_float(row.get(ocol))
                u = _safe_float(row.get(ucol))
                if o is not None or u is not None:
                    odds_ou25.append({"bookmaker": bm, "is_closing": 1, "over": o, "under": u})

        # 亚盘（初盘）
        odds_asian: list[dict] = []
        for bm, hhcol, hacol, ahcol in _ASIAN_COLUMNS:
            if hhcol in fields or hacol in fields:
                hh = _safe_float(row.get(hhcol))
                ha = _safe_float(row.get(hacol))
                ah = _safe_float(row.get(ahcol)) if ahcol and ahcol in fields else handicap_general
                if hh is not None or ha is not None:
                    odds_asian.append({"bookmaker": bm, "is_closing": 0, "handicap": ah, "home": hh, "away": ha})

        # 亚盘（终盘）
        for bm, hhcol, hacol, ahcol in _ASIAN_CLOSING:
            if hhcol in fields or hacol in fields:
                hh = _safe_float(row.get(hhcol))
                ha = _safe_float(row.get(hacol))
                ah = _safe_float(row.get(ahcol)) if ahcol and ahcol in fields else (handicap_closing or handicap_general)
                if hh is not None or ha is not None:
                    odds_asian.append({"bookmaker": bm, "is_closing": 1, "handicap": ah, "home": hh, "away": ha})

        match_data["odds_1x2"] = odds_1x2
        match_data["odds_ou25"] = odds_ou25
        match_data["odds_asian"] = odds_asian
        results.append(match_data)

    return results
