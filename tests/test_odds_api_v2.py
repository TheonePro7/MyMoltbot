"""The Odds API v2 增强版客户端测试。"""

import os
import tempfile
import unittest

from football_odds.odds_api_v2 import (
    _current_season,
    _extract_h2h,
    _extract_spreads,
    _extract_totals,
    store_events_to_db,
)
from football_odds.history_db import connect_history, count_matches


MOCK_EVENT = {
    "id": "test123",
    "sport_key": "soccer_epl",
    "home_team": "Liverpool",
    "away_team": "Arsenal",
    "commence_time": "2026-04-01T15:00:00Z",
    "bookmakers": [
        {
            "key": "pinnacle",
            "title": "Pinnacle",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Liverpool", "price": 2.10},
                        {"name": "Draw", "price": 3.50},
                        {"name": "Arsenal", "price": 3.40},
                    ],
                },
                {
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Liverpool", "price": 1.95, "point": -0.5},
                        {"name": "Arsenal", "price": 1.90, "point": 0.5},
                    ],
                },
                {
                    "key": "totals",
                    "outcomes": [
                        {"name": "Over", "price": 1.85, "point": 2.5},
                        {"name": "Under", "price": 2.00, "point": 2.5},
                    ],
                },
            ],
        },
        {
            "key": "bet365",
            "title": "Bet365",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Liverpool", "price": 2.05},
                        {"name": "Draw", "price": 3.60},
                        {"name": "Arsenal", "price": 3.50},
                    ],
                },
            ],
        },
    ],
}


class TestExtract(unittest.TestCase):
    def test_extract_h2h(self):
        bm = MOCK_EVENT["bookmakers"][0]
        h, d, a = _extract_h2h(bm, "Liverpool", "Arsenal")
        self.assertAlmostEqual(h, 2.10)
        self.assertAlmostEqual(d, 3.50)
        self.assertAlmostEqual(a, 3.40)

    def test_extract_spreads(self):
        bm = MOCK_EVENT["bookmakers"][0]
        handicap, h, a = _extract_spreads(bm, "Liverpool")
        self.assertAlmostEqual(handicap, -0.5)
        self.assertAlmostEqual(h, 1.95)
        self.assertAlmostEqual(a, 1.90)

    def test_extract_totals(self):
        bm = MOCK_EVENT["bookmakers"][0]
        line, ov, un = _extract_totals(bm)
        self.assertAlmostEqual(line, 2.5)
        self.assertAlmostEqual(ov, 1.85)
        self.assertAlmostEqual(un, 2.00)

    def test_no_market(self):
        bm = {"markets": []}
        self.assertEqual(_extract_h2h(bm, "A", "B"), (None, None, None))
        self.assertEqual(_extract_spreads(bm, "A"), (None, None, None))
        self.assertEqual(_extract_totals(bm), (None, None, None))


class TestStoreEvents(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self._tmp.close()
        os.environ["HISTORY_DB"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("HISTORY_DB", None)
        os.unlink(self._tmp.name)

    def test_store_mock_event(self):
        n = store_events_to_db([MOCK_EVENT], "soccer_epl")
        self.assertEqual(n, 1)

        with connect_history() as conn:
            c = count_matches(conn, "E0")
            self.assertEqual(c, 1)

            odds = conn.execute(
                "SELECT COUNT(*) as c FROM odds_1x2 WHERE match_id=1"
            ).fetchone()
            self.assertEqual(odds["c"], 2)

            ah = conn.execute(
                "SELECT COUNT(*) as c FROM odds_asian WHERE match_id=1"
            ).fetchone()
            self.assertEqual(ah["c"], 1)

            ou = conn.execute(
                "SELECT COUNT(*) as c FROM odds_ou25 WHERE match_id=1"
            ).fetchone()
            self.assertEqual(ou["c"], 1)


class TestCurrentSeason(unittest.TestCase):
    def test_returns_string(self):
        s = _current_season()
        self.assertEqual(len(s), 4)
        self.assertTrue(s.isdigit())


if __name__ == "__main__":
    unittest.main()
