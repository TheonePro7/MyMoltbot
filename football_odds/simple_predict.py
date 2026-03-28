"""极简预测：单场仅一家盘口时，取按比例去水后概率最大的结果。"""

from __future__ import annotations

from typing import Any

from football_odds.analysis import analyze_bookmaker_line


def predict_from_single_line(line: Any) -> dict[str, Any]:
    """line 为 BookmakerLine。"""
    r = analyze_bookmaker_line(line)
    fair = r["fair_probability_proportional"]
    items = [("3", "主胜", fair["home"]), ("1", "平", fair["draw"]), ("0", "客胜", fair["away"])]
    best = max(items, key=lambda x: x[2])
    return {
        "outcome": best[0],
        "label": best[1],
        "confidence": best[2],
        "bookmaker": r["bookmaker"],
        "odds": r["odds"],
    }
