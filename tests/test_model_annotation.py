"""Synthetic tests for scripts/model_annotation.py (no real data or model calls)."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.model_annotation import (  # noqa: E402
    GATE_CHARS,
    TIMEOUT_S,
    AnnotationError,
    _acquire_role_lock,
    _parse_agent_stdout,
    _scan_source_bytes,
    _sha256_bytes,
    _sha256_file,
    build_prompt,
    cohen_kappa,
    prepare_sample,
    prompt_hash,
    protocol_hash,
    run_round,
    summarize_round,
    validate_batch,
)
from src.temporal.io_util import load_temporal_config  # noqa: E402

CITIES = ["London", "Paris", "Amsterdam", "Barcelona", "Vienna", "Milan"]
ASPECTS = ["location", "cleanliness", "breakfast", "service", "noise", "room", "value"]

_ASPECT_TOKENS = {
    "room": ("room", "Room"),
    "cleanliness": ("clean", "dirty", "Clean", "Dirty"),
    "service": ("staff", "service", "Service"),
    "location": ("location", "metro", "central", "Location"),
    "noise": ("quiet", "noisy", "noise", "Noisy"),
    "breakfast": ("breakfast", "Breakfast"),
    "value": ("value", "price", "overpriced", "Value"),
}


def _synthetic_label_evidence(it: dict) -> tuple[str, str]:
    gate = it["gate_txt"]
    gate_lower = gate.lower()
    for token in _ASPECT_TOKENS.get(it["aspect"], ()):
        if token.lower() in gate_lower:
            start = gate_lower.index(token.lower())
            return "positive", gate[start : start + len(token)]
    if not it.get("gate_hit", True):
        return "not_about_aspect", ""
    return "positive", gate[: min(8, len(gate))]


def _agent_cli_payload(inner: dict) -> str:
    return json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": json.dumps(inner),
    })


def _write_synth_csv(path: Path, n_per_city: int = 4) -> None:
    rows = []
    rich_pos = (
        "Clean spacious room, comfortable bed, helpful staff, great breakfast buffet, "
        "good value for money, quiet night, central station location."
    )
    rich_neg = (
        "Dirty bathroom, rude service, noisy traffic, far from metro, overpriced small room, "
        "poor breakfast, bad location."
    )
    bland_pos, bland_neg = "Pleasant stay overall.", "Nothing special to report."
    for city in CITIES:
        for i in range(n_per_city):
            pos = rich_pos if i % 2 == 0 else bland_pos
            neg = rich_neg if i % 2 == 0 else bland_neg
            rows.append({
                "Hotel_Address": f"1 Test St {city} United Kingdom",
                "Positive_Review": pos,
                "Negative_Review": neg,
            })
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Hotel_Address", "Positive_Review", "Negative_Review"])
        w.writeheader()
        w.writerows(rows)


def _agent_ok(batch_items: list[dict]) -> str:
    items = []
    for it in batch_items:
        label, ev = _synthetic_label_evidence(it)
        items.append({
            "item_id": it["item_id"],
            "label": label,
            "evidence": ev,
            "uncertain": False,
            "reason": "synthetic",
        })
    return _agent_cli_payload({"items": items})


def _write_role_batches(
    out: Path,
    sample: dict,
    role: str,
    model: str,
    *,
    batch_size: int = 21,
    flip_first: bool = False,
    uncertain_idx: int | None = 1,
) -> None:
    from scripts.model_annotation import _batch_meta

    d = out / "batches" / role
    d.mkdir(parents=True, exist_ok=True)
    items = sample["items"]
    for bi, start in enumerate(range(0, len(items), batch_size)):
        batch = items[start : start + batch_size]
        batch_items = []
        for j, it in enumerate(batch):
            default_lab, ev = _synthetic_label_evidence(it)
            if flip_first and j == 0:
                lab = "negative"
            elif default_lab == "not_about_aspect":
                lab = "not_about_aspect"
            else:
                lab = "positive"
            batch_items.append({
                "item_id": it["item_id"],
                "label": lab,
                "evidence": ev,
                "uncertain": uncertain_idx is not None and j == uncertain_idx,
                "reason": "t",
            })
        doc = {
            "status": "ok",
            "metadata": {
                **_batch_meta(sample, model, role, batch),
                "batch_index": bi,
                "timestamp": "2026-01-01T00:00:00+00:00",
            },
            "items": batch_items,
        }
        (d / f"batch_{bi:04d}.json").write_text(json.dumps(doc), encoding="utf-8")


class ModelAnnotationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.private = self.root / "outputs" / "autonomous" / "private"
        self.private.mkdir(parents=True)
        self.public = self.root / "outputs" / "autonomous" / "model_annotation"
        self.public.mkdir(parents=True)
        self.csv = self.root / "synth.csv"
        _write_synth_csv(self.csv)
        self.csv_hash = _sha256_file(self.csv)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _out(self, name: str = "round1") -> Path:
        return self.private / name

    def test_scan_reproducible_hash_and_gate_txt(self) -> None:
        cfg = load_temporal_config(ROOT)
        data = self.csv.read_bytes()
        h = _sha256_bytes(data)
        a, _, _, _ = _scan_source_bytes(data, cfg, h)
        b, _, _, _ = _scan_source_bytes(data, cfg, h)
        self.assertEqual(_sha256_bytes(json.dumps(a, sort_keys=True).encode()),
                         _sha256_bytes(json.dumps(b, sort_keys=True).encode()))
        self.assertTrue(all(len(i["gate_txt"]) <= GATE_CHARS for i in a))
        self.assertTrue(all("text" not in i for i in a))

    def test_gate_txt_800_chars_in_prompt(self) -> None:
        long_txt = "helpful staff great location " + ("x" * 1200)
        row_csv = self.root / "long.csv"
        with row_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Hotel_Address", "Positive_Review", "Negative_Review"])
            w.writeheader()
            w.writerow({
                "Hotel_Address": "1 Test St London United Kingdom",
                "Positive_Review": long_txt,
                "Negative_Review": "bad",
            })
        out = self._out("long_round")
        prepare_sample(row_csv, out, expected_sha256=_sha256_file(row_csv), private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        hit = next(i for i in sample["items"] if i["gate_hit"] and i["aspect"] == "service")
        self.assertEqual(len(hit["gate_txt"]), GATE_CHARS)
        prompt = build_prompt([hit], role="grok")
        self.assertIn(hit["gate_txt"], prompt)
        self.assertNotIn(long_txt, prompt)

    def test_prepare_manifest_fields(self) -> None:
        out = self._out()
        m = prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        self.assertEqual(m["n_items"], 210)
        self.assertEqual(m["seed"], 42)
        self.assertEqual(m["cities_count"], 6)
        self.assertTrue(m["no_human_gold"])
        self.assertTrue(m["no_population_accuracy"])
        self.assertIn("population_counts", m)
        sample = json.loads((out / "sample.json").read_text())
        self.assertTrue(all("item_" in i["item_id"] for i in sample["items"]))

    def test_prepare_sha_and_overwrite_and_escape(self) -> None:
        out = self._out()
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        with self.assertRaises(AnnotationError):
            prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        with self.assertRaises(AnnotationError):
            prepare_sample(
                self.csv,
                self.root / "outside",
                expected_sha256=self.csv_hash,
                private_root=self.private,
            )
        with self.assertRaises(AnnotationError):
            prepare_sample(self.csv, out, expected_sha256="0" * 64, private_root=self.private)

    def test_prompt_hash_full_template(self) -> None:
        h = prompt_hash("grok")
        self.assertEqual(h, _sha256_bytes(build_prompt([], role="grok").encode()))
        self.assertNotEqual(prompt_hash("grok"), prompt_hash("reviewer"))

    def test_blind_prompt_payload(self) -> None:
        item = {"item_id": "item_x", "aspect": "service", "gate_txt": "helpful staff", "city": "London"}
        p = build_prompt([item], role="grok")
        self.assertIn("DATA only", p)
        self.assertIn("neutral", p)
        self.assertIn("not_about_aspect", p)
        self.assertNotIn("London", p)
        self.assertNotIn("hotel", p.lower())
        self.assertIn("helpful staff", p)
        self.assertIn('"item_id":"opaque_id"', p)

    def test_validate_batch_rules(self) -> None:
        items = [{"item_id": "a", "gate_txt": "clean room"}, {"item_id": "b", "gate_txt": "no mention"}]
        ok = {"items": [
            {"item_id": "a", "label": "positive", "evidence": "clean", "uncertain": False, "reason": ""},
            {"item_id": "b", "label": "not_about_aspect", "evidence": "", "uncertain": False, "reason": ""},
        ]}
        validate_batch(items, {"a", "b"}, ok)
        with self.assertRaises(AnnotationError):
            validate_batch(items, {"a", "b"}, {"items": ok["items"][:1]})
        with self.assertRaises(AnnotationError):
            validate_batch(items, {"a", "b"}, {"items": [
                {"item_id": "a", "label": "positive", "evidence": "missing", "uncertain": False, "reason": ""},
                {"item_id": "b", "label": "neutral", "evidence": "x", "uncertain": False, "reason": ""},
            ]})

    def test_parse_agent_stdout(self) -> None:
        inner = {"items": []}
        raw = _agent_cli_payload(inner)
        self.assertEqual(_parse_agent_stdout(raw)[0], inner)
        fenced = _agent_cli_payload({"items": []})
        fenced_obj = json.loads(fenced)
        fenced_obj["result"] = "```json\n" + json.dumps(inner) + "\n```"
        self.assertEqual(_parse_agent_stdout(json.dumps(fenced_obj))[0], inner)
        err = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "result": "{}",
        })
        with self.assertRaises(AnnotationError):
            _parse_agent_stdout(err)
        bad_type = json.dumps({
            "type": "error",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(inner),
        })
        with self.assertRaises(AnnotationError):
            _parse_agent_stdout(bad_type)

    def test_workspace_cli_json_location(self) -> None:
        from scripts.model_annotation import ROLE_STANDARD, _write_workspace

        ws = self.root / "ws"
        _write_workspace(ws)
        agents = ws / "AGENTS.md"
        self.assertTrue(agents.exists())
        self.assertEqual(agents.read_text(encoding="utf-8").strip(), ROLE_STANDARD)
        cli = ws / ".cursor" / "cli.json"
        self.assertTrue(cli.exists())
        self.assertFalse((ws / "cli.json").exists())
        deny = json.loads(cli.read_text())["permissions"]["deny"]
        self.assertIn("Read(**)", deny)
        self.assertIn("Write(**)", deny)
        self.assertIn("Shell(*)", deny)
        self.assertIn("Shell(**)", deny)
        self.assertIn("Mcp(*:*)", deny)
        self.assertIn("WebFetch(*)", deny)

    def test_exclusive_lock_ownership(self) -> None:
        lock = self.root / ".lock_test"
        self.assertTrue(_acquire_role_lock(lock))
        with self.assertRaises(AnnotationError):
            _acquire_role_lock(lock)
        lock.unlink()
        self.assertTrue(_acquire_role_lock(lock))

    def test_run_and_resume(self) -> None:
        out = self._out("round_run")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        calls = {"n": 0}

        def fake_invoke(cmd, **kw):
            calls["n"] += 1
            bi = int(Path(cmd[cmd.index("--workspace") + 1]).name.split("_")[-1])
            bs = 21
            batch = sample["items"][bi * bs : (bi + 1) * bs]
            return subprocess.CompletedProcess(cmd, 0, stdout=_agent_ok(batch), stderr="")

        run_round(
            out,
            model="fake-grok",
            role="grok",
            agent_bin="agent",
            batch_size=21,
            private_root=self.private,
            invoke=fake_invoke,
        )
        first = calls["n"]
        run_round(
            out,
            model="fake-grok",
            role="grok",
            agent_bin="agent",
            batch_size=21,
            private_root=self.private,
            invoke=fake_invoke,
        )
        self.assertEqual(calls["n"], first)
        raw_files = list((out / "batches" / "grok").glob("batch_*.raw.*.json"))
        self.assertTrue(raw_files)
        meta = json.loads((out / "batches" / "grok" / "batch_0000.json").read_text())["metadata"]
        self.assertEqual(meta["requested_model"], "fake-grok")
        self.assertIn("batch_prompt_hash", meta)
        self.assertIn("batch_item_ids", meta)

    def test_run_resume_metadata_mismatch(self) -> None:
        out = self._out("round_mm")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        batch = sample["items"][:21]
        path = out / "batches" / "grok" / "batch_0000.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "status": "ok",
            "metadata": {
                "source_hash": "bad",
                "sample_hash": sample["sample_hash"],
                "protocol_hash": protocol_hash(),
                "prompt_template_hash": prompt_hash("grok"),
                "batch_prompt_hash": "x",
                "batch_size": 21,
                "batch_item_ids": [i["item_id"] for i in batch],
                "requested_model": "fake-grok",
                "role": "grok",
                "schema": "model_annotation_sample_v1",
            },
            "items": [],
        }), encoding="utf-8")

        def fake_invoke(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, stdout=_agent_ok(batch), stderr="")

        with self.assertRaises(AnnotationError):
            run_round(
                out,
                model="fake-grok",
                role="grok",
                agent_bin="agent",
                batch_size=21,
                private_root=self.private,
                invoke=fake_invoke,
            )

    def test_run_batch_size_change_fails(self) -> None:
        out = self._out("round_bs")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        _write_role_batches(out, sample, "grok", "fake-grok", batch_size=21)
        _write_role_batches(out, sample, "reviewer", "fake-claude", batch_size=21)
        with self.assertRaises(AnnotationError):
            summarize_round(out, private_root=self.private, batch_size=10)

    def test_summarize_tampered_evidence_fails(self) -> None:
        out = self._out("round_sum_bad")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        _write_role_batches(out, sample, "grok", "fake-grok")
        _write_role_batches(out, sample, "reviewer", "fake-claude")
        bad = out / "batches" / "grok" / "batch_0001.json"
        doc = json.loads(bad.read_text())
        doc["items"][0]["evidence"] = "tampered"
        bad.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(AnnotationError):
            summarize_round(out, private_root=self.private, batch_size=21)

    def test_summarize_missing_extra_duplicate_batches(self) -> None:
        out = self._out("round_med")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        _write_role_batches(out, sample, "grok", "fake-grok")
        _write_role_batches(out, sample, "reviewer", "fake-claude")
        missing = out / "batches" / "grok" / "batch_0005.json"
        missing.unlink()
        with self.assertRaises(AnnotationError):
            summarize_round(out, private_root=self.private, batch_size=21)
        _write_role_batches(out, sample, "grok", "fake-grok")
        (out / "batches" / "grok" / "batch_9999.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(AnnotationError):
            summarize_round(out, private_root=self.private, batch_size=21)
        (out / "batches" / "grok" / "batch_9999.json").unlink(missing_ok=True)
        _write_role_batches(out, sample, "grok", "fake-grok")
        dup = out / "batches" / "grok" / "batch_0001.json"
        doc = json.loads(dup.read_text())
        doc["items"].append(doc["items"][0])
        dup.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(AnnotationError):
            summarize_round(out, private_root=self.private, batch_size=21)

    def test_summarize_math_uncertain_and_section(self) -> None:
        out = self._out("round_sum")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        _write_role_batches(out, sample, "grok", "fake-grok", uncertain_idx=1)
        _write_role_batches(out, sample, "reviewer", "fake-claude", uncertain_idx=None)
        report = self.public / "report1.json"
        pub = summarize_round(
            out,
            report_path=report,
            private_root=self.private,
            public_root=self.public,
            batch_size=21,
        )
        self.assertGreater(pub["raw_agreement_rate"], pub["provisional_agreement_rate"])
        self.assertIn("grok_vs_section", pub["weak_section_agreement"])
        self.assertIn("reviewer_vs_section", pub["weak_section_agreement"])
        self.assertIn("consensus_vs_section", pub["weak_section_agreement"])
        cons = pub["weak_section_agreement"]["consensus_vs_section"]
        self.assertLessEqual(cons["n_match"], cons["n_provisional_gate_hit"])
        self.assertIsNotNone(cons["coverage"])
        blob = report.read_text()
        self.assertNotIn("item_", blob)
        self.assertNotIn("reason", blob)
        self.assertIn("fake-grok", blob)
        labels = json.loads((out / "labels.json").read_text())
        self.assertGreater(labels["n_items"], 0)
        with self.assertRaises(AnnotationError):
            summarize_round(out, private_root=self.private, batch_size=21)

    def test_summarize_duplicate_same_model_fails(self) -> None:
        out = self._out("round_dup_model")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        _write_role_batches(out, sample, "grok", "same-model")
        _write_role_batches(out, sample, "reviewer", "same-model")
        with self.assertRaises(AnnotationError):
            summarize_round(out, private_root=self.private, batch_size=21)

    def test_cohen_kappa_undefined(self) -> None:
        self.assertIsNone(cohen_kappa([], [], ["a", "b"]))
        self.assertIsNone(cohen_kappa(["a", "a"], ["a", "a"], ["a"]))
        self.assertAlmostEqual(cohen_kappa(["a", "a"], ["a", "b"], ["a", "b"]), 0.0)

    def test_public_path_escape_and_existing(self) -> None:
        out = self._out("round_pub")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)
        sample = json.loads((out / "sample.json").read_text())
        _write_role_batches(out, sample, "grok", "fake-grok")
        _write_role_batches(out, sample, "reviewer", "fake-claude")
        with self.assertRaises(AnnotationError):
            summarize_round(
                out,
                report_path=self.root / "escape.json",
                private_root=self.private,
                public_root=self.public,
                batch_size=21,
            )
        report = self.public / "report2.json"
        summarize_round(
            out,
            report_path=report,
            private_root=self.private,
            public_root=self.public,
            batch_size=21,
        )
        with self.assertRaises(AnnotationError):
            summarize_round(
                out,
                report_path=report,
                private_root=self.private,
                public_root=self.public,
                batch_size=21,
            )

    def test_role_lock_cleanup(self) -> None:
        out = self._out("round_lock")
        prepare_sample(self.csv, out, expected_sha256=self.csv_hash, private_root=self.private)

        def boom(cmd, **kw):
            raise AnnotationError("fail")

        with self.assertRaises(AnnotationError):
            run_round(out, model="fake-grok", role="grok", agent_bin="agent", private_root=self.private, invoke=boom)
        self.assertFalse((out / ".lock_grok").exists())

    def test_timeout_safe_error(self) -> None:
        tiny = self.root / "tiny.csv"
        with tiny.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Hotel_Address", "Positive_Review", "Negative_Review"])
            w.writeheader()
            w.writerow({
                "Hotel_Address": "1 Test St London United Kingdom",
                "Positive_Review": "helpful staff clean room great location",
                "Negative_Review": "noisy bad service",
            })
        out = self._out("round_timeout")
        prepare_sample(tiny, out, expected_sha256=_sha256_file(tiny), private_root=self.private)

        def timeout_invoke(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, TIMEOUT_S)

        with self.assertRaises(AnnotationError) as ctx:
            run_round(
                out,
                model="fake-grok",
                role="grok",
                agent_bin="agent",
                batch_size=1000,
                private_root=self.private,
                invoke=timeout_invoke,
            )
        self.assertNotIn("helpful", str(ctx.exception).lower())
        self.assertIn("timeout", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
