from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_recommendations import (  # noqa: E402
    STRATEGIES,
    evaluate_file,
    evaluate_snapshot,
    sha256_json,
)


ACTIONABILITY = {
    "aspects": {
        "location": {"eligible_for_direct_action": False},
        "cleanliness": {"eligible_for_direct_action": True},
        "breakfast": {"eligible_for_direct_action": True},
        # This explicit false entry checks configuration-driven constraints in
        # addition to the fixed location rule.
        "service": {"eligible_for_direct_action": False},
    }
}

CFG = {
    "aspects": ["location", "cleanliness", "breakfast", "service"],
    "min_mentions": 5,
    "min_reliability": 0.3,
    "policy_version": "synthetic-policy-v1",
    "actionability": ACTIONABILITY,
}


def _aspect(net: float | None, mentions: int = 10, rel: float = 0.5) -> dict[str, Any]:
    return {
        "net": net,
        "mention_count": mentions,
        "reliability": rel,
    }


def _hotel(
    hotel_id: str,
    city: str,
    *,
    eligible: bool = True,
    low_breakfast: bool = False,
    missing_service: bool = False,
) -> dict[str, Any]:
    aspects = {
        "location": _aspect(-0.8),
        "cleanliness": _aspect(-0.2),
        "breakfast": _aspect(-0.4, mentions=2 if low_breakfast else 10, rel=0.1 if low_breakfast else 0.5),
        "service": _aspect(-0.1),
    }
    if missing_service:
        del aspects["service"]
    return {
        "hotel_id": hotel_id,
        "city": city,
        "eligible": eligible,
        "aspects": aspects,
    }


def _snapshot() -> dict[str, Any]:
    return {
        "schema_version": "synthetic-snapshot-v1",
        "synthetic": True,
        "config": CFG,
        "hotels": [
            _hotel("h1", "A"),
            # Missing one policy key and an explicit abstention exercise both
            # missing output and abstention accounting.
            _hotel("h2", "A", missing_service=True),
            _hotel("h3", "B"),
            _hotel("h4", "B", eligible=False),
            _hotel("h5", "B", low_breakfast=True),
        ],
    }


def _fake_all_policies(hotel: dict, cfg: dict, assumed_intensity: float = 0.0) -> dict[str, dict[str, Any]]:
    del cfg, assumed_intensity
    choices = {
        "h1": {
            "fix_weakest": "cleanliness",
            "largest_peer_gap": "cleanliness",
            "most_criticized": "breakfast",
            "peer_relative": "cleanliness",
        },
        "h2": {
            "fix_weakest": "cleanliness",
            # Deliberately absent from the returned mapping.
            "most_criticized": "cleanliness",
            "peer_relative": None,
        },
        "h3": {
            "fix_weakest": "cleanliness",
            "largest_peer_gap": "service",
            "most_criticized": "location",
            "peer_relative": "service",
        },
        "h5": {
            "fix_weakest": "breakfast",
            "largest_peer_gap": "breakfast",
            "most_criticized": "cleanliness",
            "peer_relative": "breakfast",
        },
    }[hotel["hotel_id"]]
    output: dict[str, dict[str, Any]] = {}
    for strategy, choice in choices.items():
        payload: dict[str, Any] = {
            "chosen_aspect": choice,
            # This NaN is intentionally kept out of the evaluator report; the
            # writer must still guarantee valid JSON if a scorer emits one.
            "score_table": {"synthetic": math.nan},
        }
        if choice is None:
            payload["abstention_reason"] = "insufficient evidence"
        output[strategy] = payload
    return output


