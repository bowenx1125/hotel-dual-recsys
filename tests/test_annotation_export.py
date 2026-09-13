"""Tests for scripts/export_annotation_tasks.py (synthetic fixtures only)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.export_annotation_tasks import (  # noqa: E402
    CSV_COLUMNS,
    ID_STRATEGY,
    ExportError,
    _opaque_export_item_id,
    export_tasks,
    main,
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _synthetic_item(
    item_id: str,
    *,
    city: str = "SynthCity",
    aspect: str = "location",
    text: str = "synthetic review excerpt",
    section: str | None = "positive",
    period: str | None = "2016Q1",
    hotel_id: str | None = "hotel_synth_01",
    weak_label_from_section: str | None = "positive",
    extra: dict | None = None,
) -> dict:
    item: dict = {
        "item_id": item_id,
        "city": city,
        "aspect": aspect,
        "text": text,
    }
    if section is not None:
        item["section"] = section
    if period is not None:
        item["period"] = period
    if hotel_id is not None:
        item["hotel_id"] = hotel_id
    if weak_label_from_section is not None:
        item["weak_label_from_section"] = weak_label_from_section
    if extra:
        item.update(extra)
    return item


def _make_pack(items: list[dict]) -> dict:
    return {
        "schema": "human_absa_pack_v1",
        "HUMAN_VALIDATION_REQUIRED": True,
        "items": items,
    }


class ExportAnnotationTasksTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.private_root = self.repo_root / "outputs" / "autonomous" / "private"
        self.private_root.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _write_pack(self, pack: dict, name: str = "pack.json") -> Path:
        path = self.private_root / name
        path.write_text(json.dumps(pack), encoding="utf-8")
        return path

    def _export(self, pack: dict, output_name: str = "round_01", **kwargs):
        input_path = self._write_pack(pack)
        output_dir = self.private_root / output_name
        metadata = export_tasks(
            input_path,
            output_dir,
            private_root=self.private_root,
            **kwargs,
        )
        return input_path, output_dir, metadata

    def _read_csv_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_blinding_and_blank_labels(self) -> None:
        secret_text = "SYNTH_SECRET_ALPHA"
        secret_weak = "SYNTH_WEAK_SECRET"
        pack = _make_pack(
            [
                _synthetic_item(
                    "item_a",
                    text=secret_text,
                    weak_label_from_section=secret_weak,
                    extra={"machine_score": "9.1"},
                )
            ]
        )
        _, output_dir, metadata = self._export(pack)

        for csv_name in ("annotator_a.csv", "annotator_b.csv"):
            rows = self._read_csv_rows(output_dir / csv_name)
            self.assertEqual(list(rows[0].keys()), CSV_COLUMNS)
            self.assertEqual(rows[0]["label"], "")
            self.assertEqual(rows[0]["notes"], "")
            self.assertRegex(rows[0]["item_id"], r"^item_[0-9a-f]{64}$")
            self.assertNotEqual(rows[0]["item_id"], "item_a")
            self.assertNotIn("section", rows[0])
            self.assertNotIn("weak_label_from_section", rows[0])
            self.assertNotIn("hotel_id", rows[0])
            self.assertNotIn("period", rows[0])

        meta_text = json.dumps(metadata)
        self.assertNotIn(secret_text, meta_text)
        self.assertNotIn(secret_weak, meta_text)
        self.assertNotIn("weak_label", meta_text)

    def test_deterministic_content_and_overlap(self) -> None:
        pack = _make_pack(
            [
                _synthetic_item(f"id_{i}", city=f"City{i % 2}", aspect=f"asp{i % 3}")
                for i in range(8)
            ]
        )
        input_path = self._write_pack(pack, "pack_det.json")

        meta1 = export_tasks(
            input_path,
            self.private_root / "round_a",
            private_root=self.private_root,
            overlap_rate=0.25,
            seed=99,
        )
        meta2 = export_tasks(
            input_path,
            self.private_root / "round_b",
            private_root=self.private_root,
            overlap_rate=0.25,
            seed=99,
        )

        self.assertEqual(meta1["annotator_a_sha256"], meta2["annotator_a_sha256"])
        self.assertEqual(meta1["annotator_b_sha256"], meta2["annotator_b_sha256"])
        self.assertEqual(meta1["n_overlap"], meta2["n_overlap"])

        rows_a = self._read_csv_rows(self.private_root / "round_a" / "annotator_a.csv")
        rows_b = self._read_csv_rows(self.private_root / "round_b" / "annotator_b.csv")
        ids_a = {row["item_id"] for row in rows_a}
        ids_b = {row["item_id"] for row in rows_b}
        self.assertEqual(len(rows_a), 8)
        self.assertEqual(len(rows_b), meta1["n_overlap"])
        self.assertTrue(ids_b.issubset(ids_a))

    def test_ceil_overlap_for_small_sizes(self) -> None:
        pack = _make_pack([_synthetic_item(f"small_{i}") for i in range(3)])
        _, _, metadata = self._export(pack, "round_small", overlap_rate=0.2, seed=1)
        self.assertEqual(metadata["n_overlap"], math.ceil(3 * 0.2))

    def test_duplicate_ids_rejected_before_output(self) -> None:
        pack = _make_pack(
            [
                _synthetic_item("dup_id", text="first synthetic"),
                _synthetic_item("dup_id", text="second synthetic"),
            ]
        )
        input_path = self._write_pack(pack)
        output_dir = self.private_root / "must_not_exist"
        with self.assertRaises(Exception):
            export_tasks(
                input_path,
                output_dir,
                private_root=self.private_root,
            )
        self.assertFalse(output_dir.exists())

    def test_malformed_items_rejected_before_output(self) -> None:
        pack = _make_pack([{"item_id": "", "text": "x"}])
        input_path = self._write_pack(pack)
        output_dir = self.private_root / "bad_pack"
        with self.assertRaises(Exception):
            export_tasks(input_path, output_dir, private_root=self.private_root)
        self.assertFalse(output_dir.exists())

    def test_invalid_overlap_rate_rejected(self) -> None:
        pack = _make_pack([_synthetic_item("only_one")])
        input_path = self._write_pack(pack)
        output_dir = self.private_root / "bad_rate"
        for rate in (-0.1, 1.1, float("nan")):
            with self.assertRaises(Exception):
                export_tasks(
                    input_path,
                    output_dir,
                    private_root=self.private_root,
                    overlap_rate=rate,
                )
            self.assertFalse(output_dir.exists())

    def test_output_reuse_rejected(self) -> None:
        pack = _make_pack([_synthetic_item("reuse_id")])
        _, output_dir, _ = self._export(pack, "existing_round")
        with self.assertRaises(Exception):
            export_tasks(
                self.private_root / "pack.json",
                output_dir,
                private_root=self.private_root,
            )

    def test_path_escape_rejected(self) -> None:
        pack = _make_pack([_synthetic_item("escape_id")])
        input_path = self._write_pack(pack)
        outside = Path(self._tmpdir.name) / "outside"
        outside.mkdir()
        with self.assertRaises(Exception):
            export_tasks(
                input_path,
                outside,
                private_root=self.private_root,
            )

        outside_pack = Path(self._tmpdir.name) / "outside_pack.json"
        outside_pack.write_text(input_path.read_text(encoding="utf-8"), encoding="utf-8")
        link_input = self.private_root / "link_escape.json"
        try:
            link_input.symlink_to(outside_pack)
        except OSError:
            self.skipTest("symlink creation not permitted")
        with self.assertRaises(Exception):
            export_tasks(
                link_input,
                self.private_root / "escape_out",
                private_root=self.private_root,
            )

    def test_formula_prefixes_and_csv_roundtrip(self) -> None:
        pack = _make_pack(
            [
                _synthetic_item("f1", text="=1+1"),
                _synthetic_item("f2", text="+leading"),
                _synthetic_item("f3", text="-minus"),
                _synthetic_item("f4", text="@cmd"),
                _synthetic_item("f5", text="\tleading tab"),
                _synthetic_item(
                    "f6",
                    text="line with, comma\nand newline",
                    city="  =hidden city",
                ),
            ]
        )
        input_path = self._write_pack(pack, "formula_pack.json")
        input_sha256 = _sha256_bytes(input_path.read_bytes())
        output_dir = self.private_root / "formula_round"
        metadata = export_tasks(input_path, output_dir, private_root=self.private_root)

        rows = self._read_csv_rows(output_dir / "annotator_a.csv")
        opaque_f1 = _opaque_export_item_id(input_sha256, "f1")
        opaque_f2 = _opaque_export_item_id(input_sha256, "f2")
        opaque_f5 = _opaque_export_item_id(input_sha256, "f5")
        opaque_f6 = _opaque_export_item_id(input_sha256, "f6")
        by_id = {row["item_id"]: row for row in rows}
        self.assertTrue(by_id[opaque_f1]["text"].startswith("'"))
        self.assertTrue(by_id[opaque_f2]["text"].startswith("'"))
        self.assertTrue(by_id[opaque_f5]["text"].startswith("'"))
        self.assertTrue(by_id[opaque_f6]["city"].startswith("'"))
        self.assertIn("comma", by_id[opaque_f6]["text"])
        self.assertIn("formula_injection", json.dumps(metadata).lower())

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        writer.writerow(
            [
                by_id[opaque_f6]["item_id"],
                by_id[opaque_f6]["city"],
                by_id[opaque_f6]["aspect"],
                by_id[opaque_f6]["text"],
                "",
                "",
            ]
        )
        buffer.seek(0)
        roundtrip = next(csv.DictReader(buffer))
        self.assertEqual(roundtrip["text"], by_id[opaque_f6]["text"])

    def test_opaque_id_collision_rejected(self) -> None:
        import scripts.export_annotation_tasks as export_module

        pack = _make_pack(
            [
                _synthetic_item("collision_a"),
                _synthetic_item("collision_b"),
            ]
        )
        input_path = self._write_pack(pack)
        output_dir = self.private_root / "collision_round"

        def fake_opaque(input_sha256: str, source_item_id: str) -> str:
            return "item_deadbeef"

        with patch.object(export_module, "_opaque_export_item_id", side_effect=fake_opaque):
            with self.assertRaises(ExportError):
                export_tasks(
                    input_path,
                    output_dir,
                    private_root=self.private_root,
                )
        self.assertFalse(output_dir.exists())

    def test_opaque_ids_blind_label_leaking_source_ids(self) -> None:
        source_ids = [
            "abc-room-positive",
            "def-service-negative",
            "ghi-location-neutral",
        ]
        pack = _make_pack(
            [
                _synthetic_item(
                    source_id,
                    city=f"City{i}",
                    aspect="service",
                    text=f"synthetic excerpt {i}",
                )
                for i, source_id in enumerate(source_ids)
            ]
        )
        input_path = self._write_pack(pack, "opaque_pack.json")
        before = input_path.read_bytes()
        input_sha256 = _sha256_bytes(before)

        meta_seed_a = export_tasks(
            input_path,
            self.private_root / "opaque_seed_a",
            private_root=self.private_root,
            overlap_rate=0.34,
            seed=11,
        )
        meta_seed_b = export_tasks(
            input_path,
            self.private_root / "opaque_seed_b",
            private_root=self.private_root,
            overlap_rate=0.34,
            seed=99,
        )
        after = input_path.read_bytes()
        self.assertEqual(before, after)

        opaque_ids = {
            _opaque_export_item_id(input_sha256, source_id) for source_id in source_ids
        }
        for source_id in source_ids:
            self.assertNotIn(source_id, opaque_ids)

        for round_name, meta in (("opaque_seed_a", meta_seed_a), ("opaque_seed_b", meta_seed_b)):
            output_dir = self.private_root / round_name
            rows_a = self._read_csv_rows(output_dir / "annotator_a.csv")
            rows_b = self._read_csv_rows(output_dir / "annotator_b.csv")
            ids_a = {row["item_id"] for row in rows_a}
            ids_b = {row["item_id"] for row in rows_b}

            for row in rows_a + rows_b:
                self.assertRegex(row["item_id"], r"^item_[0-9a-f]{64}$")

            meta_text = json.dumps(meta)
            for source_id in source_ids:
                self.assertNotIn(source_id, meta_text)

            csv_text = (output_dir / "annotator_a.csv").read_text(encoding="utf-8-sig")
            csv_text += (output_dir / "annotator_b.csv").read_text(encoding="utf-8-sig")
            for source_id in source_ids:
                self.assertNotIn(source_id, csv_text)

            self.assertEqual(ids_a, opaque_ids)
            self.assertTrue(ids_b.issubset(ids_a))
            self.assertEqual(meta["n_overlap"], len(ids_b))

        rows_a_first = self._read_csv_rows(
            self.private_root / "opaque_seed_a" / "annotator_a.csv"
        )
        rows_a_second = self._read_csv_rows(
            self.private_root / "opaque_seed_b" / "annotator_a.csv"
        )
        self.assertEqual(
            {row["item_id"] for row in rows_a_first},
            {row["item_id"] for row in rows_a_second},
        )

    def test_input_unchanged(self) -> None:
        pack = _make_pack([_synthetic_item("stable_id", text="stable synthetic text")])
        input_path = self._write_pack(pack)
        before = input_path.read_bytes()
        export_tasks(
            input_path,
            self.private_root / "unchanged_round",
            private_root=self.private_root,
        )
        after = input_path.read_bytes()
        self.assertEqual(_sha256_bytes(before), _sha256_bytes(after))

    def test_metadata_required_fields(self) -> None:
        pack = _make_pack(
            [
                _synthetic_item("m1", city="C1", aspect="a1", hotel_id="h1"),
                _synthetic_item("m2", city="C1", aspect="a2", hotel_id="h2"),
            ]
        )
        _, _, metadata = self._export(pack, "meta_round", overlap_rate=0.5, seed=7)

        self.assertEqual(metadata["status"], "PILOT_UNANNOTATED")
        self.assertEqual(metadata["source_provenance"], "existing_pack_not_independently_verified")
        self.assertTrue(metadata["no_gold_accuracy"])
        self.assertEqual(metadata["columns"], CSV_COLUMNS)
        self.assertEqual(metadata["allowed_labels"], ["positive", "negative", "neutral", "not_about_aspect"])
        self.assertEqual(metadata["city_counts"], {"C1": 2})
        self.assertEqual(metadata["aspect_counts"], {"a1": 1, "a2": 1})
        self.assertEqual(metadata["unique_hotel_count"], 2)
        self.assertIn("input_sha256", metadata)
        self.assertIn("annotator_a_sha256", metadata)
        self.assertIn("annotator_b_sha256", metadata)
        self.assertEqual(metadata["id_strategy"], ID_STRATEGY)

    def test_optional_fields_minimal_item(self) -> None:
        pack = _make_pack(
            [
                _synthetic_item(
                    "minimal_1",
                    section=None,
                    period=None,
                    hotel_id=None,
                    weak_label_from_section=None,
                    extra={"unknown_field": "ignored"},
                ),
                _synthetic_item(
                    "minimal_2",
                    city="OtherCity",
                    aspect="service",
                    section=None,
                    period=None,
                    hotel_id="only_one_hotel",
                    weak_label_from_section=None,
                ),
            ]
        )
        _, output_dir, metadata = self._export(pack, "optional_round")

        rows = self._read_csv_rows(output_dir / "annotator_a.csv")
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(set(row.keys()), set(CSV_COLUMNS))
            self.assertEqual(row["label"], "")
            self.assertEqual(row["notes"], "")

        self.assertEqual(metadata["unique_hotel_count"], 1)
        self.assertEqual(metadata["city_counts"], {"SynthCity": 1, "OtherCity": 1})

    def test_main_first_run_defaults_creates_annotation_rounds(self) -> None:
        import scripts.export_annotation_tasks as export_module

        pack = _make_pack([_synthetic_item("default_run_id")])
        default_input = self.private_root / "human_annotation_pack.json"
        default_input.write_text(json.dumps(pack), encoding="utf-8")

        self.assertFalse((self.private_root / "annotation_rounds").exists())

        fixed_stamp = "20990101_000000"
        buffer = io.StringIO()
        stdout = sys.stdout
        try:
            sys.stdout = buffer
            with (
                patch.object(export_module, "ROOT", self.repo_root),
                patch.object(
                    export_module,
                    "_default_output_dir",
                    return_value=self.private_root / "annotation_rounds" / fixed_stamp,
                ),
            ):
                code = main([])
        finally:
            sys.stdout = stdout

        self.assertEqual(code, 0)
        output_dir = self.private_root / "annotation_rounds" / fixed_stamp
        self.assertTrue(output_dir.is_dir())
        self.assertTrue((output_dir / "annotator_a.csv").is_file())
        self.assertTrue((output_dir / "annotator_b.csv").is_file())
        self.assertTrue((output_dir / "metadata.json").is_file())

    def test_cleanup_on_mid_csv_write_failure(self) -> None:
        import scripts.export_annotation_tasks as export_module

        pack = _make_pack([_synthetic_item("csv_fail_id")])
        input_path = self._write_pack(pack, "csv_fail_pack.json")
        output_dir = self.private_root / "csv_fail_round"

        original_write_csv = export_module._write_csv
        call_count = 0

        def flaky_write_csv(path, rows, created_files):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                original_write_csv(path, rows, created_files)
                raise OSError("simulated mid-write failure")

        with patch.object(export_module, "_write_csv", side_effect=flaky_write_csv):
            with self.assertRaises(OSError):
                export_tasks(
                    input_path,
                    output_dir,
                    private_root=self.private_root,
                )

        self.assertFalse(output_dir.exists())

    def test_cleanup_on_mid_metadata_write_failure(self) -> None:
        import scripts.export_annotation_tasks as export_module

        pack = _make_pack([_synthetic_item("meta_fail_id")])
        input_path = self._write_pack(pack, "meta_fail_pack.json")
        output_dir = self.private_root / "meta_fail_round"

        original_dump = json.dump

        def flaky_dump(obj, fp, **kwargs):
            original_dump(obj, fp, **kwargs)
            raise OSError("simulated metadata write failure")

        with patch.object(json, "dump", side_effect=flaky_dump):
            with self.assertRaises(OSError):
                export_tasks(
                    input_path,
                    output_dir,
                    private_root=self.private_root,
                )

        self.assertFalse(output_dir.exists())
        self.assertFalse((output_dir / "annotator_a.csv").exists())
        self.assertFalse((output_dir / "annotator_b.csv").exists())

    def test_concurrent_directory_collision_preserves_other_dir(self) -> None:
        pack = _make_pack([_synthetic_item("collision_id")])
        input_path = self._write_pack(pack, "collision_pack.json")
        output_dir = self.private_root / "collision_round"
        marker = output_dir / "foreign_marker.txt"

        original_mkdir = Path.mkdir

        def racing_mkdir(self_path, *args, **kwargs):
            if self_path.resolve() == output_dir.resolve() and kwargs.get("exist_ok") is False:
                original_mkdir(self_path, parents=True, exist_ok=True)
                marker.write_text("owned by another process", encoding="utf-8")
                raise FileExistsError("directory appeared concurrently")
            return original_mkdir(self_path, *args, **kwargs)

        with patch.object(Path, "mkdir", racing_mkdir):
            with self.assertRaises(FileExistsError):
                export_tasks(
                    input_path,
                    output_dir,
                    private_root=self.private_root,
                )

        self.assertTrue(output_dir.is_dir())
        self.assertTrue(marker.is_file())
        self.assertEqual(marker.read_text(encoding="utf-8"), "owned by another process")
        self.assertFalse((output_dir / "annotator_a.csv").exists())

    def test_concurrent_empty_directory_collision_preserved(self) -> None:
        pack = _make_pack([_synthetic_item("empty_collision_id")])
        input_path = self._write_pack(pack, "empty_collision_pack.json")
        output_dir = self.private_root / "empty_collision_round"

        original_mkdir = Path.mkdir

        def racing_mkdir(self_path, *args, **kwargs):
            if self_path.resolve() == output_dir.resolve() and kwargs.get("exist_ok") is False:
                original_mkdir(self_path, parents=True, exist_ok=True)
                raise FileExistsError("empty directory appeared concurrently")
            return original_mkdir(self_path, *args, **kwargs)

        with patch.object(Path, "mkdir", racing_mkdir):
            with self.assertRaises(FileExistsError):
                export_tasks(
                    input_path,
                    output_dir,
                    private_root=self.private_root,
                )

        self.assertTrue(output_dir.is_dir())
        self.assertEqual(list(output_dir.iterdir()), [])

    def test_input_hash_uses_single_byte_snapshot(self) -> None:
        pack = _make_pack([_synthetic_item("hash_id")])
        input_path = self._write_pack(pack, "hash_pack.json")
        expected_hash = _sha256_bytes(input_path.read_bytes())
        metadata = export_tasks(
            input_path,
            self.private_root / "hash_round",
            private_root=self.private_root,
        )
        self.assertEqual(metadata["input_sha256"], expected_hash)

    def test_stdout_never_prints_record_content(self) -> None:
        import scripts.export_annotation_tasks as export_module

        secret = "SYNTH_STDOUT_SECRET"
        pack = _make_pack([_synthetic_item("stdout_id", text=secret)])
        input_path = self._write_pack(pack, "stdout_pack.json")
        output_dir = self.private_root / "stdout_round"

        buffer = io.StringIO()
        stdout = sys.stdout
        try:
            sys.stdout = buffer
            with patch.object(export_module, "ROOT", self.repo_root):
                code = main(
                    [
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_dir),
                        "--overlap-rate",
                        "0.2",
                        "--seed",
                        "42",
                    ]
                )
        finally:
            sys.stdout = stdout

        self.assertEqual(code, 0)
        out = buffer.getvalue()
        self.assertNotIn(secret, out)
        self.assertNotIn("stdout_id", out)
        self.assertIn("PILOT_UNANNOTATED", out)
        self.assertIn("n_items=1", out)


if __name__ == "__main__":
    unittest.main()
