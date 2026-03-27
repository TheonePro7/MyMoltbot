"""
竞彩组合过关子注生成（含胆拖）与赛果结算（胜平负 / 让球胜平负）。
单注金额由调用方乘以子注条数；本模块只负责子注集合与命中判定。
"""

from __future__ import annotations

import itertools
from typing import Any, Iterable

# 每种玩法：在选中 n 场且不含胆时，包含的「串关长度」k（每一长度下取所有 C(n,k) 个子注）
# 单关：n 场时每场单独 1 注（在生成函数中单独处理）
COMBO_FOLD_SIZES: dict[str, list[int]] = {
    "单关": [],  # 特殊
    "2串1": [],  # 特殊：仅 n==2 时 1 注
    "3串1": [],
    "4串1": [],
    "5串1": [],
    "2串3": [1, 2],
    "3串4": [2, 3],
    "3串7": [1, 2, 3],
    "4串5": [3, 4],
    "4串11": [2, 3, 4],
    "4串15": [1, 2, 3, 4],
    "5串6": [4, 5],
    "5串16": [3, 4, 5],
    "5串26": [2, 3, 4, 5],
    "5串31": [1, 2, 3, 4, 5],
}

MAX_COMBO_TYPES = 5


def parse_handicap_int(s: str | None) -> int:
    """页面让球字符串，如 -1、+1、0，转为整数（主队视角加分）。"""
    if s is None or str(s).strip() == "":
        return 0
    t = str(s).strip().replace(" ", "")
    return int(t)


def actual_outcome_nspf(home_goals: int, away_goals: int) -> str:
    """返回 data-value：3 主胜 1 平 0 客胜。"""
    if home_goals > away_goals:
        return "3"
    if home_goals == away_goals:
        return "1"
    return "0"


def actual_outcome_spf(home_goals: int, away_goals: int, handicap: str | None) -> str:
    """让球胜平负：主队有效进球 = 实际进球 + 让球值（负为主让）。"""
    h = parse_handicap_int(handicap)
    home_eff = home_goals + h
    if home_eff > away_goals:
        return "3"
    if home_eff == away_goals:
        return "1"
    return "0"


def selection_actual_outcome(sel: dict[str, Any], home_goals: int, away_goals: int) -> str:
    m = sel.get("market") or ""
    if m == "nspf":
        return actual_outcome_nspf(home_goals, away_goals)
    if m == "spf":
        return actual_outcome_spf(home_goals, away_goals, sel.get("handicap"))
    raise ValueError(f"未知玩法: {m}")


def selection_matches_pick(sel: dict[str, Any], home_goals: int, away_goals: int) -> bool:
    actual = selection_actual_outcome(sel, home_goals, away_goals)
    return str(sel.get("outcome")) == actual


def _dan_ok(indices: Iterable[int], dan: frozenset[int]) -> bool:
    s = frozenset(indices)
    return dan.issubset(s)


def _subsets_for_fold_sizes(
    n: int,
    fold_sizes: list[int],
    dan: frozenset[int],
) -> list[frozenset[int]]:
    """生成所有子注（用选中项下标 0..n-1）。"""
    idxs = list(range(n))
    out: list[frozenset[int]] = []
    for k in fold_sizes:
        if k < len(dan):
            continue
        for comb in itertools.combinations(idxs, k):
            fs = frozenset(comb)
            if dan.issubset(fs):
                out.append(fs)
    return out


