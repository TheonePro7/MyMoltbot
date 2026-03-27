"""
特征工程：从历史赔率数据库提取机器学习特征。

核心特征类别：
1. 赔率隐含概率特征（B365、Pinnacle、市场平均）
2. 赔率变动特征（初盘→终盘）
3. 亚盘特征（盘口值 + 水位）
4. 大小球特征
5. 多庄家离散度特征
6. 联赛 + 主客场基准特征
7. 球队近期战绩特征
"""

from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from football_odds.history_db import connect_history

# 优先使用的庄家（按数据覆盖率排序）
_BM_PRIORITY_1X2 = ["B365", "PS", "BW", "WH", "IW", "VC", "LB"]
_BM_PRIORITY_AH = ["BbAvg", "Avg", "B365", "PS"]


def _implied_prob(odds: float) -> float:
    """赔率→隐含概率。"""
    if odds is None or odds <= 1.0:
        return np.nan
    return 1.0 / odds


def _fair_prob(h: float, d: float, a: float) -> tuple[float, float, float]:
    """去水后公平概率（比例法）。"""
    total = h + d + a
    if total <= 0:
        return (np.nan, np.nan, np.nan)
    return (h / total, d / total, a / total)


def load_raw_dataset(conn: sqlite3.Connection,
                      divisions: list[str] | None = None,
                      min_season: str | None = None) -> pd.DataFrame:
    """
    从数据库加载原始比赛数据，合并多庄家赔率为宽表。
    返回每场比赛一行的 DataFrame。
    """
    where_parts = ["m.ftr IS NOT NULL"]
    params: list[Any] = []

    if divisions:
        placeholders = ",".join("?" * len(divisions))
        where_parts.append(f"m.division IN ({placeholders})")
        params.extend(divisions)
    if min_season:
        where_parts.append("m.season >= ?")
        params.append(min_season)

    where = " AND ".join(where_parts)

    matches_df = pd.read_sql_query(
        f"""SELECT m.id as match_id, m.division, m.season, m.match_date,
                   m.home_team, m.away_team, m.fthg, m.ftag, m.ftr,
                   m.hthg, m.htag, m.htr,
                   m.home_shots, m.away_shots, m.home_sot, m.away_sot,
                   m.home_corners, m.away_corners, m.home_fouls, m.away_fouls,
                   m.home_yellows, m.away_yellows, m.home_reds, m.away_reds
            FROM matches m
            WHERE {where}
            ORDER BY m.match_date, m.id""",
        conn,
        params=params,
    )

    if matches_df.empty:
        return matches_df

    match_ids = matches_df["match_id"].tolist()
    id_str = ",".join(str(i) for i in match_ids)

    odds_1x2 = pd.read_sql_query(
        f"""SELECT match_id, bookmaker, is_closing, home_odds, draw_odds, away_odds
            FROM odds_1x2 WHERE match_id IN ({id_str})""",
        conn,
    )

    odds_ah = pd.read_sql_query(
        f"""SELECT match_id, bookmaker, is_closing, handicap, home_odds, away_odds
            FROM odds_asian WHERE match_id IN ({id_str})""",
        conn,
    )

    odds_ou = pd.read_sql_query(
        f"""SELECT match_id, bookmaker, is_closing, over_odds, under_odds
            FROM odds_ou25 WHERE match_id IN ({id_str})""",
        conn,
    )

    return _merge_odds_features(matches_df, odds_1x2, odds_ah, odds_ou)


def _pick_best_1x2(group: pd.DataFrame, bookmaker_priority: list[str],
                     is_closing: int) -> pd.Series:
    """从一组赔率中按庄家优先级选取最佳可用赔率。"""
    sub = group[group["is_closing"] == is_closing]
    for bm in bookmaker_priority:
        row = sub[sub["bookmaker"] == bm]
        if not row.empty:
            r = row.iloc[0]
            if pd.notna(r["home_odds"]) and r["home_odds"] > 1:
                return r
    if not sub.empty:
        return sub.iloc[0]
    return pd.Series(dtype=float)


