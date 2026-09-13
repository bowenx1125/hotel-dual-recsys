#!/usr/bin/env python3
"""Finalize model annotation with Codex audit (private labels + public aggregate report)."""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import uuid
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.model_annotation import (  # noqa: E402
    ASPECTS,
    SEED,
    _model_family,
    _is_test_model,
    _sha256_bytes,
    BATCH_DEFAULT,
    LABELS,
    PRIVATE_REL,
    PUBLIC_REL,
    AnnotationError,
    _atomic_write_json,
    _load_role_labels,
    _load_round_sample,
    _resolve_private,
    _resolve_public,
    _sha256_file,
    _sha256_json,
    cohen_kappa,
    protocol_hash,
)

FORMULA_SIG_CHARS = "=+-@"
FINAL_SCHEMA = "model_annotation_final_v1"
REPORT_SCHEMA = "model_annotation_final_report_v1"
FINAL_STATUS = "MODEL_AUDITED_REFERENCE"


def _needs_formula_quote(value: str) -> bool:
    if not value:
        return False
    if value[0] in "\t\r\n":
        return True
    stripped = value.lstrip()
    return bool(stripped) and stripped[0] in FORMULA_SIG_CHARS


def _sanitize_csv_field(value: str) -> str:
    if _needs_formula_quote(value):
        return "'" + value
    return value


def _resolve_round_output(path: Path, round_dir: Path) -> Path:
    root = round_dir.resolve()
    cand = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        cand.relative_to(root)
    except ValueError:
        raise AnnotationError("final output must resolve inside round directory") from None
    if cand.exists():
        raise AnnotationError("final output path already exists")
    return cand


def _validate_audit_decision(decision: dict, gate_txt: str) -> None:
    reason = decision.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise AnnotationError("audit reason mandatory")
    final_label = decision.get("final_label")
    if final_label is not None and final_label not in LABELS:
        raise AnnotationError("invalid final_label")
    evidence = decision.get("evidence", "")
    if not isinstance(evidence, str):
        raise AnnotationError("evidence must be string")
    if final_label in (None, "not_about_aspect"):
        if evidence:
            raise AnnotationError("null/not_about_aspect requires empty evidence")
    elif not evidence or evidence not in gate_txt:
        raise AnnotationError("evidence must be exact nonempty substring")


def _write_final_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with tmp.open("x", encoding="utf-8-sig", newline="") as fh:
            fields = ["item_id", "aspect", "text", "label", "status", "reason"]
            writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({k: _sanitize_csv_field(row.get(k, "")) for k in fields})
        os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _cleanup(paths: list[Path]) -> None:
    for p in paths:
        p.unlink(missing_ok=True)


