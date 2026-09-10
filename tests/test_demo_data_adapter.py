from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import build_snapshot, eligible_hotels


class TestDataAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = build_snapshot(ROOT)
        cls.hotels = eligible_hotels(cls.snap)

    def test_reads_real_tables(self):
        self.assertGreaterEqual(self.snap["n_hotels_in_aspect_table"], 24)
        self.assertGreaterEqual(self.snap["n_eligible_hotels"], 3)
        self.assertFalse(self.snap["synthetic"])

    def test_schema_and_finite_numbers(self):
        h = self.hotels[0]
        for key in ("hotel_id", "hotel_url", "compset_id", "n_reviews"):
            self.assertIn(key, h)
        for a, rec in h["aspects"].items():
            for k, v in rec.items():
                if isinstance(v, float):
                    self.assertTrue(math.isfinite(v), msg=f"{h['hotel_id']} {a} {k}={v}")

    def test_missing_optional_fields_do_not_crash(self):
        for h in self.hotels:
            self.assertIn("peer_count", h)
            self.assertTrue(h["compset_valid"])
            # price may be None
            self.assertTrue(h.get("price") is None or isinstance(h.get("price"), float))