def _merge_odds_features(matches: pd.DataFrame, odds_1x2: pd.DataFrame,
                          odds_ah: pd.DataFrame, odds_ou: pd.DataFrame) -> pd.DataFrame:
    """将多庄家赔率合并到比赛主表。"""
    df = matches.copy()

    # 欧赔特征：初盘
    # 庄家名映射：竞彩/北单 SP 映射到标准 B365/PS 特征列
    _BM_ALIASES = {
        "B365": ["B365", "Bet365", "竞彩SP", "北单SP"],
        "PS": ["PS", "Pinnacle", "竞彩让球SP"],
    }

    if not odds_1x2.empty:
        open_1x2 = odds_1x2[odds_1x2["is_closing"] == 0]
        for bm, aliases in _BM_ALIASES.items():
            matched = open_1x2[open_1x2["bookmaker"].isin(aliases)]
            if matched.empty:
                matched = open_1x2[open_1x2["bookmaker"] == bm]
            bm_data = matched.drop_duplicates(subset=["match_id"], keep="first").set_index("match_id")
            suffix = f"_{bm.lower()}_open"
            for col in ["home_odds", "draw_odds", "away_odds"]:
                new_name = col.replace("_odds", "") + suffix
                if new_name not in df.columns:
                    df = df.merge(
                        bm_data[[col]].rename(columns={col: new_name}),
                        left_on="match_id", right_index=True, how="left",
                    )

        # 终盘
        close_1x2 = odds_1x2[odds_1x2["is_closing"] == 1]
        for bm in ["B365", "PS"]:
            bm_aliases = _BM_ALIASES.get(bm, [bm])
            matched = close_1x2[close_1x2["bookmaker"].isin(bm_aliases)]
            if matched.empty:
                matched = close_1x2[close_1x2["bookmaker"] == bm]
            bm_data = matched.drop_duplicates(subset=["match_id"], keep="first").set_index("match_id")
            suffix = f"_{bm.lower()}_close"
            for col in ["home_odds", "draw_odds", "away_odds"]:
                new_name = col.replace("_odds", "") + suffix
                if new_name not in df.columns:
                    df = df.merge(
                        bm_data[[col]].rename(columns={col: new_name}),
                        left_on="match_id", right_index=True, how="left",
                    )

        # 市场平均 / 最大
        for bm_label, bm_key in [("avg", "Avg"), ("max", "Max"), ("bbavg", "BbAvg")]:
            bm_data = open_1x2[open_1x2["bookmaker"] == bm_key].drop_duplicates(
                subset=["match_id"], keep="first").set_index("match_id")
            suffix = f"_{bm_label}_open"
            for col in ["home_odds", "draw_odds", "away_odds"]:
                new_name = col.replace("_odds", "") + suffix
                if new_name not in df.columns:
                    df = df.merge(
                        bm_data[[col]].rename(columns={col: new_name}),
                        left_on="match_id", right_index=True, how="left",
                    )

        # 多庄家统计
        stats = open_1x2.groupby("match_id").agg(
            bm_count=("bookmaker", "nunique"),
            home_odds_std=("home_odds", "std"),
            draw_odds_std=("draw_odds", "std"),
            away_odds_std=("away_odds", "std"),
            home_odds_mean=("home_odds", "mean"),
            draw_odds_mean=("draw_odds", "mean"),
            away_odds_mean=("away_odds", "mean"),
        )
        for col in stats.columns:
            if col not in df.columns:
                df = df.merge(stats[[col]], left_on="match_id", right_index=True, how="left")

    # 亚盘特征
    if not odds_ah.empty:
        ah_open = odds_ah[odds_ah["is_closing"] == 0]
        for bm_label, bm_keys in [("ah_b365", ["B365"]), ("ah_avg", ["Avg", "BbAvg"])]:
            for bm_key in bm_keys:
                bm_data = ah_open[ah_open["bookmaker"] == bm_key].set_index("match_id")
                if not bm_data.empty:
                    df = df.merge(
                        bm_data[["handicap", "home_odds", "away_odds"]].rename(columns={
                            "handicap": f"{bm_label}_handicap",
                            "home_odds": f"{bm_label}_home",
                            "away_odds": f"{bm_label}_away",
                        }),
                        left_on="match_id", right_index=True, how="left",
                    )
                    break

    # 大小球特征
    if not odds_ou.empty:
        ou_open = odds_ou[odds_ou["is_closing"] == 0]
        for bm_label, bm_keys in [("ou_b365", ["B365"]), ("ou_avg", ["Avg", "BbAvg"])]:
            for bm_key in bm_keys:
                bm_data = ou_open[ou_open["bookmaker"] == bm_key].set_index("match_id")
                if not bm_data.empty:
                    df = df.merge(
                        bm_data[["over_odds", "under_odds"]].rename(columns={
                            "over_odds": f"{bm_label}_over",
                            "under_odds": f"{bm_label}_under",
                        }),
                        left_on="match_id", right_index=True, how="left",
                    )
                    break

    return df