def finalize_round(
    round_dir: Path,
    audit_path: Path,
    *,
    report_path: Path | None = None,
    private_root: Path,
    public_root: Path | None = None,
    batch_size: int = BATCH_DEFAULT,
) -> dict:
    if batch_size < 1:
        raise AnnotationError("batch_size must be >= 1")
    rd = _resolve_private(round_dir, private_root)
    audit_p = _resolve_private(audit_path, private_root)
    final_json_p = _resolve_round_output(rd / "final_labels.json", rd)
    final_csv_p = _resolve_round_output(rd / "final_labels.csv", rd)
    report_p = _resolve_public(Path(report_path), public_root=public_root) if report_path else None

    labels_path = rd / "labels.json"
    audit_queue_path = rd / "audit_queue.json"
    if not labels_path.exists() or not audit_queue_path.exists():
        raise AnnotationError("round missing labels.json or audit_queue.json")

    manifest, sample = _load_round_sample(rd)
    labels_doc = json.loads(labels_path.read_text(encoding="utf-8"))
    audit_queue_doc = json.loads(audit_queue_path.read_text(encoding="utf-8"))
    grok_map, grok_meta = _load_role_labels(rd, "grok", sample, batch_size)
    rev_map, rev_meta = _load_role_labels(rd, "reviewer", sample, batch_size)

    audit_bytes = audit_p.read_bytes()
    audit_doc = json.loads(audit_bytes)
    gm, rm = grok_meta["requested_model"], rev_meta["requested_model"]
    if gm == rm or (_model_family(gm) == _model_family(rm) and not (_is_test_model(gm) and _is_test_model(rm))):
        raise AnnotationError("independent model families required")
    if audit_doc.get("auditor") != "Codex":
        raise AnnotationError("audit auditor must be Codex")
    if audit_doc.get("sample_hash") != sample["sample_hash"]:
        raise AnnotationError("audit sample_hash mismatch")

    queue_ids = {row["item_id"] for row in audit_queue_doc.get("queue", [])}
    decisions = audit_doc.get("decisions")
    if not isinstance(decisions, list):
        raise AnnotationError("audit decisions must be a list")
    decision_by_id: dict[str, dict] = {}
    for dec in decisions:
        if not isinstance(dec, dict):
            raise AnnotationError("invalid audit decision row")
        iid = dec.get("item_id")
        if not iid or iid in decision_by_id:
            raise AnnotationError("audit item_id coverage invalid")
        decision_by_id[iid] = dec
    if set(decision_by_id) != queue_ids:
        raise AnnotationError("audit must cover exact audit_queue IDs once")

    items_by_id = {it["item_id"]: it for it in sample["items"]}
    label_rows = {row["item_id"]: row for row in labels_doc.get("labels", [])}
    if len(label_rows) != len(labels_doc.get("labels", [])) or set(label_rows) != set(items_by_id):
        raise AnnotationError("labels.json item coverage mismatch")

    for iid, row in label_rows.items():
        g, r = grok_map[iid], rev_map[iid]
        expected_status = "provisional" if g["label"] == r["label"] and not g["uncertain"] and not r["uncertain"] else "unresolved"
        if row["grok"] != g or row["reviewer"] != r or row["status"] != expected_status:
            raise AnnotationError("labels.json does not match batch outputs")

    expected_queue = [r["item_id"] for r in labels_doc["labels"] if r["status"] != "provisional"]
    rng = random.Random(SEED)
    for aspect in ASPECTS:
        candidates = [r for r in labels_doc["labels"] if r["aspect"] == aspect and r["status"] == "provisional"]
        rng.shuffle(candidates)
        expected_queue.extend(r["item_id"] for r in candidates[:2])
    if queue_ids != set(expected_queue) or len(audit_queue_doc.get("queue", [])) != len(queue_ids):
        raise AnnotationError("audit queue does not match frozen sampling rule")

    for iid, dec in decision_by_id.items():
        _validate_audit_decision(dec, items_by_id[iid]["gate_txt"])

    final_rows: list[dict[str, Any]] = []
    per_aspect: dict[str, Counter] = defaultdict(Counter)
    final_accepted = final_unresolved = changed_consensus = 0
    disagreement_or_uncertain = provisional_count = 0

    for it in sample["items"]:
        iid = it["item_id"]
        base = label_rows[iid]
        g, r = base["grok"], base["reviewer"]
        raw_same = g["label"] == r["label"]
        uncertain = g.get("uncertain") or r.get("uncertain")
        if not raw_same or uncertain:
            disagreement_or_uncertain += 1
        if base["status"] == "provisional" and not uncertain:
            provisional_count += 1

        if iid in decision_by_id:
            dec = decision_by_id[iid]
            final_label = dec.get("final_label")
            audit_reason = dec["reason"].strip()
            if (
                base["status"] == "provisional"
                and not uncertain
                and final_label != g["label"]
            ):
                changed_consensus += 1
            if final_label is None:
                status = "unresolved"
                final_unresolved += 1
            else:
                status = "accepted_codex"
                final_accepted += 1
                per_aspect[it["aspect"]][final_label] += 1
        else:
            if base["status"] != "provisional" or uncertain:
                raise AnnotationError("non-audited item must be provisional consensus")
            final_label = g["label"]
            status = "accepted_consensus"
            audit_reason = ""
            final_accepted += 1
            per_aspect[it["aspect"]][final_label] += 1

        final_rows.append({
            "item_id": iid,
            "aspect": it["aspect"],
            "final_label": final_label,
            "status": status,
            "audit_reason": audit_reason,
            "audited": iid in decision_by_id,
            "audit_evidence": decision_by_id.get(iid, {}).get("evidence", ""),
            "grok": g,
            "reviewer": r,
            "gate_txt": it["gate_txt"],
        })

    n_items = len(sample["items"])
    ka = [grok_map[i["item_id"]]["label"] for i in sample["items"]]
    kb = [rev_map[i["item_id"]]["label"] for i in sample["items"]]
    raw_agree = sum(1 for a, b in zip(ka, kb) if a == b)
    audit_doc_hash = _sha256_bytes(audit_bytes)
    provenance = {
        "audit_path": str(audit_p.relative_to(private_root.resolve())),
        "audit_doc_hash": audit_doc_hash,
        "source_hash": sample["source_hash"],
        "sample_hash": sample["sample_hash"],
        "protocol_hash": protocol_hash(),
    }
    final_doc = {
        "schema": FINAL_SCHEMA,
        "status": FINAL_STATUS,
        "no_human_gold": True,
        "no_population_accuracy": True,
        "n_items": n_items,
        "requested_models": {
            "grok": grok_meta["requested_model"],
            "reviewer": rev_meta["requested_model"],
        },
        "provenance": provenance,
        "labels": final_rows,
    }
    csv_rows = [
        {
            "item_id": r["item_id"],
            "aspect": r["aspect"],
            "text": r["gate_txt"],
            "label": r["final_label"] or "",
            "status": r["status"],
            "reason": r["audit_reason"],
        }
        for r in final_rows
    ]

    written: list[Path] = []
    try:
        _atomic_write_json(final_json_p, final_doc)
        written.append(final_json_p)
        _write_final_csv(final_csv_p, csv_rows)
        written.append(final_csv_p)
    except Exception:
        _cleanup(written)
        raise

    public = {
        "schema": REPORT_SCHEMA,
        "status": FINAL_STATUS,
        "no_human_gold": True,
        "no_population_accuracy": True,
        "source_hash": sample["source_hash"],
        "sample_hash": sample["sample_hash"],
        "protocol_hash": protocol_hash(),
        "cities_count": manifest.get("cities_count", 0),
        "hotel_count": len(manifest.get("hotels") or []),
        "n_items": n_items,
        "requested_models": final_doc["requested_models"],
        "raw_agreement_rate": raw_agree / n_items if n_items else 0.0,
        "cohen_kappa": cohen_kappa(ka, kb, list(LABELS)),
        "provisional_count": provisional_count,
        "audited_count": len(queue_ids),
        "disagreement_or_uncertain_count": disagreement_or_uncertain,
        "final_accepted_count": final_accepted,
        "final_unresolved_count": final_unresolved,
        "changed_consensus_audit_count": changed_consensus,
        "per_aspect_final_label_counts": {k: dict(v) for k, v in per_aspect.items()},
        "audit_doc_hash": audit_doc_hash,
    }
    if report_p:
        try:
            report_p.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(report_p, public)
        except Exception:
            _cleanup(written)
            raise
    return public


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Finalize model annotation with Codex audit.")
    p.add_argument("--round", required=True, help="Private round directory")
    p.add_argument("--audit", required=True, help="Private Codex audit JSON path")
    p.add_argument("--report", default=None, help="Public aggregate report JSON path")
    p.add_argument("--private-root", default=str(PRIVATE_REL))
    p.add_argument("--batch-size", type=int, default=BATCH_DEFAULT)
    args = p.parse_args(argv)
    private_root = ROOT / Path(args.private_root)
    try:
        pub = finalize_round(
            Path(args.round),
            Path(args.audit),
            report_path=Path(args.report) if args.report else None,
            private_root=private_root,
            batch_size=args.batch_size,
        )
        print(
            f"accepted={pub['final_accepted_count']} "
            f"unresolved={pub['final_unresolved_count']} "
            f"audited={pub['audited_count']}"
        )
    except AnnotationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
