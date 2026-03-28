"""
球队战绩特征：从历史比赛中计算每支球队在每场比赛前的近期战绩。
这些特征在赛前就可以获取（不像射门角球等需要赛后），是提升预测准确率的关键。

特征包括：
1. 近 N 场整体战绩（胜率/平率/负率/进球均值/失球均值/净胜球）
2. 近 N 场主场/客场专属战绩
3. 历史交锋战绩
4. 球队当前连胜/连败/连平/不败场次
5. ELO 评分
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def compute_team_features(df: pd.DataFrame, windows: list[int] = [5, 10]) -> pd.DataFrame:
    """
    给每场比赛添加球队近期战绩特征。
    df 必须按 match_date 排序，包含 home_team, away_team, fthg, ftag, ftr 列。
    """
    df = df.sort_values(["match_date", "match_id"]).reset_index(drop=True)

    # 预分配特征列
    feat_cols = []
    for w in windows:
        for side in ["home", "away"]:
            for stat in ["win_rate", "draw_rate", "lose_rate", "goals_scored_avg",
                         "goals_conceded_avg", "goal_diff_avg", "points_avg"]:
                feat_cols.append(f"{side}_last{w}_{stat}")
            for venue_stat in ["venue_win_rate", "venue_goals_avg"]:
                feat_cols.append(f"{side}_last{w}_{venue_stat}")

    for col in ["home_streak_w", "home_streak_l", "home_streak_unbeaten",
                "away_streak_w", "away_streak_l", "away_streak_unbeaten",
                "h2h_home_win_rate", "h2h_draw_rate", "h2h_total_games",
                "home_elo", "away_elo"]:
        feat_cols.append(col)

    for col in feat_cols:
        df[col] = np.nan

    # 构建每支球队的历史记录
    team_history: dict[str, list[dict]] = {}
    team_elo: dict[str, float] = {}
    h2h_history: dict[str, list[dict]] = {}

    K_ELO = 20.0
    DEFAULT_ELO = 1500.0

    for idx in range(len(df)):
        row = df.iloc[idx]
        ht = row["home_team"]
        at = row["away_team"]
        fthg = row.get("fthg")
        ftag = row.get("ftag")
        ftr = row.get("ftr")

        # 计算特征（用当前比赛之前的数据）
        for side, team, is_home in [("home", ht, True), ("away", at, False)]:
            hist = team_history.get(team, [])

            for w in windows:
                recent = hist[-w:] if len(hist) >= w else hist
                if not recent:
                    continue

                wins = sum(1 for g in recent if g["result"] == "W")
                draws = sum(1 for g in recent if g["result"] == "D")
                losses = sum(1 for g in recent if g["result"] == "L")
                n = len(recent)
                gs = [g["goals_scored"] for g in recent]
                gc = [g["goals_conceded"] for g in recent]

                df.at[idx, f"{side}_last{w}_win_rate"] = wins / n
                df.at[idx, f"{side}_last{w}_draw_rate"] = draws / n
                df.at[idx, f"{side}_last{w}_lose_rate"] = losses / n
                df.at[idx, f"{side}_last{w}_goals_scored_avg"] = np.mean(gs)
                df.at[idx, f"{side}_last{w}_goals_conceded_avg"] = np.mean(gc)
                df.at[idx, f"{side}_last{w}_goal_diff_avg"] = np.mean([a - b for a, b in zip(gs, gc)])
                df.at[idx, f"{side}_last{w}_points_avg"] = (wins * 3 + draws) / n

                # 主客场专属
                venue_key = "home" if is_home else "away"
                venue_games = [g for g in recent if g["venue"] == venue_key]
                if venue_games:
                    v_wins = sum(1 for g in venue_games if g["result"] == "W")
                    v_gs = [g["goals_scored"] for g in venue_games]
                    df.at[idx, f"{side}_last{w}_venue_win_rate"] = v_wins / len(venue_games)
                    df.at[idx, f"{side}_last{w}_venue_goals_avg"] = np.mean(v_gs)

            # 连胜/连败/不败
            if hist:
                streak_w = 0
                for g in reversed(hist):
                    if g["result"] == "W":
                        streak_w += 1
                    else:
                        break
                streak_l = 0
                for g in reversed(hist):
                    if g["result"] == "L":
                        streak_l += 1
                    else:
                        break
                streak_ub = 0
                for g in reversed(hist):
                    if g["result"] != "L":
                        streak_ub += 1
                    else:
                        break

                df.at[idx, f"{side}_streak_w"] = streak_w
                df.at[idx, f"{side}_streak_l"] = streak_l
                df.at[idx, f"{side}_streak_unbeaten"] = streak_ub

            # ELO
            df.at[idx, f"{side}_elo"] = team_elo.get(team, DEFAULT_ELO)

        # 历史交锋
        h2h_key = f"{ht}|{at}" if ht < at else f"{at}|{ht}"
        h2h = h2h_history.get(h2h_key, [])
        if h2h:
            # 从主队视角
            home_wins = sum(1 for g in h2h if g["home"] == ht and g["result"] == "H")
            home_wins += sum(1 for g in h2h if g["home"] != ht and g["result"] == "A")
            draws_h2h = sum(1 for g in h2h if g["result"] == "D")
            df.at[idx, "h2h_home_win_rate"] = home_wins / len(h2h)
            df.at[idx, "h2h_draw_rate"] = draws_h2h / len(h2h)
            df.at[idx, "h2h_total_games"] = len(h2h)

        # 更新历史（只在有比赛结果时更新）
        if ftr in ("H", "D", "A") and fthg is not None:
            fthg, ftag = int(fthg), int(ftag)

            # 主队记录
            h_result = "W" if ftr == "H" else ("D" if ftr == "D" else "L")
            team_history.setdefault(ht, []).append({
                "result": h_result, "goals_scored": fthg, "goals_conceded": ftag, "venue": "home"
            })

            # 客队记录
            a_result = "W" if ftr == "A" else ("D" if ftr == "D" else "L")
            team_history.setdefault(at, []).append({
                "result": a_result, "goals_scored": ftag, "goals_conceded": fthg, "venue": "away"
            })

            # 交锋记录
            h2h_history.setdefault(h2h_key, []).append({
                "home": ht, "result": ftr
            })

            # 更新 ELO
            elo_h = team_elo.get(ht, DEFAULT_ELO)
            elo_a = team_elo.get(at, DEFAULT_ELO)
            exp_h = 1.0 / (1.0 + 10 ** ((elo_a - elo_h) / 400.0))
            actual_h = 1.0 if ftr == "H" else (0.5 if ftr == "D" else 0.0)
            team_elo[ht] = elo_h + K_ELO * (actual_h - exp_h)
            team_elo[at] = elo_a + K_ELO * ((1 - actual_h) - (1 - exp_h))

    return df
