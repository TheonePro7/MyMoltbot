from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BookmakerLine:
    """单场 1X2 欧赔（十进制）。"""

    bookmaker: str
    home: float
    draw: float
    away: float

    def __post_init__(self) -> None:
        for name, val in (("home", self.home), ("draw", self.draw), ("away", self.away)):
            if val <= 1.0:
                raise ValueError(f"{name} 赔率必须大于 1.0，当前为 {val}")


@dataclass(frozen=True)
class MatchOdds:
    """一场比赛在多家公司的盘口。"""

    match_id: str
    home_team: str
    away_team: str
    lines: tuple[BookmakerLine, ...]
