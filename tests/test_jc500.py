"""500 竞彩 HTML 解析测试。"""

import unittest
from pathlib import Path

from football_odds.jc500 import parse_jc_html


class TestJc500Parse(unittest.TestCase):
    def test_parse_fixture(self) -> None:
        p = Path(__file__).resolve().parent / "fixtures" / "jc_one_row.html"
        html = p.read_text(encoding="utf-8")
        pairs = parse_jc_html(html)
        self.assertEqual(len(pairs), 2)
        m0, meta0 = pairs[0]
        self.assertIn("胜平负", m0.match_id)
        self.assertEqual(m0.home_team, "测试主队")
        self.assertEqual(m0.lines[0].home, 2.0)
        self.assertEqual(m0.lines[0].draw, 3.0)
        self.assertEqual(m0.lines[0].away, 4.0)
        self.assertEqual(meta0.league, "测试联赛")

        m1, _ = pairs[1]
        self.assertIn("让球", m1.match_id)
        self.assertEqual(m1.lines[0].home, 1.5)


if __name__ == "__main__":
    unittest.main()
