"""
中英文球队名映射：北单/竞彩中文球队名 ↔ 五大联赛英文球队名。
映射表通过日期+比分唯一匹配自动生成。

用途：对竞彩/北单比赛，查找该球队在五大联赛的历史数据所属联赛，
然后用对应联赛的专属模型做预测。
"""

from __future__ import annotations

import json
from pathlib import Path

_MAPPING_FILE = Path(__file__).resolve().parent.parent / "data" / "team_name_mapping.json"
_mapping: dict[str, str] | None = None


def _load_mapping() -> dict[str, str]:
    global _mapping
    if _mapping is None:
        if _MAPPING_FILE.exists():
            with open(_MAPPING_FILE, "r", encoding="utf-8") as f:
                _mapping = json.load(f)
        else:
            _mapping = {}
    return _mapping


def cn_to_en(cn_name: str) -> str | None:
    """中文球队名转英文。找不到返回 None。"""
    m = _load_mapping()
    return m.get(cn_name)


def find_league(cn_home: str, cn_away: str) -> str | None:
    """
    根据中文球队名判断所属联赛。
    查历史数据库找该英文球队名所在的联赛。
    """
    en_home = cn_to_en(cn_home)
    en_away = cn_to_en(cn_away)
    if not en_home and not en_away:
        return None

    from football_odds.history_db import connect_history
    with connect_history() as conn:
        for en_name in [en_home, en_away]:
            if not en_name:
                continue
            row = conn.execute(
                """SELECT division, COUNT(*) as c FROM matches
                   WHERE (home_team=? OR away_team=?) AND division IN ('E0','E1','SP1','D1','I1','F1')
                   GROUP BY division ORDER BY c DESC LIMIT 1""",
                (en_name, en_name),
            ).fetchone()
            if row:
                return row["division"]
    return None


def get_all_mappings() -> dict[str, str]:
    """返回完整的中英文映射字典。"""
    return dict(_load_mapping())
