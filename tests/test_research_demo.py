"""Tests for panel_adapter and build_research_demo CLI."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from src.recommendation.panel_adapter import (  # noqa: E402
    build_panel_snapshot,
    complete_periods,
    resolve_period,
    validate_panel,
    validate_period_label,
)


CFG = {
    "aspects": ["location", "cleanliness", "breakfast", "service", "noise", "room", "value"],
    "min_mentions": 5,
    "min_reviews_hotel": 10,
    "min_reliability": 0.3,
    "reliability_k": 10.0,
    "weights": {"gap": 0.45, "criticism": 0.35, "unreliable": 0.20},
    "policy_version": "panel_adapter_v1",
}

INLINE_ACTIONABILITY = {
    aspect: {
        "eligible_for_direct_action": aspect != "location",
        "actionability_level": "immutable" if aspect == "location" else "high",
    }
    for aspect in CFG["aspects"]
}

CFG_WITH_INLINE_ACTIONABILITY = {**CFG, "actionability": INLINE_ACTIONABILITY}


def _panel_row(
    *,
    hotel_id: str,
    hotel_name: str,
    city: str,
    period: str,
    period_complete: bool,
    aspect: str,
    pos: int,
    neg: int,
    has_measurement: bool | None = None,
    lat: float = 51.5,
    lon: float = -0.1,
    total_reviews: int = 20,
    smoothed_net: float = 0.2,
    reliability: float = 0.6,
) -> dict:
    tot = pos + neg
    if has_measurement is None:
        has_measurement = tot > 0
    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "city": city,
        "country": "Testland",
        "latitude": lat,
        "longitude": lon,
        "period": period,
        "period_complete": period_complete,
        "aspect": aspect,
        "positive_mentions": pos,
        "negative_mentions": neg,
        "total_mentions": tot,
        "has_measurement": has_measurement,
        "raw_net": (pos - neg) / tot if tot else float("nan"),
        "smoothed_net": smoothed_net if has_measurement else float("nan"),
        "measurement_reliability": reliability if has_measurement else 0.0,
        "total_reviews": total_reviews,
        "mean_reviewer_score": 8.0,
        "prior_strength": 10.0,
    }


def _hotel_block(
    hotel_id: str,
    *,
    city: str,
    period: str,
    period_complete: bool,
    pos: int = 8,
    neg: int = 2,
    total_reviews: int = 20,
    lat: float = 51.5,
    lon: float = -0.1,
) -> list[dict]:
    rows = []
    for aspect in CFG["aspects"]:
        rows.append(
            _panel_row(
                hotel_id=hotel_id,
                hotel_name=f"Hotel {hotel_id}",
                city=city,
                period=period,
                period_complete=period_complete,
                aspect=aspect,
                pos=pos,
                neg=neg,
                lat=lat,
                lon=lon,
                total_reviews=total_reviews,
            )
        )
    return rows


def _peers(rows: list[dict]) -> "pd.DataFrame":
    return pd.DataFrame(rows)


@unittest.skipUnless(HAS_PANDAS, "pandas not available")
class TestPanelAdapter(unittest.TestCase):
    def _build_fixture(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        rows: list[dict] = []
        rows.extend(_hotel_block("h1", city="Alpha", period="2020Q1", period_complete=True))
        rows.extend(_hotel_block("h2", city="Alpha", period="2020Q1", period_complete=True))
        rows.extend(_hotel_block("h3", city="Alpha", period="2020Q1", period_complete=True))
        rows.extend(_hotel_block("h1", city="Alpha", period="2020Q2", period_complete=False))
        rows.extend(_hotel_block("h2", city="Alpha", period="2020Q2", period_complete=False))
        rows.extend(_hotel_block("h1", city="Alpha", period="2020Q3", period_complete=True, pos=10, neg=0))
        rows.extend(_hotel_block("h2", city="Alpha", period="2020Q3", period_complete=True))
        rows.extend(_hotel_block("h4", city="Beta", period="2020Q3", period_complete=True))
        rows.extend(_hotel_block("h5", city="Beta", period="2020Q3", period_complete=True, total_reviews=5))
        rows.extend(
            _hotel_block(
                "h6",
                city="Beta",
                period="2020Q3",
                period_complete=True,
                lat=float("nan"),
                lon=float("nan"),
            )
        )
        no_meas_rows = [
            _panel_row(
                hotel_id="h7",
                hotel_name="Hotel h7",
                city="Beta",
                period="2020Q3",
                period_complete=True,
                aspect=aspect,
                pos=0,
                neg=0,
                has_measurement=False,
                total_reviews=20,
            )
            for aspect in CFG["aspects"]
        ]
        rows.extend(no_meas_rows)

        panel = pd.DataFrame(rows)
        peers = _peers([
            {"hotel_id": "h1", "peer_hotel_id": "h2", "city": "Alpha", "rank": 1, "distance_km": 0.5},
            {"hotel_id": "h1", "peer_hotel_id": "h3", "city": "Alpha", "rank": 2, "distance_km": 0.8},
            {"hotel_id": "h2", "peer_hotel_id": "h1", "city": "Alpha", "rank": 1, "distance_km": 0.5},
            {"hotel_id": "h2", "peer_hotel_id": "h3", "city": "Alpha", "rank": 2, "distance_km": 0.7},
            {"hotel_id": "h4", "peer_hotel_id": "h5", "city": "Beta", "rank": 1, "distance_km": 1.0},
            {"hotel_id": "h5", "peer_hotel_id": "h4", "city": "Beta", "rank": 1, "distance_km": 1.0},
            {"hotel_id": "h7", "peer_hotel_id": "h4", "city": "Beta", "rank": 1, "distance_km": 2.0},
            {"hotel_id": "h7", "peer_hotel_id": "h5", "city": "Beta", "rank": 2, "distance_km": 2.5},
        ])
        return panel, peers

    def test_latest_complete_period_default(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            source_metadata={"synthetic": True, "dataset_id": "test-fixture"},
        )
        self.assertEqual(snap["period"], "2020Q3")
        self.assertTrue(snap["synthetic"])

    def test_synthetic_unknown_when_not_provided(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(panel, peers, CFG)
        self.assertIsNone(snap["synthetic"])

    def test_reject_partial_requested_period(self):
        panel, peers = self._build_fixture()
        with self.assertRaises(ValueError):
            build_panel_snapshot(panel, peers, CFG, period="2020Q2")

    def test_no_future_period_data_in_snapshot(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q1",
            source_metadata={"synthetic": True},
        )
        self.assertEqual(snap["period"], "2020Q1")
        ids = {h["hotel_id"] for h in snap["hotels"]}
        self.assertEqual(ids, {"h1", "h2", "h3"})

    def test_source_panel_coverage_fields(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q3",
            source_metadata={"synthetic": True},
        )
        self.assertEqual(snap["n_hotels_source_panel"], 7)
        self.assertEqual(snap["n_hotels_total"], 6)
        self.assertEqual(snap["absent_selected_period_count"], 1)
        self.assertEqual(snap["absent_selected_period_hotel_ids"], ["h3"])
        self.assertEqual(snap["thresholds"]["min_reviews_hotel"], 10)
        self.assertEqual(snap["scoring_version"], "panel_adapter_v1")

    def test_all_hotels_accounted_with_reasons(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q3",
            source_metadata={"synthetic": True},
        )
        self.assertEqual(snap["n_hotels_total"], len(snap["hotels"]))
        self.assertEqual(
            snap["n_eligible_hotels"] + snap["n_excluded_hotels"],
            snap["n_hotels_total"],
        )
        by_id = {h["hotel_id"]: h for h in snap["hotels"]}
        self.assertFalse(by_id["h5"]["eligible"])
        self.assertIn("n_reviews<10", by_id["h5"]["ineligible_reason"])
        self.assertFalse(by_id["h6"]["eligible"])
        self.assertEqual(by_id["h6"]["ineligible_reason"], "missing_coordinates")
        self.assertFalse(by_id["h7"]["eligible"])
        self.assertEqual(by_id["h7"]["ineligible_reason"], "no_measured_aspects")

    def test_out_of_range_coordinates_marked_invalid(self):
        panel, peers = self._build_fixture()
        bad_rows = _hotel_block(
            "h8",
            city="Beta",
            period="2020Q3",
            period_complete=True,
            lat=95.0,
            lon=10.0,
        )
        panel = pd.concat([panel, pd.DataFrame(bad_rows)], ignore_index=True)
        peers = pd.concat(
            [
                peers,
                pd.DataFrame([
                    {"hotel_id": "h8", "peer_hotel_id": "h4", "city": "Beta", "rank": 1, "distance_km": 1.0},
                    {"hotel_id": "h8", "peer_hotel_id": "h5", "city": "Beta", "rank": 2, "distance_km": 1.2},
                ]),
            ],
            ignore_index=True,
        )
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q3",
            source_metadata={"synthetic": True},
        )
        h8 = next(h for h in snap["hotels"] if h["hotel_id"] == "h8")
        self.assertFalse(h8["compset_valid"])
        self.assertIsNone(h8["lat"])
        self.assertIsNone(h8["lon"])

    def test_peer_absent_from_selected_period_excluded(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q1",
            source_metadata={"synthetic": True},
        )
        h1 = next(h for h in snap["hotels"] if h["hotel_id"] == "h1")
        self.assertEqual(set(h1["peer_ids"]), {"h2", "h3"})
        self.assertEqual(h1["peer_count"], 2)

    def test_peers_removed_absent_period_count(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q3",
            source_metadata={"synthetic": True},
        )
        self.assertGreaterEqual(snap["peers_removed_absent_period"], 1)

    def test_measured_peers_only_for_peer_median(self):
        panel, peers = self._build_fixture()
        low_rel_rows = []
        for aspect in CFG["aspects"]:
            low_rel_rows.append(
                _panel_row(
                    hotel_id="h3",
                    hotel_name="Hotel h3",
                    city="Alpha",
                    period="2020Q1",
                    period_complete=True,
                    aspect=aspect,
                    pos=1,
                    neg=0,
                    reliability=0.1,
                )
            )
        panel = pd.concat([self._build_fixture()[0], pd.DataFrame(low_rel_rows)]).drop_duplicates(
            subset=["hotel_id", "aspect", "period"], keep="last"
        )
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q1",
            source_metadata={"synthetic": True},
        )
        h1 = next(h for h in snap["hotels"] if h["hotel_id"] == "h1")
        rec = h1["aspects"]["location"]
        self.assertEqual(rec["peer_n"], 1)
        self.assertIsNotNone(rec["peer_median_net"])

    def test_no_measurement_null_nets_and_rates(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q3",
            source_metadata={"synthetic": True},
        )
        h7 = next(h for h in snap["hotels"] if h["hotel_id"] == "h7")
        loc = h7["aspects"]["location"]
        self.assertFalse(loc["has_measurement"])
        self.assertIsNone(loc["net"])
        self.assertIsNone(loc["neg_rate"])
        self.assertIsNone(loc["mention_rate"])

    def test_duplicate_panel_rows_rejected(self):
        panel, peers = self._build_fixture()
        dup = panel.iloc[[0]].copy()
        bad = pd.concat([panel, dup], ignore_index=True)
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])

    def test_count_validation_rejects_bool_fraction_inf(self):
        panel, _ = self._build_fixture()
        bad = panel.copy()
        bad["positive_mentions"] = bad["positive_mentions"].astype(object)
        bad.loc[0, "positive_mentions"] = True
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])
        bad = panel.copy()
        bad["total_reviews"] = bad["total_reviews"].astype(float)
        bad.loc[0, "total_reviews"] = 1.5
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])
        bad = panel.copy()
        bad["negative_mentions"] = bad["negative_mentions"].astype(object)
        bad.loc[0, "negative_mentions"] = float("inf")
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])

    def test_measured_net_and_reliability_ranges_rejected(self):
        panel, _ = self._build_fixture()
        bad = panel.copy()
        bad.loc[0, "smoothed_net"] = 1.5
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])
        bad = panel.copy()
        bad.loc[0, "measurement_reliability"] = -0.1
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])

    def test_mentions_may_exceed_total_reviews(self):
        panel, peers = self._build_fixture()
        rows = _hotel_block("hx", city="Gamma", period="2021Q1", period_complete=True, total_reviews=5)
        for row in rows:
            row["positive_mentions"] = 6
            row["negative_mentions"] = 4
            row["total_mentions"] = 10
        panel = pd.DataFrame(rows)
        peers = _peers([
            {"hotel_id": "hx", "peer_hotel_id": "hy", "city": "Gamma", "rank": 1, "distance_km": 0.5},
            {"hotel_id": "hy", "peer_hotel_id": "hx", "city": "Gamma", "rank": 1, "distance_km": 0.5},
        ])
        rows_hy = _hotel_block("hy", city="Gamma", period="2021Q1", period_complete=True)
        panel = pd.concat([panel, pd.DataFrame(rows_hy)], ignore_index=True)
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2021Q1",
            source_metadata={"synthetic": True},
        )
        self.assertEqual(snap["n_hotels_total"], 2)

    def test_period_label_validation(self):
        with self.assertRaises(ValueError):
            validate_period_label("2020Q5")
        with self.assertRaises(ValueError):
            validate_period_label("20Q1")

    def test_complete_period_conflicting_flags_raise(self):
        panel, _ = self._build_fixture()
        conflict = panel.copy()
        conflict.loc[
            (conflict["period"] == "2020Q1") & (conflict["hotel_id"] == "h2"),
            "period_complete",
        ] = False
        with self.assertRaises(ValueError):
            complete_periods(conflict)

    def test_self_peer_edges_rejected(self):
        panel, peers = self._build_fixture()
        bad_peers = peers.copy()
        bad_peers.loc[0, "peer_hotel_id"] = bad_peers.loc[0, "hotel_id"]
        with self.assertRaises(ValueError):
            build_panel_snapshot(
                panel,
                bad_peers,
                CFG,
                period="2020Q1",
                source_metadata={"synthetic": True},
            )

    def test_cross_city_peer_edges_rejected(self):
        panel, peers = self._build_fixture()
        bad_peers = peers.copy()
        bad_peers.loc[0, "city"] = "OtherCity"
        with self.assertRaises(ValueError):
            build_panel_snapshot(
                panel,
                bad_peers,
                CFG,
                period="2020Q1",
                source_metadata={"synthetic": True},
            )

    def test_strict_json_no_nan(self):
        panel, peers = self._build_fixture()
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q3",
            source_metadata={"synthetic": True},
        )
        json.dumps(snap, allow_nan=False)
        for hotel in snap["hotels"]:
            for aspect, rec in hotel["aspects"].items():
                for key, value in rec.items():
                    if isinstance(value, float):
                        self.assertTrue(math.isfinite(value), msg=f"{hotel['hotel_id']} {aspect} {key}")

    def test_complete_period_helpers(self):
        panel, _ = self._build_fixture()
        self.assertEqual(complete_periods(panel), ["2020Q1", "2020Q3"])
        self.assertEqual(resolve_period(panel, None), "2020Q3")

    def test_numeric_hotel_id_rejected(self):
        panel, peers = self._build_fixture()
        bad = panel.copy()
        bad["hotel_id"] = bad["hotel_id"].astype(object)
        bad.loc[0, "hotel_id"] = 1
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])

    def test_numeric_string_hotel_id_collision_rejected(self):
        rows = _hotel_block("1", city="Alpha", period="2021Q1", period_complete=True)
        rows_int = _hotel_block("collision", city="Alpha", period="2021Q1", period_complete=True)
        panel = pd.DataFrame(rows + rows_int)
        panel["hotel_id"] = panel["hotel_id"].astype(object)
        panel.loc[panel["hotel_id"] == "collision", "hotel_id"] = 1
        peers = _peers([
            {"hotel_id": "1", "peer_hotel_id": "collision", "city": "Alpha", "rank": 1, "distance_km": 0.5},
            {"hotel_id": "collision", "peer_hotel_id": "1", "city": "Alpha", "rank": 1, "distance_km": 0.5},
        ])
        peers["hotel_id"] = peers["hotel_id"].astype(object)
        peers.loc[peers["hotel_id"] == "collision", "hotel_id"] = 1
        with self.assertRaises(ValueError):
            build_panel_snapshot(
                panel,
                peers,
                CFG,
                period="2021Q1",
                source_metadata={"synthetic": True},
            )

    def test_empty_hotel_name_or_city_rejected(self):
        panel, _ = self._build_fixture()
        bad = panel.copy()
        bad.loc[0, "hotel_name"] = ""
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])
        bad = panel.copy()
        bad.loc[0, "city"] = ""
        with self.assertRaises(ValueError):
            validate_panel(bad, CFG["aspects"])

    def test_passed_actionability_frozen_in_snapshot_config(self):
        panel, peers = self._build_fixture()
        actionability = {"location": {"eligible_for_direct_action": False, "actionability_level": "immutable"}}
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q3",
            source_metadata={"synthetic": True},
            actionability=actionability,
        )
        self.assertIn("actionability", snap["config"])
        self.assertFalse(snap["config"]["actionability"]["location"]["eligible_for_direct_action"])
        actionability["location"]["eligible_for_direct_action"] = True
        self.assertFalse(snap["config"]["actionability"]["location"]["eligible_for_direct_action"])

    def test_passed_actionability_accepts_aspects_wrapper(self):
        panel, peers = self._build_fixture()
        wrapped = {"aspects": {"service": {"eligible_for_direct_action": True}}}
        snap = build_panel_snapshot(
            panel,
            peers,
            CFG,
            period="2020Q3",
            source_metadata={"synthetic": True},
            actionability=wrapped,
        )
        self.assertTrue(snap["config"]["actionability"]["service"]["eligible_for_direct_action"])

    def test_actionability_no_alias_mutates_caller_cfg(self):
        panel, peers = self._build_fixture()
        cfg = dict(CFG)
        actionability = {"aspects": {"location": {"eligible_for_direct_action": False}}}
        build_panel_snapshot(
            panel,
            peers,
            cfg,
            period="2020Q3",
            source_metadata={"synthetic": True},
            actionability=actionability,
        )
        self.assertNotIn("actionability", cfg)
        actionability["aspects"]["location"]["eligible_for_direct_action"] = True

    def test_cfg_existing_actionability_retained_over_param(self):
        panel, peers = self._build_fixture()
        cfg = {**CFG, "actionability": {"location": {"eligible_for_direct_action": False}}}
        snap = build_panel_snapshot(
            panel,
            peers,
            cfg,
            period="2020Q3",
            source_metadata={"synthetic": True},
            actionability={"service": {"eligible_for_direct_action": True}},
        )
        self.assertFalse(snap["config"]["actionability"]["location"]["eligible_for_direct_action"])
        self.assertNotIn("service", snap["config"]["actionability"])


@unittest.skipUnless(HAS_PANDAS, "pandas not available")
class TestBuildResearchDemoCLI(unittest.TestCase):
    def _write_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        rows = _hotel_block("a1", city="Gamma", period="2021Q4", period_complete=True)
        rows.extend(_hotel_block("a2", city="Gamma", period="2021Q4", period_complete=True))
        rows.extend(_hotel_block("a3", city="Gamma", period="2021Q4", period_complete=True))
        panel = pd.DataFrame(rows)
        peers = pd.DataFrame([
            {"hotel_id": "a1", "peer_hotel_id": "a2", "city": "Gamma", "rank": 1, "distance_km": 0.4},
            {"hotel_id": "a1", "peer_hotel_id": "a3", "city": "Gamma", "rank": 2, "distance_km": 0.6},
            {"hotel_id": "a2", "peer_hotel_id": "a1", "city": "Gamma", "rank": 1, "distance_km": 0.4},
            {"hotel_id": "a2", "peer_hotel_id": "a3", "city": "Gamma", "rank": 2, "distance_km": 0.5},
            {"hotel_id": "a3", "peer_hotel_id": "a1", "city": "Gamma", "rank": 1, "distance_km": 0.6},
            {"hotel_id": "a3", "peer_hotel_id": "a2", "city": "Gamma", "rank": 2, "distance_km": 0.5},
        ])
        panel_path = root / "panel.parquet"
        peers_path = root / "peers.parquet"
        cfg_path = root / "demo.json"
        panel.to_parquet(panel_path, index=False)
        peers.to_parquet(peers_path, index=False)
        cfg_path.write_text(json.dumps(CFG_WITH_INLINE_ACTIONABILITY), encoding="utf-8")
        return panel_path, peers_path, cfg_path

    def _write_actionability_fixture(self, root: Path) -> Path:
        act_path = root / "actionability.json"
        act_path.write_text(
            json.dumps({"aspects": INLINE_ACTIONABILITY}),
            encoding="utf-8",
        )
        return act_path

    def _run_cli(self, *extra: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(ROOT / "scripts" / "build_research_demo.py"), *extra]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd or ROOT))

    def test_cli_success_on_temp_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, peers_path, cfg_path = self._write_fixture(root)
            out_path = root / "out.json"
            proc = self._run_cli(
                "--root",
                str(root),
                "--panel",
                panel_path.name,
                "--peers",
                peers_path.name,
                "--config",
                cfg_path.name,
                "--output",
                out_path.name,
                "--overwrite",
                "--synthetic",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertTrue(out_path.exists())
            snap = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(snap["period"], "2021Q4")
            self.assertTrue(snap["synthetic"])
            self.assertGreaterEqual(snap["n_eligible_hotels"], 1)

    def test_cli_default_not_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, peers_path, cfg_path = self._write_fixture(root)
            out_path = root / "out.json"
            proc = self._run_cli(
                "--root",
                str(root),
                "--panel",
                panel_path.name,
                "--peers",
                peers_path.name,
                "--config",
                cfg_path.name,
                "--output",
                out_path.name,
                "--overwrite",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            snap = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertFalse(snap["synthetic"])

    def test_cli_refuses_overwrite_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_path = root / "out.json"
            out_path.write_text("{}", encoding="utf-8")
            proc = self._run_cli(
                "--root",
                str(root),
                "--panel",
                "missing.parquet",
                "--output",
                out_path.name,
            )
            self.assertEqual(proc.returncode, 3)

    def test_cli_refuses_broken_symlink_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_path = root / "out.json"
            os.symlink(root / "missing-target.json", out_path)
            proc = self._run_cli(
                "--root",
                str(root),
                "--panel",
                "missing.parquet",
                "--output",
                out_path.name,
            )
            self.assertEqual(proc.returncode, 3)

    def test_cli_rejects_output_same_as_input_even_with_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, peers_path, cfg_path = self._write_fixture(root)
            proc = self._run_cli(
                "--root",
                str(root),
                "--panel",
                panel_path.name,
                "--peers",
                peers_path.name,
                "--config",
                cfg_path.name,
                "--output",
                panel_path.name,
                "--overwrite",
                "--synthetic",
            )
            self.assertEqual(proc.returncode, 5)

    def test_cli_absolute_external_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, peers_path, cfg_path = self._write_fixture(root)
            out_path = root / "out.json"
            proc = self._run_cli(
                "--root",
                str(ROOT),
                "--panel",
                str(panel_path),
                "--peers",
                str(peers_path),
                "--config",
                str(cfg_path),
                "--output",
                str(out_path),
                "--overwrite",
                "--synthetic",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            snap = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(snap["sources"]["panel_parquet"], panel_path.name)

    def test_cli_schema_error_clean_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, peers_path, cfg_path = self._write_fixture(root)
            panel = pd.read_parquet(panel_path)
            panel.loc[0, "smoothed_net"] = 9.0
            panel.to_parquet(panel_path, index=False)
            out_path = root / "out.json"
            proc = self._run_cli(
                "--root",
                str(root),
                "--panel",
                panel_path.name,
                "--peers",
                peers_path.name,
                "--config",
                cfg_path.name,
                "--output",
                out_path.name,
                "--overwrite",
                "--synthetic",
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("error:", proc.stderr)
            self.assertNotIn("9.0", proc.stderr)

    def test_cli_reads_external_actionability_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, peers_path, cfg_path = self._write_fixture(root)
            act_path = self._write_actionability_fixture(root)
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            del cfg["actionability"]
            cfg["actionability_config"] = act_path.name
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
            out_path = root / "out.json"
            proc = self._run_cli(
                "--root",
                str(root),
                "--panel",
                panel_path.name,
                "--peers",
                peers_path.name,
                "--config",
                cfg_path.name,
                "--output",
                out_path.name,
                "--overwrite",
                "--synthetic",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            snap = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("actionability", snap["config"])
            self.assertFalse(snap["config"]["actionability"]["location"]["eligible_for_direct_action"])
            self.assertEqual(snap["sources"]["actionability_path"], act_path.name)
            self.assertIn("actionability_sha256", snap["source_file_hashes"])
            self.assertIn("demo_config", snap["source_file_hashes"])

    def test_cli_rejects_output_same_as_actionability_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, peers_path, cfg_path = self._write_fixture(root)
            act_path = self._write_actionability_fixture(root)
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            del cfg["actionability"]
            cfg["actionability_config"] = act_path.name
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
            proc = self._run_cli(
                "--root",
                str(root),
                "--panel",
                panel_path.name,
                "--peers",
                peers_path.name,
                "--config",
                cfg_path.name,
                "--output",
                act_path.name,
                "--overwrite",
                "--synthetic",
            )
            self.assertEqual(proc.returncode, 5)

    def test_cli_concurrent_no_overwrite_one_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, peers_path, cfg_path = self._write_fixture(root)
            out_path = root / "out.json"
            barrier = threading.Barrier(2)

            def worker() -> int:
                barrier.wait()
                proc = self._run_cli(
                    "--root",
                    str(root),
                    "--panel",
                    panel_path.name,
                    "--peers",
                    peers_path.name,
                    "--config",
                    cfg_path.name,
                    "--output",
                    out_path.name,
                    "--synthetic",
                )
                return proc.returncode

            results = []
            threads = [threading.Thread(target=lambda: results.append(worker())) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(results.count(0), 1)
            self.assertTrue(all(code in (0, 1, 3) for code in results))
            snap = json.loads(out_path.read_text(encoding="utf-8"))
            json.dumps(snap, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
