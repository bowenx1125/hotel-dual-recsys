from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import build_snapshot, eligible_hotels
from demo.scoring import all_policies, competition_aware_scores, is_finite


class TestScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = build_snapshot(ROOT)
        cls.cfg = cls.snap["config"]
        cls.hotel = eligible_hotels(cls.snap)[0]

    def test_reproducible(self):
        a = all_policies(self.hotel, self.cfg, 0.0)
        b = all_policies(self.hotel, self.cfg, 0.0)
        self.assertEqual(
            {k: v["chosen_aspect"] for k, v in a.items()},
            {k: v["chosen_aspect"] for k, v in b.items()},
        )

    def test_finite_scores(self):
        scores = competition_aware_scores(self.hotel, self.cfg, 0.3)
        self.assertTrue(scores)
        for a, s in scores.items():
            self.assertTrue(is_finite(s), msg=f"{a}={s}")

    def test_four_strategies(self):
        pol = all_policies(self.hotel, self.cfg, 0.0)
        self.assertEqual(set(pol), {"fix_weakest", "largest_peer_gap", "most_criticized", "competition_aware"})
        self.assertTrue(pol["competition_aware"].get("heuristic"))
