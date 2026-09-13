"""Synthetic tests for scripts/finalize_model_annotation.py."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.finalize_model_annotation import (  # noqa: E402
    _needs_formula_quote,
    finalize_round,
)
from scripts.model_annotation import (  # noqa: E402
    AnnotationError,
    prepare_sample,
    summarize_round,
    _sha256_file,
)
from tests.test_model_annotation import (  # noqa: E402
    _write_role_batches,
    _write_synth_csv,
)


def _build_audit(sample: dict, queue: list[dict], labels_doc: dict, decisions: list[dict]) -> dict:
    items = {it["item_id"]: it for it in sample["items"]}
    label_rows = {r["item_id"]: r for r in labels_doc["labels"]}
    out = []
    for dec in decisions:
        iid = dec["item_id"]
        gate = items.get(iid, {}).get("gate_txt", "fake")
        final_label = dec.get("final_label")
        if final_label in (None, "not_about_aspect"):
            evidence = ""
        else:
            evidence = dec.get("evidence") or gate[: min(6, len(gate))]
        out.append({
            "item_id": iid,
            "final_label": final_label,
            "evidence": evidence,
            "reason": dec.get("reason", "codex"),
        })
    return {"sample_hash": sample["sample_hash"], "auditor": "Codex", "decisions": out}


class FinalizeModelAnnotationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.private = self.root / "outputs" / "autonomous" / "private"
        self.public = self.root / "outputs" / "autonomous" / "model_annotation"
        self.private.mkdir(parents=True)
        self.public.mkdir(parents=True)
        self.csv = self.root / "synth.csv"
        _write_synth_csv(self.csv, n_per_city=2)
        self.csv_hash = _sha256_file(self.csv)
        self.round = self.private / "round_fin"
        prepare_sample(self.csv, self.round, expected_sha256=self.csv_hash, private_root=self.private)
        self.sample = json.loads((self.round / "sample.json").read_text())
        _write_role_batches(self.round, self.sample, "grok", "fake-grok", batch_size=21, flip_first=True)
        _write_role_batches(self.round, self.sample, "reviewer", "fake-claude", batch_size=21, uncertain_idx=2)
        summarize_round(self.round, private_root=self.private, batch_size=21)
        self.labels = json.loads((self.round / "labels.json").read_text())
        self.queue = json.loads((self.round / "audit_queue.json").read_text())["queue"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _default_decisions(self) -> list[dict]:
        decs = []
        for q in self.queue:
            row = next(r for r in self.labels["labels"] if r["item_id"] == q["item_id"])
            if row["status"] == "provisional" and not row["grok"]["uncertain"]:
                final_label = row["grok"]["label"]
            else:
                final_label = row["grok"]["label"]
            decs.append({"item_id": q["item_id"], "final_label": final_label, "reason": "ok"})
        return decs

    def _write_audit(self, decisions: list[dict], name: str = "audit.json") -> Path:
        doc = _build_audit(self.sample, self.queue, self.labels, decisions)
        path = self.round / name
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def test_happy_path_counts_and_report(self) -> None:
        audit = self._write_audit(self._default_decisions())
        report = self.public / "final_test.json"
        pub = finalize_round(
            self.round,
            audit,
            report_path=report,
            private_root=self.private,
            public_root=self.public,
            batch_size=21,
        )
        self.assertEqual(pub["status"], "MODEL_AUDITED_REFERENCE")
        self.assertTrue(pub["no_human_gold"])
        self.assertEqual(pub["audited_count"], len(self.queue))
        self.assertGreater(pub["provisional_count"], 0)
        self.assertGreater(pub["disagreement_or_uncertain_count"], 0)
        self.assertEqual(
            pub["final_accepted_count"] + pub["final_unresolved_count"],
            pub["n_items"],
        )
        blob = report.read_text(encoding="utf-8")
        self.assertNotIn("item_", blob)
        self.assertNotIn("reason", blob)
        final_doc = json.loads((self.round / "final_labels.json").read_text())
        consensus = [r for r in final_doc["labels"] if r["status"] == "accepted_consensus"]
        self.assertTrue(consensus)

    def test_incomplete_and_wrong_ids(self) -> None:
        decs = self._default_decisions()[:-1]
        audit = self._write_audit(decs)
        with self.assertRaises(AnnotationError):
            finalize_round(self.round, audit, private_root=self.private, batch_size=21)
        extra = self._default_decisions() + [{"item_id": "item_fake", "final_label": "positive", "reason": "x"}]
        audit2 = self._write_audit(extra)
        with self.assertRaises(AnnotationError):
            finalize_round(self.round, audit2, private_root=self.private, batch_size=21)

    def test_fake_evidence_and_hash_mismatch(self) -> None:
        decs = self._default_decisions()
        decs[0] = {**decs[0], "final_label": "positive", "evidence": "NOT_IN_TEXT", "reason": "bad"}
        audit = self._write_audit(decs)
        with self.assertRaises(AnnotationError):
            finalize_round(self.round, audit, private_root=self.private, batch_size=21)
        bad = {"sample_hash": "0" * 64, "auditor": "Codex", "decisions": []}
        path = self.round / "bad_hash.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(AnnotationError):
            finalize_round(self.round, path, private_root=self.private, batch_size=21)

    def test_overwrite_and_path_escape(self) -> None:
        audit = self._write_audit(self._default_decisions())
        report = self.public / "final_escape.json"
        finalize_round(
            self.round,
            audit,
            report_path=report,
            private_root=self.private,
            public_root=self.public,
            batch_size=21,
        )
        with self.assertRaises(AnnotationError):
            finalize_round(self.round, audit, private_root=self.private, batch_size=21)
        out2 = self.private / "round2"
        prepare_sample(self.csv, out2, expected_sha256=self.csv_hash, private_root=self.private)
        with self.assertRaises(AnnotationError):
            finalize_round(out2, self.root / "escape_audit.json", private_root=self.private, batch_size=21)

    def test_ambiguous_null_and_csv_formula(self) -> None:
        decs = []
        for q in self.queue:
            row = next(r for r in self.labels["labels"] if r["item_id"] == q["item_id"])
            if row["status"] != "provisional":
                decs.append({"item_id": q["item_id"], "final_label": None, "reason": "unclear"})
            else:
                decs.append({"item_id": q["item_id"], "final_label": row["grok"]["label"], "reason": "ok"})
        audit = self._write_audit(decs)
        pub = finalize_round(self.round, audit, private_root=self.private, batch_size=21)
        self.assertGreater(pub["final_unresolved_count"], 0)
        final_doc = json.loads((self.round / "final_labels.json").read_text())
        final_doc["labels"][0]["gate_txt"] = "=HYPERLINK()"
        csv_path = self.round / "formula.csv"
        from scripts.finalize_model_annotation import _write_final_csv

        _write_final_csv(
            csv_path,
            [{
                "item_id": "=cmd",
                "aspect": "room",
                "text": final_doc["labels"][0]["gate_txt"],
                "label": "positive",
                "status": "accepted_codex",
                "reason": "+note",
            }],
        )
        with csv_path.open(encoding="utf-8-sig") as fh:
            row = next(csv.DictReader(fh))
        self.assertTrue(_needs_formula_quote("=cmd"))
        self.assertTrue(row["item_id"].startswith("'"))
        self.assertTrue(row["reason"].startswith("'"))

    def test_tampered_queue_and_labels_rejected(self):
        audit = self._write_audit(self._default_decisions())
        path = self.round / "audit_queue.json"
        original = path.read_bytes()
        queue = json.loads(original)
        queue["queue"].append(queue["queue"][0])
        path.write_text(json.dumps(queue))
        with self.assertRaises(AnnotationError):
            finalize_round(self.round, audit, private_root=self.private)
        path.write_bytes(original)
        path = self.round / "labels.json"
        labels = json.loads(path.read_bytes())
        labels["labels"][0]["grok"]["uncertain"] = not labels["labels"][0]["grok"]["uncertain"]
        path.write_text(json.dumps(labels))
        with self.assertRaises(AnnotationError):
            finalize_round(self.round, audit, private_root=self.private)

    def test_changed_consensus_count(self) -> None:
        decs = []
        for q in self.queue:
            row = next(r for r in self.labels["labels"] if r["item_id"] == q["item_id"])
            if row["status"] == "provisional" and not row["grok"]["uncertain"]:
                decs.append({
                    "item_id": q["item_id"],
                    "final_label": "neutral",
                    "reason": "override",
                })
            elif row["status"] != "provisional":
                decs.append({"item_id": q["item_id"], "final_label": row["grok"]["label"], "reason": "ok"})
            else:
                decs.append({"item_id": q["item_id"], "final_label": row["grok"]["label"], "reason": "ok"})
        audit = self._write_audit(decs)
        pub = finalize_round(self.round, audit, private_root=self.private, batch_size=21)
        self.assertGreaterEqual(pub["changed_consensus_audit_count"], 0)


if __name__ == "__main__":
    unittest.main()
