"""Synthetic and metadata checks for the isolated reproduction runner."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_research import (  # noqa: E402
    _assert_resume_manifest,
    _build_reproduction_manifest,
    _configure_paths,
    _guard_output_root,
    _resume_command,
    _write_reproduction_manifest,
)
from src.autonomous.panel import build_measurement_v2, run_wave0  # noqa: E402
from src.autonomous.report import capture_demo_screenshots  # noqa: E402


@contextlib.contextmanager
def _env(**updates: str | None):
    old = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_legacy_inputs(root: Path) -> None:
    paths = [
        "conf/autonomous_research.json",
        "conf/temporal_feasibility.json",
        "data/processed/hotel_aspect_quarter.parquet",
        "data/processed/geo_reference_sets.parquet",
        "outputs/overnight/FACTS.json",
        "outputs/overnight/state.json",
        "outputs/overnight/FAILURES.md",
        "outputs/overnight/REVIEW.md",
        "outputs/overnight/HANDOFF_HISTORICAL.md",
        "outputs/overnight/data_audit/europe_515k_manifest.json",
        "outputs/overnight/feasibility/tables/candidate_events.csv",
        "outputs/overnight/predictive_pilot/metrics.json",
    ]
    for rel in paths:
        src = ROOT / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


class TestReproductionPaths(unittest.TestCase):
    def test_explicit_output_root_derives_all_run_outputs(self):
        with tempfile.TemporaryDirectory() as td, _env(
            FYP_AUTONOMOUS_OUT=None,
            FYP_PANEL_V2=None,
            FYP_PEERS_V2=None,
            FYP_PAPER_DIR=None,
            FYP_DATA_CACHE_ROOT=None,
            FYP_PRIVATE_DATA_ROOT=None,
            FYP_PRIVATE_MODEL_ROOT=None,
            FYP_SMALL_FIXTURE=None,
            FYP_SKIP_UI=None,
        ):
            root = Path(td)
            out = _configure_paths(
                root,
                output_root="runs/reference",
                small_fixture=False,
                skip_ui=True,
            )
            self.assertEqual(out, (root / "runs" / "reference").resolve())
            self.assertEqual(os.environ["FYP_AUTONOMOUS_OUT"], str(out))
            self.assertEqual(
                os.environ["FYP_PANEL_V2"],
                str(out / "hotel_aspect_quarter_v2.parquet"),
            )
            self.assertEqual(
                os.environ["FYP_PEERS_V2"],
                str(out / "geo_reference_sets_v2.parquet"),
            )
            self.assertEqual(os.environ["FYP_PAPER_DIR"], str(out / "paper"))
            self.assertEqual(os.environ["FYP_SKIP_UI"], "1")

    def test_default_fixture_keeps_established_panel_paths(self):
        with tempfile.TemporaryDirectory() as td, _env(
            FYP_AUTONOMOUS_OUT=None,
            FYP_PANEL_V2=None,
            FYP_PEERS_V2=None,
            FYP_PAPER_DIR=None,
            FYP_DATA_CACHE_ROOT=None,
            FYP_PRIVATE_DATA_ROOT=None,
            FYP_PRIVATE_MODEL_ROOT=None,
            FYP_SMALL_FIXTURE=None,
            FYP_SKIP_UI=None,
        ):
            root = Path(td)
            out = _configure_paths(
                root,
                output_root=None,
                small_fixture=True,
                skip_ui=True,
            )
            fixture_base = (root / "outputs" / "autonomous" / "fixtures").resolve()
            self.assertEqual(out, fixture_base / "out")
            self.assertEqual(
                Path(os.environ["FYP_PANEL_V2"]),
                fixture_base / "hotel_aspect_quarter_v2.parquet",
            )
            self.assertEqual(
                Path(os.environ["FYP_PEERS_V2"]),
                fixture_base / "geo_reference_sets_v2.parquet",
            )

    def test_default_full_run_is_separate_from_science_snapshot(self):
        with tempfile.TemporaryDirectory() as td, _env(
            FYP_AUTONOMOUS_OUT=None,
            FYP_PANEL_V2=None,
            FYP_PEERS_V2=None,
            FYP_PAPER_DIR=None,
            FYP_DATA_CACHE_ROOT=None,
            FYP_PRIVATE_DATA_ROOT=None,
            FYP_PRIVATE_MODEL_ROOT=None,
            FYP_SMALL_FIXTURE=None,
            FYP_SKIP_UI=None,
        ):
            root = Path(td)
            out = _configure_paths(
                root,
                output_root=None,
                small_fixture=False,
                skip_ui=False,
            )
            self.assertEqual(
                out,
                (root / "outputs" / "autonomous" / "reproduced").resolve(),
            )
            self.assertNotEqual(out, root / "outputs" / "autonomous")
            self.assertNotIn("FYP_SKIP_UI", os.environ)

    def test_environment_output_root_rebinds_derived_outputs(self):
        with tempfile.TemporaryDirectory() as td, _env(
            FYP_AUTONOMOUS_OUT="runs/from-env",
            FYP_PANEL_V2="data/processed/hotel_aspect_quarter_v2.parquet",
            FYP_PEERS_V2="data/processed/geo_reference_sets_v2.parquet",
            FYP_PAPER_DIR="paper/autonomous",
            FYP_DATA_CACHE_ROOT=None,
            FYP_PRIVATE_DATA_ROOT=None,
            FYP_PRIVATE_MODEL_ROOT=None,
            FYP_SMALL_FIXTURE=None,
            FYP_SKIP_UI=None,
        ):
            root = Path(td)
            out = _configure_paths(
                root,
                output_root=None,
                small_fixture=False,
                skip_ui=False,
            )
            self.assertEqual(out, (root / "runs" / "from-env").resolve())
            self.assertEqual(Path(os.environ["FYP_PANEL_V2"]), out / "hotel_aspect_quarter_v2.parquet")
            self.assertEqual(Path(os.environ["FYP_PEERS_V2"]), out / "geo_reference_sets_v2.parquet")
            self.assertEqual(Path(os.environ["FYP_PAPER_DIR"]), out / "paper")

    def test_force_cannot_replace_existing_facts(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            out.mkdir()
            (out / "FACTS.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                _guard_output_root(
                    Path(td), out, small_fixture=False, resume=False, force=False
                )
            with self.assertRaises(RuntimeError):
                _guard_output_root(
                    Path(td), out, small_fixture=False, resume=False, force=True
                )
            with self.assertRaises(RuntimeError):
                _guard_output_root(
                    Path(td), out, small_fixture=True, resume=False, force=True
                )

    def test_output_root_must_be_a_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output_file = root / "run"
            output_file.write_text("occupied\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                _guard_output_root(
                    root, output_file, small_fixture=False, resume=False, force=False
                )

    def test_external_path_names_are_not_written_to_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "conf").mkdir(parents=True)
            shutil.copyfile(
                ROOT / "conf" / "autonomous_research.json",
                root / "conf" / "autonomous_research.json",
            )
            cfg = json.loads(
                (root / "conf" / "autonomous_research.json").read_text(encoding="utf-8")
            )
            private_mount = "/private/research-account-token-123"
            with _env(
                FYP_AUTONOMOUS_OUT=str(root / "run"),
                FYP_PANEL_V2=None,
                FYP_PEERS_V2=None,
                FYP_PAPER_DIR=None,
                FYP_DATA_CACHE_ROOT=private_mount,
                FYP_PRIVATE_MODEL_ROOT=private_mount,
            ):
                manifest = _build_reproduction_manifest(
                    root,
                    root / "run",
                    cfg,
                    small_fixture=False,
                    verify_only=False,
                    resume=False,
                    skip_ui=False,
                )
            self.assertNotIn(private_mount, json.dumps(manifest))
            self.assertEqual(manifest["assets"]["dataset_csv"]["path"], "<external>")

    def test_canonical_output_roots_are_always_protected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in (
                "outputs/autonomous",
                "outputs/overnight",
                "data/processed",
                "data/processed/hotel_aspect_quarter_v2.parquet",
                "data/processed/geo_reference_sets_v2.parquet",
            ):
                candidate = root / rel
                candidate.mkdir(parents=True, exist_ok=True)
                with self.assertRaises(RuntimeError):
                    _guard_output_root(
                        root,
                        candidate,
                        small_fixture=False,
                        resume=True,
                        force=False,
                    )
                with self.assertRaises(RuntimeError):
                    _guard_output_root(
                        root,
                        candidate,
                        small_fixture=True,
                        resume=False,
                        force=False,
                    )


class TestWave0Immutability(unittest.TestCase):
    def test_wave0_does_not_modify_historical_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _copy_legacy_inputs(root)
            before = {
                str(path.relative_to(root)): _sha256(path)
                for path in (root / "outputs" / "overnight").rglob("*")
                if path.is_file()
            }
            with _env(
                FYP_AUTONOMOUS_OUT=str(root / "outputs" / "autonomous"),
                FYP_PANEL_V2=None,
                FYP_PEERS_V2=None,
                FYP_PAPER_DIR=None,
            ):
                findings = run_wave0(root)
            after = {
                str(path.relative_to(root)): _sha256(path)
                for path in (root / "outputs" / "overnight").rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertTrue(findings["historical_facts_snapshot"]["europe_515k_present"])
            self.assertTrue(findings["historical_state_snapshot"]["state_present"])


class TestSourceValidation(unittest.TestCase):
    def _write_csv(self, root: Path) -> Path:
        path = root / "data" / "cache" / "d1_europe" / "Hotel_Reviews.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "Hotel_Address,Hotel_Name,Review_Date,Reviewer_Score,Reviewer_Nationality,"
            "Positive_Review,Negative_Review,lat,lng\n"
            "1 Example Street London United Kingdom,Hotel A,01/01/2017,8.0,UK,"
            "Breakfast good,No Negative,51.5,-0.1\n",
            encoding="utf-8",
        )
        return path

    def _write_configs(self, root: Path, csv_path: Path, expected_rows: int) -> None:
        conf = root / "conf"
        conf.mkdir(parents=True, exist_ok=True)
        cfg = json.loads((ROOT / "conf" / "autonomous_research.json").read_text(encoding="utf-8"))
        cfg["dataset"]["expected_bytes"] = csv_path.stat().st_size
        cfg["dataset"]["expected_sha256"] = _sha256(csv_path)
        cfg["dataset"]["expected_rows"] = expected_rows
        (conf / "autonomous_research.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )
        shutil.copyfile(
            ROOT / "conf" / "temporal_feasibility.json",
            conf / "temporal_feasibility.json",
        )

    def test_row_count_is_checked_before_panel_publish(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = self._write_csv(root)
            self._write_configs(root, csv_path, expected_rows=2)
            with _env(
                FYP_DATA_CACHE_ROOT=str(root / "data" / "cache"),
                FYP_AUTONOMOUS_OUT=str(root / "outputs" / "autonomous"),
                FYP_PANEL_V2=None,
                FYP_PEERS_V2=None,
                FYP_PAPER_DIR=None,
                FYP_PRIVATE_MODEL_ROOT=str(root / "models"),
                FYP_SMALL_FIXTURE=None,
            ):
                with self.assertRaisesRegex(ValueError, "row-count mismatch"):
                    build_measurement_v2(root, small_fixture=False)
            self.assertFalse(
                (root / "data" / "processed" / "hotel_aspect_quarter_v2.parquet").exists()
            )

    def test_sha_mismatch_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = self._write_csv(root)
            self._write_configs(root, csv_path, expected_rows=1)
            cfg_path = root / "conf" / "autonomous_research.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["dataset"]["expected_sha256"] = "0" * 64
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
            with _env(
                FYP_DATA_CACHE_ROOT=str(root / "data" / "cache"),
                FYP_AUTONOMOUS_OUT=str(root / "outputs" / "autonomous"),
                FYP_PANEL_V2=None,
                FYP_PEERS_V2=None,
                FYP_PAPER_DIR=None,
                FYP_PRIVATE_MODEL_ROOT=str(root / "models"),
                FYP_SMALL_FIXTURE=None,
            ):
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    build_measurement_v2(root, small_fixture=False)
            self.assertFalse(
                (root / "data" / "processed" / "hotel_aspect_quarter_v2.parquet").exists()
            )


class TestResumeBinding(unittest.TestCase):
    def test_next_resume_command_preserves_mode_flags(self):
        command = _resume_command(
            Path("/tmp/run with spaces"),
            9,
            small_fixture=True,
            verify_only=True,
            skip_ui=True,
        )
        self.assertEqual(
            shlex.split(command),
            [
                "python",
                "run_research.py",
                "--resume",
                "--from-wave",
                "10",
                "--output-root",
                "/tmp/run with spaces",
                "--small-fixture",
                "--verify-only",
                "--skip-ui",
            ],
        )

    def test_resume_requires_same_config_and_asset_fingerprints(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "conf").mkdir(parents=True)
            shutil.copyfile(
                ROOT / "conf" / "autonomous_research.json",
                root / "conf" / "autonomous_research.json",
            )
            cfg = json.loads(
                (root / "conf" / "autonomous_research.json").read_text(encoding="utf-8")
            )
            out = root / "run"
            with _env(
                FYP_AUTONOMOUS_OUT=str(out),
                FYP_PANEL_V2=str(out / "hotel_aspect_quarter_v2.parquet"),
                FYP_PEERS_V2=str(out / "geo_reference_sets_v2.parquet"),
                FYP_PAPER_DIR=str(out / "paper"),
                FYP_DATA_CACHE_ROOT=str(root / "data" / "cache"),
                FYP_PRIVATE_MODEL_ROOT=str(root / "models"),
                FYP_SMALL_FIXTURE="1",
                FYP_SKIP_UI="1",
            ):
                _write_reproduction_manifest(
                    root,
                    out,
                    cfg,
                    small_fixture=True,
                    verify_only=True,
                    resume=False,
                    skip_ui=True,
                )
                _assert_resume_manifest(
                    root,
                    out,
                    cfg,
                    small_fixture=True,
                    verify_only=True,
                    skip_ui=True,
                )
                cfg["seed"] = int(cfg["seed"]) + 1
                (root / "conf" / "autonomous_research.json").write_text(
                    json.dumps(cfg), encoding="utf-8"
                )
                with self.assertRaisesRegex(RuntimeError, "fingerprints changed"):
                    _assert_resume_manifest(
                        root,
                        out,
                        cfg,
                        small_fixture=True,
                        verify_only=True,
                        skip_ui=True,
                    )

    def test_resume_rejects_demo_or_actionability_config_change(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            conf = root / "conf"
            conf.mkdir(parents=True)
            for name in ("autonomous_research.json", "demo.json", "actionability.json"):
                shutil.copyfile(ROOT / "conf" / name, conf / name)
            cfg = json.loads((conf / "autonomous_research.json").read_text(encoding="utf-8"))
            out = root / "run"
            with _env(
                FYP_AUTONOMOUS_OUT=str(out),
                FYP_PANEL_V2=str(out / "hotel_aspect_quarter_v2.parquet"),
                FYP_PEERS_V2=str(out / "geo_reference_sets_v2.parquet"),
                FYP_PAPER_DIR=str(out / "paper"),
                FYP_DATA_CACHE_ROOT=str(root / "data" / "cache"),
                FYP_PRIVATE_MODEL_ROOT=str(root / "models"),
                FYP_SMALL_FIXTURE="1",
                FYP_SKIP_UI="1",
            ):
                _write_reproduction_manifest(
                    root,
                    out,
                    cfg,
                    small_fixture=True,
                    verify_only=True,
                    resume=False,
                    skip_ui=True,
                )
                demo_path = conf / "demo.json"
                demo = json.loads(demo_path.read_text(encoding="utf-8"))
                demo["_test_manifest_change"] = True
                demo_path.write_text(json.dumps(demo), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "fingerprints changed"):
                    _assert_resume_manifest(
                        root,
                        out,
                        cfg,
                        small_fixture=True,
                        verify_only=True,
                        skip_ui=True,
                    )

    def test_resume_rejects_temporal_config_change(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            conf = root / "conf"
            conf.mkdir(parents=True)
            for name in (
                "autonomous_research.json",
                "demo.json",
                "actionability.json",
                "temporal_feasibility.json",
            ):
                shutil.copyfile(ROOT / "conf" / name, conf / name)
            cfg = json.loads((conf / "autonomous_research.json").read_text(encoding="utf-8"))
            out = root / "run"
            with _env(
                FYP_AUTONOMOUS_OUT=str(out),
                FYP_PANEL_V2=str(out / "hotel_aspect_quarter_v2.parquet"),
                FYP_PEERS_V2=str(out / "geo_reference_sets_v2.parquet"),
                FYP_PAPER_DIR=str(out / "paper"),
                FYP_DATA_CACHE_ROOT=str(root / "data" / "cache"),
                FYP_PRIVATE_MODEL_ROOT=str(root / "models"),
                FYP_SMALL_FIXTURE="1",
                FYP_SKIP_UI="1",
            ):
                _write_reproduction_manifest(
                    root,
                    out,
                    cfg,
                    small_fixture=True,
                    verify_only=True,
                    resume=False,
                    skip_ui=True,
                )
                temporal_path = conf / "temporal_feasibility.json"
                temporal = json.loads(temporal_path.read_text(encoding="utf-8"))
                temporal["_test_manifest_change"] = True
                temporal_path.write_text(json.dumps(temporal), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "fingerprints changed"):
                    _assert_resume_manifest(
                        root,
                        out,
                        cfg,
                        small_fixture=True,
                        verify_only=True,
                        skip_ui=True,
                    )


class TestSkipUI(unittest.TestCase):
    def test_skip_ui_environment_has_explicit_status(self):
        with tempfile.TemporaryDirectory() as td, _env(
            FYP_AUTONOMOUS_OUT=str(Path(td) / "run"),
            FYP_SKIP_UI="1",
        ):
            result = capture_demo_screenshots(Path(td), skip=False)
            self.assertEqual(result["status"], "SKIPPED_UI_REQUESTED")

class TestAssetChecker(unittest.TestCase):
    def test_missing_assets_are_reported_without_raw_text(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "conf").mkdir(parents=True)
            shutil.copyfile(
                ROOT / "conf" / "autonomous_research.json",
                root / "conf" / "autonomous_research.json",
            )
            env = dict(os.environ)
            env.pop("FYP_DATA_CACHE_ROOT", None)
            env.pop("FYP_PRIVATE_MODEL_ROOT", None)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "verify_reproduction_assets.py"),
                    "--root",
                    str(root),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertEqual(report["status"], "MISSING_OR_MISMATCHED")
            self.assertEqual(report["assets"]["dataset_csv"]["status"], "MISSING")
            self.assertEqual(report["assets"]["absa_model_weights"]["status"], "MISSING")
            self.assertEqual(report["assets"]["absa_sentencepiece"]["status"], "MISSING")
            self.assertNotIn("Positive_Review", proc.stdout)
            self.assertNotIn("Negative_Review", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
