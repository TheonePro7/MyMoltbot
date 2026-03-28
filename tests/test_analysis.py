"""赔率分析单元测试（标准库 unittest）。"""

import json
import tempfile
import unittest
from pathlib import Path

from football_odds.analysis import (
    compare_bookmakers,
    implied_probabilities,
    load_matches_from_json,
    overround,
    remove_margin_proportional,
)
from football_odds.models import BookmakerLine, MatchOdds


class TestImpliedAndMargin(unittest.TestCase):
    def test_implied_and_overround(self) -> None:
        imp = implied_probabilities(2.0, 3.0, 6.0)
        self.assertAlmostEqual(imp["home"], 0.5)
        self.assertAlmostEqual(imp["draw"], 1.0 / 3.0)
        self.assertAlmostEqual(imp["away"], 1.0 / 6.0)
        ov = overround(imp)
        self.assertAlmostEqual(ov, 0.0)

    def test_remove_margin_proportional(self) -> None:
        imp = implied_probabilities(2.0, 3.0, 3.0)
        fair = remove_margin_proportional(imp)
        s = fair["home"] + fair["draw"] + fair["away"]
        self.assertAlmostEqual(s, 1.0)


class TestCompare(unittest.TestCase):
    def test_compare_bookmakers(self) -> None:
        m = MatchOdds(
            match_id="t1",
            home_team="H",
            away_team="A",
            lines=(
                BookmakerLine("b1", 2.0, 3.0, 4.0),
                BookmakerLine("b2", 2.2, 3.0, 4.0),
            ),
        )
        r = compare_bookmakers(m)
        self.assertEqual(r["best_odds_bookmaker"]["home"], "b2")


class TestLoadJson(unittest.TestCase):
    def test_load_matches_from_json(self) -> None:
        data = [
            {
                "match_id": "x",
                "home_team": "h",
                "away_team": "a",
                "lines": [{"bookmaker": "b", "home": 2.0, "draw": 3.0, "away": 4.0}],
            }
        ]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            ms = load_matches_from_json(p)
            self.assertEqual(len(ms), 1)
            self.assertEqual(ms[0].lines[0].bookmaker, "b")


if __name__ == "__main__":
    unittest.main()
