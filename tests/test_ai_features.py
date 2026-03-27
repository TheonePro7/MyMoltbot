"""AI 特征工程和模型测试。"""

import os
import tempfile
import unittest

import numpy as np
import pandas as pd

from ai.features import _implied_prob, _fair_prob, compute_features, get_feature_columns


class TestImpliedProb(unittest.TestCase):
    def test_normal(self):
        self.assertAlmostEqual(_implied_prob(2.0), 0.5)
        self.assertAlmostEqual(_implied_prob(4.0), 0.25)

    def test_invalid(self):
        self.assertTrue(np.isnan(_implied_prob(1.0)))
        self.assertTrue(np.isnan(_implied_prob(0.5)))
        self.assertTrue(np.isnan(_implied_prob(None)))


class TestFairProb(unittest.TestCase):
    def test_fair(self):
        h, d, a = _fair_prob(0.5, 0.3, 0.28)
        self.assertAlmostEqual(h + d + a, 1.0, places=5)


class TestComputeFeatures(unittest.TestCase):
    def test_basic_features(self):
        df = pd.DataFrame({
            "match_id": [1, 2],
            "division": ["E0", "E0"],
            "season": ["2526", "2526"],
            "match_date": ["2025-08-15", "2025-08-16"],
            "home_team": ["A", "C"],
            "away_team": ["B", "D"],
            "fthg": [2, 1],
            "ftag": [1, 1],
            "ftr": ["H", "D"],
            "home_b365_open": [1.8, 2.5],
            "draw_b365_open": [3.5, 3.3],
            "away_b365_open": [4.0, 2.8],
        })
        result = compute_features(df)
        self.assertIn("ip_home_b365", result.columns)
        self.assertIn("fp_home_b365", result.columns)
        self.assertIn("overround_b365", result.columns)
        self.assertIn("target", result.columns)
        self.assertEqual(result.iloc[0]["target"], 0)
        self.assertEqual(result.iloc[1]["target"], 1)

    def test_feature_columns(self):
        df = pd.DataFrame({
            "match_id": [1],
            "division": ["E0"],
            "season": ["2526"],
            "match_date": ["2025-08-15"],
            "home_team": ["A"],
            "away_team": ["B"],
            "fthg": [2],
            "ftag": [1],
            "ftr": ["H"],
            "home_b365_open": [1.8],
            "draw_b365_open": [3.5],
            "away_b365_open": [4.0],
            "target": [0],
            "ip_home_b365": [0.556],
            "div_encoded": [0],
        })
        cols = get_feature_columns(df)
        self.assertNotIn("match_id", cols)
        self.assertNotIn("target", cols)
        self.assertNotIn("fthg", cols)
        self.assertIn("home_b365_open", cols)
        self.assertIn("ip_home_b365", cols)


if __name__ == "__main__":
    unittest.main()