def generate_subbet_index_sets(
    n: int,
    combo_type_keys: list[str],
    dan_indices: set[int],
) -> list[frozenset[int]]:
    """
    n 为选中场次数量；dan_indices 为胆在 0..n-1 中的下标集合。
    返回去重后的子注（每场下标集合）。
    """
    if len(combo_type_keys) > MAX_COMBO_TYPES:
        raise ValueError(f"组合过关最多 {MAX_COMBO_TYPES} 种")
    if not combo_type_keys:
        raise ValueError("请至少选择一种过关方式")
    dan_f = frozenset(dan_indices)
    if not dan_f.issubset(range(n)):
        raise ValueError("胆下标不合法")
    seen: set[frozenset[int]] = set()
    ordered: list[frozenset[int]] = []

    for key in combo_type_keys:
        key = key.strip()
        if key == "单关":
            if n < 1:
                raise ValueError("单关至少选 1 场")
            for i in range(n):
                fs = frozenset({i})
                if not _dan_ok(fs, dan_f):
                    continue
                if fs not in seen:
                    seen.add(fs)
                    ordered.append(fs)
            continue
        if key.endswith("串1") and "串" in key:
            need_str = key.split("串", 1)[0]
            if not need_str.isdigit():
                raise ValueError(f"无法解析过关: {key}")
            need = int(need_str)
            if n != need:
                raise ValueError(f"{key} 需恰好选择 {need} 场比赛")
            fs = frozenset(range(n))
            if not dan_f.issubset(fs):
                raise ValueError("胆必须包含在子注中")
            if fs not in seen:
                seen.add(fs)
                ordered.append(fs)
            continue
        sizes = COMBO_FOLD_SIZES.get(key)
        if sizes is None:
            raise ValueError(f"不支持的过关方式: {key}")
        for fs in _subsets_for_fold_sizes(n, sizes, dan_f):
            if fs not in seen:
                seen.add(fs)
                ordered.append(fs)
    if not ordered:
        raise ValueError("当前胆拖与过关组合无法生成任何子注")
    return ordered


def build_subbet_lines(
    selections_ordered: list[dict[str, Any]],
    combo_type_keys: list[str],
    dan_selection_ids: set[str],
) -> list[dict[str, Any]]:
    """
    selections_ordered 为用户勾选顺序；dan_selection_ids 为勾胆的 selection_id 集合。
    返回每条子注：{"picks": [sel0, sel1, ...], "odds_product": float}
    """
    n = len(selections_ordered)
    id_to_i = {s["selection_id"]: i for i, s in enumerate(selections_ordered)}
    dan_indices = {id_to_i[i] for i in dan_selection_ids if i in id_to_i}
    if len(dan_indices) != len(dan_selection_ids):
        raise ValueError("存在无效的胆选项")
    index_sets = generate_subbet_index_sets(n, combo_type_keys, dan_indices)
    lines: list[dict[str, Any]] = []
    for fs in index_sets:
        picks = [selections_ordered[i] for i in sorted(fs)]
        prod = 1.0
        for p in picks:
            prod *= float(p["odds"])
        lines.append({"picks": picks, "odds_product": prod})
    return lines


def line_is_won(picks: list[dict[str, Any]], results_by_fixture: dict[str, tuple[int, int]]) -> bool:
    """results_by_fixture: fixture_id -> (主队进球, 客队进球)。"""
    for p in picks:
        fid = p.get("fixture_id")
        if not fid or fid not in results_by_fixture:
            return False
        hg, ag = results_by_fixture[fid]
        if not selection_matches_pick(p, hg, ag):
            return False
    return True


def settle_lines(
    lines: list[dict[str, Any]],
    results_by_fixture: dict[str, tuple[int, int]],
    stake_per_line: float,
    multiplier: int = 1,
) -> tuple[list[dict[str, Any]], float, float]:
    """
    返回 (逐行结果带 won/payout), 总返还, 盈亏。
    命中：返还 = stake_per_line * multiplier * odds_product
    """
    per = float(stake_per_line) * int(multiplier)
    out_lines: list[dict[str, Any]] = []
    total_payout = 0.0
    for ln in lines:
        picks = ln["picks"]
        prod = float(ln["odds_product"])
        won = line_is_won(picks, results_by_fixture)
        payout = per * prod if won else 0.0
        total_payout += payout
        row = dict(ln)
        row["won"] = won
        row["payout"] = payout
        row["stake"] = per
        out_lines.append(row)
    total_stake = per * len(lines)
    profit = total_payout - total_stake
    return out_lines, total_payout, profit


def list_combo_options_for_n(n: int) -> list[str]:
    """返回当前 n 场时可用的过关名称（用于表单）；n>5 时仅单关与本场 n 串 1。"""
    if n < 1:
        return []
    out: list[str] = ["单关"]
    if n >= 2:
        out.append(f"{n}串1")
    if n == 2:
        out.append("2串3")
    elif n == 3:
        out.extend(["3串4", "3串7"])
    elif n == 4:
        out.extend(["4串5", "4串11", "4串15"])
    elif n == 5:
        out.extend(["5串6", "5串16", "5串26", "5串31"])
    return out