class TestPolicyEvaluation(unittest.TestCase):
    def test_counts_constraints_city_coverage_and_common_denominator(self) -> None:
        result = evaluate_snapshot(_snapshot(), scorer=_fake_all_policies)

        self.assertEqual(result["population"], {"all_hotel_count": 5, "eligible_hotel_count": 4})
        self.assertTrue(result["descriptive_only"])
        self.assertEqual(result["evidence_level"], "DESCRIPTIVE")
        self.assertEqual(result["thresholds"], {"min_mentions": 5, "min_reliability": 0.3})

        fix = result["strategies"]["fix_weakest"]
        self.assertEqual(fix["all_hotel_count"], 5)
        self.assertEqual(fix["eligible_hotel_count"], 4)
        self.assertEqual(fix["recommendation_count"], 4)
        self.assertEqual(fix["abstention_count"], 0)
        self.assertEqual(fix["choice_counts"], {"breakfast": 1, "cleanliness": 3})
        self.assertEqual(fix["checks"]["low_evidence_choice_count"], 1)

        largest = result["strategies"]["largest_peer_gap"]
        self.assertEqual(largest["recommendation_count"], 3)
        self.assertEqual(largest["abstention_count"], 1)
        self.assertEqual(largest["abstention_reasons"], {"missing_policy_output": 1})
        self.assertEqual(largest["checks"]["non_actionable_choice_count"], 1)
        self.assertEqual(largest["checks"]["low_evidence_choice_count"], 1)
        self.assertAlmostEqual(largest["coverage"], 3 / 4)
        self.assertEqual(largest["by_city"]["A"]["recommendation_count"], 1)
        self.assertEqual(largest["by_city"]["A"]["abstention_count"], 1)
        self.assertAlmostEqual(largest["by_city"]["A"]["coverage"], 1 / 2)
        self.assertEqual(largest["by_city"]["B"]["all_hotel_count"], 3)
        self.assertEqual(largest["by_city"]["B"]["eligible_hotel_count"], 2)
        self.assertEqual(largest["by_city"]["B"]["recommendation_count"], 2)
        self.assertAlmostEqual(largest["by_city"]["B"]["coverage"], 1.0)

        most = result["strategies"]["most_criticized"]
        self.assertEqual(most["recommendation_count"], 4)
        self.assertEqual(most["abstention_count"], 0)
        self.assertEqual(most["checks"]["non_actionable_choice_count"], 1)
        self.assertEqual(most["checks"]["low_evidence_choice_count"], 0)

        peer = result["strategies"]["peer_relative"]
        self.assertEqual(peer["recommendation_count"], 3)
        self.assertEqual(peer["abstention_count"], 1)
        self.assertEqual(peer["checks"]["non_actionable_choice_count"], 1)
        self.assertEqual(peer["checks"]["low_evidence_choice_count"], 1)

        common = result["common_comparison"]
        self.assertEqual(common["hotel_count"], 3)
        self.assertEqual(common["hotel_ids"], ["h1", "h3", "h5"])
        for pair in common["pairwise"].values():
            self.assertEqual(pair["denominator"], 3)
            self.assertEqual(pair["agreement_count"] + pair["disagreement_count"], 3)
            self.assertAlmostEqual(pair["agreement_rate"] + pair["disagreement_rate"], 1.0)

    def test_missing_net_and_empty_common_set_are_explicit(self) -> None:
        snapshot = {
            "config": {"actionability": ACTIONABILITY},
            "hotels": [{
                "hotel_id": "empty",
                "city": "A",
                "eligible": True,
                "aspects": {"cleanliness": {"net": None, "mention_count": 0, "reliability": None}},
            }],
        }

        def abstaining_scorer(hotel: dict, cfg: dict, intensity: float) -> dict[str, dict[str, Any]]:
            del hotel, cfg, intensity
            return {
                strategy: {"chosen_aspect": None, "abstention_reason": "missing net"}
                for strategy in STRATEGIES
            }

        result = evaluate_snapshot(snapshot, scorer=abstaining_scorer)
        self.assertEqual(result["population"]["all_hotel_count"], 1)
        for strategy in STRATEGIES:
            stats = result["strategies"][strategy]
            self.assertEqual(stats["recommendation_count"], 0)
            self.assertEqual(stats["abstention_count"], 1)
            self.assertEqual(stats["coverage"], 0.0)
        self.assertEqual(result["common_comparison"]["hotel_count"], 0)
        for pair in result["common_comparison"]["pairwise"].values():
            self.assertIsNone(pair["agreement_rate"])
            self.assertIsNone(pair["disagreement_rate"])

    def test_missing_actionability_is_reported_as_unknown(self) -> None:
        snapshot = _snapshot()
        snapshot["config"] = {
            key: value for key, value in snapshot["config"].items() if key != "actionability"
        }
        result = evaluate_snapshot(snapshot, scorer=_fake_all_policies)

        self.assertEqual(
            result["actionability_audit"]["configured_aspects_without_metadata"],
            ["breakfast", "cleanliness", "service"],
        )
        self.assertGreater(result["actionability_audit"]["unknown_selected_choice_count"], 0)
        self.assertGreater(
            result["strategies"]["fix_weakest"]["checks"]["unknown_actionability_choice_count"],
            0,
        )
        # Location remains explicitly non-actionable even when the rest of the
        # configuration is unavailable.
        self.assertEqual(
            result["strategies"]["most_criticized"]["checks"]["non_actionable_choice_count"],
            1,
        )

    def test_duplicate_hotel_ids_are_rejected(self) -> None:
        snapshot = _snapshot()
        snapshot["hotels"].append(_hotel("h1", "C"))
        with self.assertRaisesRegex(ValueError, "duplicate hotel_id"):
            evaluate_snapshot(snapshot, scorer=_fake_all_policies)

    def test_input_output_alias_and_broken_symlink_guards(self) -> None:
        snapshot = _snapshot()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "research_snapshot.json"
            output = root / "policy_evaluation.json"
            source.write_text(json.dumps(snapshot), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "output path"):
                evaluate_file(source, source, overwrite=True, scorer=_fake_all_policies)

            alias = root / "snapshot-alias.json"
            alias.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "output path"):
                evaluate_file(source, alias, overwrite=True, scorer=_fake_all_policies)

            hardlink = root / "hardlink-output.json"
            os.link(source, hardlink)
            with self.assertRaisesRegex(ValueError, "output path"):
                evaluate_file(source, hardlink, overwrite=True, scorer=_fake_all_policies)

            broken = root / "dangling-output.json"
            broken.symlink_to(root / "missing-target.json")
            with self.assertRaises(FileExistsError):
                evaluate_file(source, broken, scorer=_fake_all_policies)
            self.assertTrue(broken.is_symlink())

            # Explicit overwrite publishes atomically and replaces only the
            # dangling output link, while the input remains intact.
            evaluate_file(source, broken, overwrite=True, scorer=_fake_all_policies)
            self.assertFalse(broken.is_symlink())
            self.assertEqual(json.loads(broken.read_text(encoding="utf-8"))["population"]["all_hotel_count"], 5)
            self.assertTrue(source.is_file())

    def test_repeatable_hashes_and_strict_no_overwrite_with_valid_json(self) -> None:
        snapshot = _snapshot()
        first = evaluate_snapshot(snapshot, scorer=_fake_all_policies)
        second = evaluate_snapshot(json.loads(json.dumps(snapshot)), scorer=_fake_all_policies)
        self.assertEqual(first, second)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "research_snapshot.json"
            output = root / "policy_evaluation.json"
            source.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            result = evaluate_file(source, output, scorer=_fake_all_policies)
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(result["input_sha256"], source_hash)
            self.assertEqual(result["config_sha256"], sha256_json(CFG))
            before = output.read_bytes()
            self.assertNotIn(b"NaN", before)
            json.loads(before)

            with self.assertRaises(FileExistsError):
                evaluate_file(source, output, scorer=_fake_all_policies)
            self.assertEqual(output.read_bytes(), before)

            evaluate_file(source, output, overwrite=True, scorer=_fake_all_policies)
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
