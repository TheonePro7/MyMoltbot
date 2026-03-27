from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from football_odds.models import BookmakerLine, MatchOdds


def implied_probabilities(home: float, draw: float, away: float) -> dict[str, float]:
    """根据十进制赔率计算隐含概率（未去水），三者之和通常大于 1。"""
    return {
        "home": 1.0 / home,
        "draw": 1.0 / draw,
        "away": 1.0 / away,
    }


def overround(implied: dict[str, float]) -> float:
    """庄家抽水（overround）：隐含概率之和减 1。例如 1.08 表示约 8% 抽水。"""
    return implied["home"] + implied["draw"] + implied["away"] - 1.0


def remove_margin_proportional(implied: dict[str, float]) -> dict[str, float]:
    """
    按比例去水：假设抽水按各结果隐含概率成比例分摊（常用简便法）。
    返回归一化后概率，三者之和为 1。
    """
    total = implied["home"] + implied["draw"] + implied["away"]
    if total <= 0:
        raise ValueError("隐含概率之和必须为正")
    return {
        "home": implied["home"] / total,
        "draw": implied["draw"] / total,
        "away": implied["away"] / total,
    }


def analyze_bookmaker_line(line: BookmakerLine) -> dict[str, Any]:
    """分析单一庄家盘口：隐含概率、抽水、去水后概率。"""
    imp = implied_probabilities(line.home, line.draw, line.away)
    fair = remove_margin_proportional(imp)
    return {
        "bookmaker": line.bookmaker,
        "odds": {"home": line.home, "draw": line.draw, "away": line.away},
        "implied_probability": imp,
        "overround": overround(imp),
        "fair_probability_proportional": fair,
    }


def compare_bookmakers(match: MatchOdds) -> dict[str, Any]:
    """
    多庄家对比：每场结果的最高赔、最低赔、简单平均赔；
    以及各庄家去水后主胜概率的简单平均（粗共识，非统计模型）。
    """
    if not match.lines:
        raise ValueError("至少需要一条庄家盘口")

    homes = [ln.home for ln in match.lines]
    draws = [ln.draw for ln in match.lines]
    aways = [ln.away for ln in match.lines]

    best = {
        "home": max(match.lines, key=lambda x: x.home).bookmaker,
        "draw": max(match.lines, key=lambda x: x.draw).bookmaker,
        "away": max(match.lines, key=lambda x: x.away).bookmaker,
    }
    worst = {
        "home": min(match.lines, key=lambda x: x.home).bookmaker,
        "draw": min(match.lines, key=lambda x: x.draw).bookmaker,
        "away": min(match.lines, key=lambda x: x.away).bookmaker,
    }

    analyses = [analyze_bookmaker_line(ln) for ln in match.lines]
    n = len(analyses)
    avg_fair_home = sum(a["fair_probability_proportional"]["home"] for a in analyses) / n
    avg_fair_draw = sum(a["fair_probability_proportional"]["draw"] for a in analyses) / n
    avg_fair_away = sum(a["fair_probability_proportional"]["away"] for a in analyses) / n

    return {
        "match_id": match.match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "bookmaker_count": n,
        "best_odds_bookmaker": best,
        "worst_odds_bookmaker": worst,
        "odds_range": {
            "home": {"min": min(homes), "max": max(homes), "mean": sum(homes) / n},
            "draw": {"min": min(draws), "max": max(draws), "mean": sum(draws) / n},
            "away": {"min": min(aways), "max": max(aways), "mean": sum(aways) / n},
        },
        "consensus_fair_probability_mean": {
            "home": avg_fair_home,
            "draw": avg_fair_draw,
            "away": avg_fair_away,
        },
        "per_bookmaker": analyses,
    }


def _parse_bookmaker_line(obj: dict[str, Any]) -> BookmakerLine:
    return BookmakerLine(
        bookmaker=str(obj["bookmaker"]),
        home=float(obj["home"]),
        draw=float(obj["draw"]),
        away=float(obj["away"]),
    )


def load_matches_from_json(path: str | Path) -> list[MatchOdds]:
    """
    从 JSON 文件加载比赛与盘口。
    格式示例见 examples/matches_sample.json。
    """
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("JSON 根节点应为数组")

    matches: list[MatchOdds] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("每场比赛应为对象")
        lines_raw = item.get("lines", [])
        if not lines_raw:
            raise ValueError(f"比赛 {item.get('match_id', '?')} 缺少 lines")
        lines = tuple(_parse_bookmaker_line(x) for x in lines_raw)
        matches.append(
            MatchOdds(
                match_id=str(item["match_id"]),
                home_team=str(item["home_team"]),
                away_team=str(item["away_team"]),
                lines=lines,
            )
        )
    return matches


def format_percent(x: float, digits: int = 2) -> str:
    """格式化为百分比字符串。"""
    return f"{100.0 * x:.{digits}f}%"
