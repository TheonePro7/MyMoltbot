"""组合过关与结算单元测试。"""

import unittest

from football_odds.parlay import (
    actual_outcome_nspf,
    actual_outcome_spf,
    build_subbet_lines,
    generate_subbet_index_sets,
    settle_lines,
)


class TestParlay(unittest.TestCase):
    def test_2串3_no_dan(self) -> None:
        s = generate_subbet_index_sets(2, ["2串3"], set())
        self.assertEqual(len(s), 3)

    def test_2串1_with_dan(self) -> None:
        s = generate_subbet_index_sets(2, ["2串1"], {0})
        self.assertEqual(s, [frozenset({0, 1})])

    def test_build_and_settle(self) -> None:
        selections = [
            {
                "selection_id": "a-nspf-3",
                "fixture_id": "a",
                "market": "nspf",
                "handicap": "",
                "outcome": "3",
                "odds": 2.0,
                "matchnum": "M1",
            },
            {
                "selection_id": "b-nspf-1",
                "fixture_id": "b",
                "market": "nspf",
                "handicap": "",
                "outcome": "1",
                "odds": 3.0,
                "matchnum": "M2",
            },
        ]
        lines = build_subbet_lines(selections, ["2串1"], set())
        self.assertEqual(len(lines), 1)
        res = {"a": (2, 1), "b": (0, 0)}
        settled, payout, profit = settle_lines(lines, res, stake_per_line=2.0, multiplier=1)
        self.assertTrue(settled[0]["won"])
        # 每子注本金 2 元，赔率积 2*3=6，命中返还 2*6=12
        self.assertAlmostEqual(payout, 12.0)
        self.assertAlmostEqual(profit, 10.0)

    def test_outcome_spf(self) -> None:
        self.assertEqual(actual_outcome_nspf(2, 1), "3")
        # 主让 1 球：主队 3:1 → 有效 2:1 主胜
        self.assertEqual(actual_outcome_spf(3, 1, "-1"), "3")


if __name__ == "__main__":
    unittest.main()
