"""历史数据模块测试：CSV 解析、数据库读写。"""

import os
import sqlite3
import tempfile
import unittest

from football_odds.history_csv import (
    _parse_date,
    parse_csv_rows,
    season_code_range,
)
from football_odds.history_db import (
    connect_history,
    count_matches,
    get_match_with_odds,
    init_history_db,
    insert_match,
    insert_odds_1x2,
    insert_odds_asian,
    insert_odds_ou25,
    is_imported,
    mark_imported,
    summary_stats,
)

SAMPLE_CSV = """\
Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR,B365H,B365D,B365A,PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,B365>2.5,B365<2.5,P>2.5,P<2.5,AHh,B365AHH,B365AHA,PAHH,PAHA,B365CH,B365CD,B365CA,PSCH,PSCD,PSCA
E0,15/08/2025,20:00,Liverpool,Bournemouth,4,2,H,1,0,H,19,10,10,3,7,10,6,7,1,2,0,0,1.3,6,8.5,1.28,6.56,9.07,1.34,6.5,9.5,1.31,5.96,8.31,1.36,3.2,1.37,3.26,-1.5,1.83,2.03,1.9,2.03,1.29,6.25,9,1.29,6.55,9.75
E0,16/08/2025,12:30,Aston Villa,Newcastle,0,0,D,0,0,D,3,16,3,3,13,11,3,6,1,1,1,0,2.25,3.5,2.9,2.24,3.72,3.13,2.38,3.75,3.1,2.3,3.56,2.94,1.62,2.3,1.65,2.33,-0.25,2,1.85,1.96,1.94,2.45,3.4,2.8,2.32,3.63,3.07
"""


class TestSeasonCodes(unittest.TestCase):
    def test_range_20(self):
        codes = season_code_range(20)
        self.assertEqual(len(codes), 20)
        self.assertEqual(codes[0], "2526")
        self.assertEqual(codes[19], "0607")

    def test_range_5(self):
        codes = season_code_range(5)
        self.assertEqual(len(codes), 5)
        self.assertEqual(codes[0], "2526")
        self.assertEqual(codes[4], "2122")


class TestParseDate(unittest.TestCase):
    def test_short_year(self):
        self.assertEqual(_parse_date("19/08/06"), "2006-08-19")

    def test_long_year(self):
        self.assertEqual(_parse_date("15/08/2025"), "2025-08-15")


class TestParseCsv(unittest.TestCase):
    def test_parse_sample(self):
        rows = parse_csv_rows(SAMPLE_CSV, "2526")
        self.assertEqual(len(rows), 2)

        r0 = rows[0]
        self.assertEqual(r0["home_team"], "Liverpool")
        self.assertEqual(r0["away_team"], "Bournemouth")
        self.assertEqual(r0["fthg"], 4)
        self.assertEqual(r0["ftag"], 2)
        self.assertEqual(r0["ftr"], "H")
        self.assertEqual(r0["match_date"], "2025-08-15")
        self.assertEqual(r0["season"], "2526")

        self.assertTrue(len(r0["odds_1x2"]) > 0)
        b365 = [o for o in r0["odds_1x2"] if o["bookmaker"] == "B365" and o["is_closing"] == 0]
        self.assertEqual(len(b365), 1)
        self.assertAlmostEqual(b365[0]["home"], 1.3)

        b365c = [o for o in r0["odds_1x2"] if o["bookmaker"] == "B365" and o["is_closing"] == 1]
        self.assertEqual(len(b365c), 1)
        self.assertAlmostEqual(b365c[0]["home"], 1.29)

        self.assertTrue(len(r0["odds_ou25"]) > 0)
        self.assertTrue(len(r0["odds_asian"]) > 0)

        ah = [o for o in r0["odds_asian"] if o["bookmaker"] == "B365" and o["is_closing"] == 0]
        self.assertEqual(len(ah), 1)
        self.assertAlmostEqual(ah[0]["handicap"], -1.5)


class TestHistoryDb(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self._tmp.close()
        os.environ["HISTORY_DB"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("HISTORY_DB", None)
        os.unlink(self._tmp.name)

    def test_insert_and_query(self):
        with connect_history() as conn:
            mid = insert_match(conn, {
                "division": "E0", "season": "2526",
                "match_date": "2025-08-15", "match_time": "20:00",
                "home_team": "Liverpool", "away_team": "Bournemouth",
                "fthg": 4, "ftag": 2, "ftr": "H",
                "hthg": 1, "htag": 0, "htr": "H",
                "referee": "A Taylor",
                "home_shots": 19, "away_shots": 10,
                "home_sot": 10, "away_sot": 3,
                "home_corners": 6, "away_corners": 7,
                "home_fouls": 7, "away_fouls": 10,
                "home_yellows": 1, "away_yellows": 2,
                "home_reds": 0, "away_reds": 0,
            })
            self.assertGreater(mid, 0)

            insert_odds_1x2(conn, mid, "B365", 0, 1.3, 6.0, 8.5)
            insert_odds_1x2(conn, mid, "B365", 1, 1.29, 6.25, 9.0)
            insert_odds_ou25(conn, mid, "B365", 0, 1.36, 3.2)
            insert_odds_asian(conn, mid, "B365", 0, -1.5, 1.83, 2.03)
            conn.commit()

            c = count_matches(conn, "E0", "2526")
            self.assertEqual(c, 1)

            m = get_match_with_odds(conn, mid)
            self.assertIsNotNone(m)
            self.assertEqual(m["home_team"], "Liverpool")
            self.assertEqual(len(m["odds_1x2"]), 2)
            self.assertEqual(len(m["odds_ou25"]), 1)
            self.assertEqual(len(m["odds_asian"]), 1)

    def test_import_log(self):
        with connect_history() as conn:
            self.assertFalse(is_imported(conn, "E0", "2526"))
            mark_imported(conn, "E0", "2526", 380)
            self.assertTrue(is_imported(conn, "E0", "2526"))

    def test_full_csv_import(self):
        rows = parse_csv_rows(SAMPLE_CSV, "2526")
        with connect_history() as conn:
            for match_data in rows:
                odds_1x2 = match_data.pop("odds_1x2", [])
                odds_ou25 = match_data.pop("odds_ou25", [])
                odds_asian = match_data.pop("odds_asian", [])
                mid = insert_match(conn, match_data)
                for od in odds_1x2:
                    insert_odds_1x2(conn, mid, od["bookmaker"], od["is_closing"],
                                    od.get("home"), od.get("draw"), od.get("away"))
                for od in odds_ou25:
                    insert_odds_ou25(conn, mid, od["bookmaker"], od["is_closing"],
                                      od.get("over"), od.get("under"))
                for od in odds_asian:
                    insert_odds_asian(conn, mid, od["bookmaker"], od["is_closing"],
                                       od.get("handicap"), od.get("home"), od.get("away"))
            conn.commit()

            stats = summary_stats(conn)
            self.assertEqual(stats["total_matches"], 2)
            self.assertGreater(stats["total_odds_records"], 0)


if __name__ == "__main__":
    unittest.main()