def compute_features(df: pd.DataFrame, add_team_features: bool = True) -> pd.DataFrame:
    """
    在宽表基础上计算衍生特征。返回增加了特征列的 DataFrame。
    add_team_features: 是否计算球队近期战绩（首次训练时设为 True）。
    """
    out = df.copy()

    # 隐含概率（B365 初盘为主，Pinnacle 作为补充）
    for prefix, bm_suffix in [("b365", "b365_open"), ("ps", "ps_open")]:
        h_col = f"home_{bm_suffix}"
        d_col = f"draw_{bm_suffix}"
        a_col = f"away_{bm_suffix}"
        if h_col in out.columns:
            out[f"ip_home_{prefix}"] = out[h_col].apply(_implied_prob)
            out[f"ip_draw_{prefix}"] = out[d_col].apply(_implied_prob)
            out[f"ip_away_{prefix}"] = out[a_col].apply(_implied_prob)
            total = out[f"ip_home_{prefix}"] + out[f"ip_draw_{prefix}"] + out[f"ip_away_{prefix}"]
            out[f"overround_{prefix}"] = total - 1.0
            out[f"fp_home_{prefix}"] = out[f"ip_home_{prefix}"] / total
            out[f"fp_draw_{prefix}"] = out[f"ip_draw_{prefix}"] / total
            out[f"fp_away_{prefix}"] = out[f"ip_away_{prefix}"] / total

    # 赔率变动（终盘 - 初盘，仅在有终盘数据时）
    for bm in ["b365", "ps"]:
        for outcome in ["home", "draw", "away"]:
            open_col = f"{outcome}_{bm}_open"
            close_col = f"{outcome}_{bm}_close"
            if open_col in out.columns and close_col in out.columns:
                out[f"drift_{outcome}_{bm}"] = out[close_col] - out[open_col]
                out[f"drift_pct_{outcome}_{bm}"] = (out[close_col] - out[open_col]) / out[open_col]

    # 联赛编码
    if "division" in out.columns:
        out["div_encoded"] = pd.Categorical(out["division"]).codes

    # 球队近期战绩特征
    if add_team_features and "home_team" in out.columns and "ftr" in out.columns:
        try:
            from ai.team_features import compute_team_features
            out = compute_team_features(out)
        except Exception:
            pass

    # 目标变量
    out["target"] = out["ftr"].map({"H": 0, "D": 1, "A": 2})

    return out


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """返回适合训练的特征列名。"""
    exclude = {
        "match_id", "division", "season", "match_date", "home_team", "away_team",
        "fthg", "ftag", "ftr", "hthg", "htag", "htr", "referee", "target",
        "match_time",
    }
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    return [c for c in numeric_cols if c not in exclude]


def build_dataset(divisions: list[str] | None = None,
                   min_season: str | None = None) -> pd.DataFrame:
    """一键构建特征完整的数据集。"""
    with connect_history() as conn:
        raw = load_raw_dataset(conn, divisions=divisions, min_season=min_season)
    if raw.empty:
        return raw
    return compute_features(raw)
