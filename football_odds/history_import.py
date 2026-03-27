"""
历史数据导入编排：从 football-data.co.uk 批量下载 CSV 并导入 SQLite。
支持命令行直接运行：python3 -m football_odds.history_import
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Callable

from football_odds.history_csv import (
    ALL_LEAGUES,
    MAIN_LEAGUES,
    download_csv,
    parse_csv_rows,
    season_code_range,
)
from football_odds.history_db import (
    connect_history,
    count_matches,
    insert_match,
    insert_odds_1x2,
    insert_odds_asian,
    insert_odds_ou25,
    is_imported,
    mark_imported,
    summary_stats,
)


def import_single(division: str, season: str, force: bool = False,
                   progress_fn: Callable[[str], None] | None = None) -> int:
    """
    导入单个赛季单个联赛。返回导入的比赛数量。
    如果已导入且 force=False，则跳过返回 -1。
    """
    def log(msg: str) -> None:
        if progress_fn:
            progress_fn(msg)

    with connect_history() as conn:
        if not force and is_imported(conn, division, season):
            log(f"  跳过 {division}/{season}（已导入）")
            return -1

    log(f"  下载 {division}/{season} ...")
    csv_text = download_csv(season, division)
    if csv_text is None:
        log(f"  {division}/{season} 无数据（404 或空文件）")
        return 0

    log(f"  解析 CSV ...")
    rows = parse_csv_rows(csv_text, season)
    if not rows:
        log(f"  {division}/{season} 解析后无有效行")
        return 0

    log(f"  写入数据库（{len(rows)} 场比赛）...")
    count = 0
    with connect_history() as conn:
        for match_data in rows:
            odds_1x2 = match_data.pop("odds_1x2", [])
            odds_ou25 = match_data.pop("odds_ou25", [])
            odds_asian = match_data.pop("odds_asian", [])

            match_id = insert_match(conn, match_data)
            if match_id <= 0:
                continue

            for od in odds_1x2:
                insert_odds_1x2(conn, match_id, od["bookmaker"], od["is_closing"],
                                od.get("home"), od.get("draw"), od.get("away"))

            for od in odds_ou25:
                insert_odds_ou25(conn, match_id, od["bookmaker"], od["is_closing"],
                                  od.get("over"), od.get("under"))

            for od in odds_asian:
                insert_odds_asian(conn, match_id, od["bookmaker"], od["is_closing"],
                                   od.get("handicap"), od.get("home"), od.get("away"))

            count += 1

        conn.commit()
        mark_imported(conn, division, season, count)

    log(f"  完成 {division}/{season}：{count} 场比赛")
    return count


def import_batch(n_seasons: int = 20, leagues: str = "main", force: bool = False,
                  progress_fn: Callable[[str], None] | None = None) -> dict[str, Any]:
    """
    批量导入。leagues 可选 'main'（五大联赛顶级）或 'all'（全部）。
    返回导入统计摘要。
    """
    def log(msg: str) -> None:
        if progress_fn:
            progress_fn(msg)

    league_map = MAIN_LEAGUES if leagues == "main" else ALL_LEAGUES
    seasons = season_code_range(n_seasons)

    all_divs = []
    for divs in league_map.values():
        all_divs.extend(divs)

    total_tasks = len(all_divs) * len(seasons)
    total_imported = 0
    total_skipped = 0
    total_empty = 0
    done = 0
    errors: list[str] = []

    log(f"开始导入：{len(all_divs)} 个联赛 × {len(seasons)} 个赛季 = {total_tasks} 个文件")
    log(f"赛季范围：{seasons[-1]} 到 {seasons[0]}")
    log("")

    for season in seasons:
        for div in all_divs:
            done += 1
            try:
                n = import_single(div, season, force=force, progress_fn=progress_fn)
                if n == -1:
                    total_skipped += 1
                elif n == 0:
                    total_empty += 1
                else:
                    total_imported += n
            except Exception as e:
                msg = f"错误 {div}/{season}: {e}"
                log(msg)
                errors.append(msg)

            if done % 5 == 0:
                log(f"  进度：{done}/{total_tasks}")

            time.sleep(0.3)

    log("")
    log(f"导入完成！总计 {total_imported} 场比赛，跳过 {total_skipped} 个已导入文件，{total_empty} 个空文件")

    with connect_history() as conn:
        stats = summary_stats(conn)

    return {
        "imported_matches": total_imported,
        "skipped_files": total_skipped,
        "empty_files": total_empty,
        "errors": errors,
        "db_stats": stats,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="导入 football-data.co.uk 历史赔率数据")
    p.add_argument("--seasons", type=int, default=20, help="导入赛季数量（从 2025/26 向前，默认 20）")
    p.add_argument("--leagues", choices=["main", "all"], default="main",
                    help="联赛范围：main=五大联赛顶级（E0,SP1,D1,I1,F1），all=全部")
    p.add_argument("--force", action="store_true", help="强制重新导入（忽略已导入标记）")
    p.add_argument("--division", type=str, default=None, help="只导入指定联赛代码（如 E0）")
    p.add_argument("--season", type=str, default=None, help="只导入指定赛季代码（如 2526）")
    p.add_argument("--stats", action="store_true", help="只显示当前数据库统计信息")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    def log(msg: str) -> None:
        print(msg, flush=True)

    if args.stats:
        with connect_history() as conn:
            stats = summary_stats(conn)
        log(f"数据库总比赛数：{stats['total_matches']}")
        log(f"欧赔记录数：{stats['total_odds_records']}")
        log(f"亚盘记录数：{stats['total_asian_records']}")
        log("")
        if stats["by_division"]:
            log(f"{'联赛':>6} {'国家':<12} {'名称':<20} {'比赛数':>8} {'赛季范围'}")
            for d in stats["by_division"]:
                log(f"{d['division']:>6} {d['country'] or '':<12} {d['league_name'] or '':<20} "
                    f"{d['match_count']:>8} {d['first_season']}-{d['last_season']}")
        return 0

    if args.division and args.season:
        n = import_single(args.division, args.season, force=args.force, progress_fn=log)
        log(f"导入结果：{n} 场比赛")
        return 0

    result = import_batch(
        n_seasons=args.seasons,
        leagues=args.leagues,
        force=args.force,
        progress_fn=log,
    )
    stats = result["db_stats"]
    log(f"\n数据库统计：")
    log(f"  总比赛数：{stats['total_matches']}")
    log(f"  欧赔记录数：{stats['total_odds_records']}")
    log(f"  亚盘记录数：{stats['total_asian_records']}")
    if result["errors"]:
        log(f"\n遇到 {len(result['errors'])} 个错误：")
        for e in result["errors"]:
            log(f"  - {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
