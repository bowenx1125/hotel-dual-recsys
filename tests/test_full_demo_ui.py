#!/usr/bin/env python3
"""Synthetic unit tests for full-research demo UI helpers (FYP-NIGHT-005 C)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo import en, zh_cn
from demo.app import (
    MGR_HOTEL_KEY,
    count_aspects_with_peer_references,
    count_aspects_with_review_evidence,
    hotel_display_labels,
    hydrate_hotel_selection,
)
from demo.config import load_config


def _synthetic_hotel(
    hotel_id: str = "hotel-a",
    hotel_name: str = "Alpha Hotel",
    peer_count: int = 3,
) -> dict:
    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "city": "Brussels",
        "compset_id": "geo:Brussels",
        "compset_valid": True,
        "peer_count": peer_count,
        "n_reviews": 42,
        "aspects": {
            "cleanliness": {
                "has_measurement": True,
                "mention_count": 8,
                "net": -0.2,
                "reliability": 0.44,
                "peer_n": 3,
            },
            "service": {
                "has_measurement": True,
                "mention_count": 3,
                "net": 0.1,
                "reliability": 0.23,
                "peer_n": 2,
            },
            "location": {
                "has_measurement": False,
                "mention_count": None,
                "net": None,
                "reliability": None,
                "peer_n": 0,
            },
        },
    }


class TestHotelSelectionHelpers(unittest.TestCase):
    def test_duplicate_names_get_short_id_suffix(self):
        hotels = [
            {"hotel_id": "long-id-alpha-001", "hotel_name": "Grand Hotel"},
            {"hotel_id": "long-id-beta-002", "hotel_name": "Grand Hotel"},
            {"hotel_id": "solo-003", "hotel_name": "Solo Inn"},
        ]
        labels = hotel_display_labels(hotels)
        self.assertEqual(labels["long-id-alpha-001"], "Grand Hotel (lpha-001)")
        self.assertEqual(labels["long-id-beta-002"], "Grand Hotel (beta-002)")
        self.assertEqual(labels["solo-003"], "Solo Inn")

    def test_hydrate_hotel_selection_preserves_valid_id(self):
        state = {MGR_HOTEL_KEY: "hotel-b"}
        hid = hydrate_hotel_selection(state, ["hotel-a", "hotel-b"], "hotel-a")
        self.assertEqual(hid, "hotel-b")
        self.assertEqual(state[MGR_HOTEL_KEY], "hotel-b")

    def test_hydrate_hotel_selection_resets_invalid_id(self):
        state = {MGR_HOTEL_KEY: "missing"}
        hid = hydrate_hotel_selection(state, ["hotel-a", "hotel-b"], "hotel-b")
        self.assertEqual(hid, "hotel-b")
        self.assertEqual(state[MGR_HOTEL_KEY], "hotel-b")


class TestAspectEvidenceCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = {
            **load_config(),
            "min_mentions": 5,
            "min_reliability": 0.3,
            "min_measured_peers": 2,
            "aspects": ["cleanliness", "service", "location"],
        }

    def test_review_evidence_counts_measured_aspects_only(self):
        hotel = _synthetic_hotel()
        self.assertEqual(count_aspects_with_review_evidence(hotel, self.cfg), 1)

    def test_peer_reference_counts_require_peer_n(self):
        hotel = _synthetic_hotel()
        self.assertEqual(count_aspects_with_peer_references(hotel, self.cfg), 1)


class TestLocaleHelpers(unittest.TestCase):
    def test_ineligible_reason_labels_match_across_locales(self):
        for reason in ("peer_count<2", "n_reviews<10", "compset_valid=0"):
            self.assertTrue(zh_cn.ineligible_reason_label(reason))
            self.assertTrue(en.ineligible_reason_label(reason))

    def test_excluded_aspect_reasons_format(self):
        excluded = [{"aspect": "service", "reason": "mention_count<5"}]
        zh_out = zh_cn.format_excluded_aspect_reasons(excluded, zh_cn.aspect_label)
        en_out = en.format_excluded_aspect_reasons(excluded, en.aspect_label)
        self.assertIn("服务", zh_out)
        self.assertIn("Service", en_out)


if __name__ == "__main__":
    unittest.main()
