#!/usr/bin/env python3
"""足彩赔率分析命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys

from football_odds.analysis import (
    analyze_bookmaker_line,
    compare_bookmakers,
    load_matches_from_json,
    format_percent,
)
from football_odds.models import BookmakerLine


def _print_line_analysis(line: BookmakerLine) -> None:
    r = analyze_bookmaker_line(line)
    print(f"庄家: {r['bookmaker']}")
    print(
        f"  赔率 主 {r['odds']['home']:.2f} 平 {r['odds']['draw']:.2f} 客 {r['odds']['away']:.2f}"
    )
    imp = r["implied_probability"]
    print(
        f"  隐含概率 主 {format_percent(imp['home'])} 平 {format_percent(imp['draw'])} "
        f"客 {format_percent(imp['away'])}"
    )
    print(f"  抽水(overround): {format_percent(r['overround'])}")
    fair = r["fair_probability_proportional"]
    print(
        f"  去水后(比例法) 主 {format_percent(fair['home'])} 平 {format_percent(fair['draw'])} "
        f"客 {format_percent(fair['away'])}"
    )
    print()


def cmd_analyze_file(args: argparse.Namespace) -> int:
    matches = load_matches_from_json(args.json_path)
    for m in matches:
        print(f"=== {m.match_id} {m.home_team} vs {m.away_team} ===")
        for ln in m.lines:
            _print_line_analysis(ln)
    return 0


def cmd_compare_file(args: argparse.Namespace) -> int:
    matches = load_matches_from_json(args.json_path)
    for m in matches:
        cmp_result = compare_bookmakers(m)
        print(f"=== 对比 {m.match_id} {m.home_team} vs {m.away_team} ===")
        o = cmp_result["odds_range"]
        print(
            f"赔率区间 主 [{o['home']['min']:.2f}, {o['home']['max']:.2f}] "
            f"均值 {o['home']['mean']:.2f}"
        )
        print(
            f"         平 [{o['draw']['min']:.2f}, {o['draw']['max']:.2f}] "
            f"均值 {o['draw']['mean']:.2f}"
        )
        print(
            f"         客 [{o['away']['min']:.2f}, {o['away']['max']:.2f}] "
            f"均值 {o['away']['mean']:.2f}"
        )
        b = cmp_result["best_odds_bookmaker"]
        print(f"最高赔所在庄家 主:{b['home']} 平:{b['draw']} 客:{b['away']}")
        c = cmp_result["consensus_fair_probability_mean"]
        print(
            f"多庄去水后概率均值(粗共识) 主 {format_percent(c['home'])} "
            f"平 {format_percent(c['draw'])} 客 {format_percent(c['away'])}"
        )
        print()
        if args.json_out:
            print(json.dumps(cmp_result, ensure_ascii=False, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="足彩欧赔分析：隐含概率、抽水、多庄对比")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="按庄家逐条分析 JSON 中的赔率")
    a.add_argument("json_path", help="比赛与盘口 JSON 路径")
    a.set_defaults(func=cmd_analyze_file)

    c = sub.add_parser("compare", help="对 JSON 中每场比赛做多庄家对比")
    c.add_argument("json_path", help="比赛与盘口 JSON 路径")
    c.add_argument("--json-out", action="store_true", help="同时输出结构化 JSON")
    c.set_defaults(func=cmd_compare_file)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
