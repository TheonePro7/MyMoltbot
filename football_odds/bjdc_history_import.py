"""
北单历史数据批量导入：从 500.com 抓取所有历史期号的北单数据。
包含北单SP、竞彩SP、让球、比分，写入 history.sqlite3。

用法：
  python3 -m football_odds.bjdc_history_import              # 导入全部（约1000期）
  python3 -m football_odds.bjdc_history_import --recent 100  # 只导入最近100期
  python3 -m football_odds.bjdc_history_import --stats       # 查看已导入统计
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any

from football_odds.bjdc import BjdcRow, fetch_bjdc
from football_odds.history_db import (
    connect_history,
    insert_match,
    insert_odds_1x2,
    insert_odds_asian,
)

# 全部可用期号（从用户提供的 select 列表提取，2024年至今）
# 更早的期号（2007-2023）数量太多，先导入近3年
EXPECTS_RECENT = [
    "26039","26038","26037","26036","26035","26034","26033","26032","26031",
    "26026","26025","26024","26023","26022","26021","26019","26018","26017",
    "26016","26015","26014","26013","26012","26011",
    "25125","25124","25123","25122","25121","25115","25114","25113","25112",
    "25111","25105","25104","25103","25102","25101","25095","25094","25093",
    "25092","25091","25085","25084","25083","25082","25081","25075","25074",
    "25073","25072","25071","25065","25064","25063","25062","25061","25055",
    "25054","25053","25052","25051","25044","25043","25042","25041","25035",
    "25034","25033","25032","25031","25024","25023","25022","25021","25014",
    "25013","25012","25011",
    "24125","24124","24123","24122","24121","24115","24114","24113","24112",
    "24111","24105","24104","24103","24102","24101","24095","24094","24093",
    "24092","24091","24085","24084","24083","24082","24081","24075","24074",
    "24073","24072","24071","24065","24064","24063","24062","24061","24055",
    "24054","24053","24052","24051","24045","24044","24043","24042","24041",
    "24035","24034","24033","24032","24031","24024","24023","24022","24021",
    "24015","24014","24013","24012","24011",
]


def _parse_handicap_float(s: str) -> float | None:
    s = s.strip()
    if not s or s == "0":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def _is_expect_imported(conn: sqlite3.Connection, expect: str) -> bool:
    """检查某期号是否已导入。"""
    row = conn.execute(
        "SELECT 1 FROM import_log WHERE division='BD' AND season=?",
        (expect,),
    ).fetchone()
    return row is not None


def _mark_expect_imported(conn: sqlite3.Connection, expect: str, count: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO import_log (division, season, imported_at, rows_count) VALUES (?, ?, ?, ?)",
        ("BD", expect, now, count),
    )
    conn.commit()


def import_single_expect(expect: str, force: bool = False, log_fn=None) -> int:
    """导入单期北单数据。返回导入的比赛数。"""
    def log(msg):
        if log_fn: log_fn(msg)

    with connect_history() as conn:
        if not force and _is_expect_imported(conn, expect):
            return -1

    try:
        rows = fetch_bjdc(expect=expect)
    except Exception as e:
        log(f"  抓取失败 {expect}: {e}")
        return 0

    if not rows:
        return 0

    count = 0
    with connect_history() as conn:
        for br in rows:
            if not br.home_team or not br.away_team:
                continue

            date = br.match_date or ""

            match_data = {
                "division": "BD",
                "season": expect,
                "match_date": date,
                "match_time": br.kickoff,
                "home_team": br.home_team,
                "away_team": br.away_team,
                "fthg": None, "ftag": None, "ftr": None,
                "hthg": None, "htag": None, "htr": None,
                "referee": br.league,
                "home_shots": None, "away_shots": None,
                "home_sot": None, "away_sot": None,
                "home_corners": None, "away_corners": None,
                "home_fouls": None, "away_fouls": None,
                "home_yellows": None, "away_yellows": None,
                "home_reds": None, "away_reds": None,
            }

            if br.score_text and re.match(r'^\d+:\d+$', br.score_text):
                parts = br.score_text.split(":")
                hg, ag = int(parts[0]), int(parts[1])
                match_data["fthg"] = hg
                match_data["ftag"] = ag
                match_data["ftr"] = "H" if hg > ag else ("D" if hg == ag else "A")

            match_id = insert_match(conn, match_data)
            if match_id <= 0:
                continue

            if br.bd_sp_win is not None:
                insert_odds_1x2(conn, match_id, "北单SP", 0,
                                br.bd_sp_win, br.bd_sp_draw, br.bd_sp_lose)
                handicap = _parse_handicap_float(br.handicap)
                if handicap is not None:
                    insert_odds_asian(conn, match_id, "北单", 0,
                                      handicap, br.bd_sp_win, br.bd_sp_lose)

            if br.jc_sp_win is not None:
                insert_odds_1x2(conn, match_id, "竞彩SP", 0,
                                br.jc_sp_win, br.jc_sp_draw, br.jc_sp_lose)

            count += 1

        conn.commit()
        _mark_expect_imported(conn, expect, count)

    return count


def import_batch(expects: list[str] | None = None, force: bool = False,
                  log_fn=None) -> dict[str, Any]:
    """批量导入多期北单数据。"""
    def log(msg):
        if log_fn: log_fn(msg)

    target = expects or EXPECTS_RECENT
    total = 0
    skipped = 0
    empty = 0
    errors = 0

    log(f"开始导入 {len(target)} 期北单历史数据...")

    for i, expect in enumerate(target):
        n = import_single_expect(expect, force=force, log_fn=log_fn)
        if n == -1:
            skipped += 1
        elif n == 0:
            empty += 1
        elif n > 0:
            total += n
            log(f"  [{i+1}/{len(target)}] 期号 {expect}: {n} 场")
        else:
            errors += 1

        if (i + 1) % 20 == 0:
            log(f"  进度: {i+1}/{len(target)}, 已导入 {total} 场")

        time.sleep(0.5)

    log(f"\n导入完成: {total} 场比赛, 跳过 {skipped} 期(已导入), {empty} 期(空), {errors} 个错误")

    with connect_history() as conn:
        bd_count = conn.execute(
            "SELECT COUNT(*) as c FROM matches WHERE division='BD'"
        ).fetchone()
        bd_with_result = conn.execute(
            "SELECT COUNT(*) as c FROM matches WHERE division='BD' AND ftr IS NOT NULL"
        ).fetchone()

    return {
        "imported": total,
        "skipped": skipped,
        "empty": empty,
        "errors": errors,
        "total_bd_matches": bd_count["c"] if bd_count else 0,
        "total_bd_with_result": bd_with_result["c"] if bd_with_result else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="北单历史数据批量导入")
    parser.add_argument("--recent", type=int, default=None,
                        help="只导入最近 N 期（默认全部）")
    parser.add_argument("--force", action="store_true", help="强制重新导入")
    parser.add_argument("--stats", action="store_true", help="查看已导入统计")
    args = parser.parse_args()

    def log(msg):
        print(msg, flush=True)

    if args.stats:
        with connect_history() as conn:
            bd_count = conn.execute(
                "SELECT COUNT(*) as c FROM matches WHERE division='BD'"
            ).fetchone()
            bd_with_result = conn.execute(
                "SELECT COUNT(*) as c FROM matches WHERE division='BD' AND ftr IS NOT NULL"
            ).fetchone()
            log(f"北单总比赛数: {bd_count['c']}")
            log(f"有比分结果:   {bd_with_result['c']}")

            imported = conn.execute(
                "SELECT COUNT(*) as c FROM import_log WHERE division='BD'"
            ).fetchone()
            log(f"已导入期数:   {imported['c']}")
        return 0

    target = EXPECTS_RECENT
    if args.recent:
        target = EXPECTS_RECENT[:args.recent]

    result = import_batch(expects=target, force=args.force, log_fn=log)
    log(f"\n数据库统计:")
    log(f"  北单总比赛: {result['total_bd_matches']}")
    log(f"  有比分结果: {result['total_bd_with_result']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
