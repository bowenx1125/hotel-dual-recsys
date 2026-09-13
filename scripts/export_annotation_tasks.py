#!/usr/bin/env python3
"""Export blinded human annotation CSV packs from a private ABSA sample (stdlib only)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REL = Path("outputs/autonomous/private")

CSV_COLUMNS = ["item_id", "city", "aspect", "text", "label", "notes"]
ALLOWED_LABELS = ["positive", "negative", "neutral", "not_about_aspect"]
REQUIRED_ITEM_FIELDS = ("item_id", "city", "aspect", "text")
FORMULA_SIG_CHARS = "=+-@"
FORMULA_INJECTION_NOTE = (
    "CSV string fields are prefixed with a single quote when the first significant "
    "character is =, +, -, or @, or when the value begins with tab/CR/LF. "
    "The source JSON input file is never modified."
)
LIMITATION_NOTE = (
    "Pilot export only: uses the existing private pack without broadening coverage "
    "or independently verifying provenance or weak labels. "
    "This utility does not compute gold accuracy."
)
ID_STRATEGY = (
    "exported item_id is the literal prefix 'item_' followed by the lowercase "
    "hex SHA-256 digest of the UTF-8 string formed by joining metadata "
    "input_sha256, a single NUL byte (U+0000), and the source pack item's "
    "original item_id. A trusted local importer can recompute each exported "
    "item_id from the preserved source pack and metadata input_sha256 without "
    "a per-item crosswalk file."
)


class ExportError(Exception):
    """Export failed; message must not contain record text or identifiers."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _opaque_export_item_id(input_sha256: str, source_item_id: str) -> str:
    payload = input_sha256.encode("utf-8") + b"\0" + source_item_id.encode("utf-8")
    return f"item_{hashlib.sha256(payload).hexdigest()}"


def _opaque_ids_for_items(input_sha256: str, items: list[dict]) -> dict[str, str]:
    opaque_by_source: dict[str, str] = {}
    seen_opaque: dict[str, str] = {}
    for item in items:
        source_id = item["item_id"]
        opaque_id = _opaque_export_item_id(input_sha256, source_id)
        prior_source = seen_opaque.get(opaque_id)
        if prior_source is not None and prior_source != source_id:
            raise ExportError("opaque item_id collision detected")
        seen_opaque[opaque_id] = source_id
        opaque_by_source[source_id] = opaque_id
    return opaque_by_source


def _resolve_within_private(path: Path, private_root: Path) -> Path:
    private_resolved = private_root.resolve()
    if not path.is_absolute():
        candidate = (ROOT / path).resolve()
    else:
        candidate = path.resolve()
    try:
        candidate.relative_to(private_resolved)
    except ValueError:
        raise ExportError("path must resolve inside the private annotation root") from None
    return candidate


def _needs_formula_quote(value: str) -> bool:
    if not value:
        return False
    if value[0] in "\t\r\n":
        return True
    stripped = value.lstrip()
    if not stripped:
        return False
    return stripped[0] in FORMULA_SIG_CHARS


def _sanitize_csv_field(value: str) -> str:
    if _needs_formula_quote(value):
        return "'" + value
    return value


def _validate_overlap_rate(overlap_rate: float) -> None:
    if math.isnan(overlap_rate) or overlap_rate < 0.0 or overlap_rate > 1.0:
        raise ExportError("overlap_rate must be a number in [0, 1]")


def _load_and_validate_pack(raw: bytes) -> tuple[dict, list[dict]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise ExportError("input is not valid UTF-8 JSON") from None
    except json.JSONDecodeError:
        raise ExportError("input is not valid UTF-8 JSON") from None

    if not isinstance(payload, dict):
        raise ExportError("input must be a JSON object")

    if payload.get("schema") != "human_absa_pack_v1":
        raise ExportError("unsupported input schema")

    if payload.get("HUMAN_VALIDATION_REQUIRED") is not True:
        raise ExportError("HUMAN_VALIDATION_REQUIRED must be true")

    items = payload.get("items")
    if not isinstance(items, list):
        raise ExportError("items must be a list")

    validated: list[dict] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ExportError(f"item at index {index} must be an object")

        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                raise ExportError(f"item at index {index} missing required field")
            if not isinstance(item[field], str):
                raise ExportError(f"item at index {index} has invalid field type")

        hotel_id = item.get("hotel_id")
        if hotel_id is not None and not isinstance(hotel_id, str):
            raise ExportError(f"item at index {index} has invalid field type")

        item_id = item["item_id"]
        text = item["text"]
        if not item_id.strip():
            raise ExportError(f"item at index {index} has empty item_id")
        if not text.strip():
            raise ExportError(f"item at index {index} has empty text")
        if item_id in seen_ids:
            raise ExportError(f"duplicate item_id at index {index}")
        seen_ids.add(item_id)

        normalized = {field: item[field] for field in REQUIRED_ITEM_FIELDS}
        if isinstance(hotel_id, str):
            normalized["hotel_id"] = hotel_id
        validated.append(normalized)

    return payload, validated


def _row_from_item(item: dict, opaque_item_id: str) -> dict[str, str]:
    return {
        "item_id": opaque_item_id,
        "city": item["city"],
        "aspect": item["aspect"],
        "text": item["text"],
        "label": "",
        "notes": "",
    }


def _write_csv(path: Path, rows: list[dict[str, str]], created_files: list[Path]) -> None:
    handle = path.open("x", encoding="utf-8-sig", newline="")
    created_files.append(path)
    try:
        writer = csv.DictWriter(
            handle,
            fieldnames=CSV_COLUMNS,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {column: _sanitize_csv_field(row.get(column, "")) for column in CSV_COLUMNS}
            )
    finally:
        handle.close()


def _shuffle_items(items: list[dict], seed: int) -> list[dict]:
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    return shuffled


def _select_overlap(items: list[dict], overlap_rate: float, seed: int) -> list[dict]:
    n_overlap = math.ceil(len(items) * overlap_rate)
    if n_overlap <= 0:
        return []
    indices = list(range(len(items)))
    random.Random(seed + 1).shuffle(indices)
    chosen = [items[i] for i in indices[:n_overlap]]
    return _shuffle_items(chosen, seed + 2)


def _cleanup_output(output_dir: Path, created_files: list[Path], created_output: bool) -> None:
    for path in created_files:
        try:
            path.unlink()
        except OSError:
            pass
    if created_output:
        try:
            output_dir.rmdir()
        except OSError:
            pass


def export_tasks(
    input_path: Path | str,
    output_dir: Path | str,
    *,
    private_root: Path | str,
    overlap_rate: float = 0.2,
    seed: int = 42,
) -> dict:
    """Validate input, write blinded CSV packs and metadata; return metadata dict."""
    private_root_path = Path(private_root)
    resolved_input = _resolve_within_private(Path(input_path), private_root_path)
    resolved_output = _resolve_within_private(Path(output_dir), private_root_path)

    if resolved_output.exists():
        raise ExportError("output directory already exists")

    _validate_overlap_rate(overlap_rate)

    try:
        input_bytes = resolved_input.read_bytes()
    except OSError as exc:
        raise ExportError("unable to read input file") from exc

    input_sha256 = _sha256_bytes(input_bytes)
    _, items = _load_and_validate_pack(input_bytes)
    opaque_ids = _opaque_ids_for_items(input_sha256, items)

    rows_a = [
        _row_from_item(item, opaque_ids[item["item_id"]])
        for item in _shuffle_items(items, seed)
    ]
    overlap_items = _select_overlap(items, overlap_rate, seed)
    rows_b = [
        _row_from_item(item, opaque_ids[item["item_id"]]) for item in overlap_items
    ]

    n_items = len(items)
    n_overlap = len(rows_b)

    city_counts = dict(Counter(item["city"] for item in items))
    aspect_counts = dict(Counter(item["aspect"] for item in items))
    hotel_ids = {item["hotel_id"] for item in items if item.get("hotel_id")}
    unique_hotel_count = len(hotel_ids)

    created_files: list[Path] = []
    created_output = False
    try:
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        resolved_output.mkdir(parents=False, exist_ok=False)
        created_output = True

        path_a = resolved_output / "annotator_a.csv"
        path_b = resolved_output / "annotator_b.csv"
        path_meta = resolved_output / "metadata.json"

        _write_csv(path_a, rows_a, created_files)
        _write_csv(path_b, rows_b, created_files)

        metadata = {
            "input_sha256": input_sha256,
            "annotator_a_sha256": _sha256_file(path_a),
            "annotator_b_sha256": _sha256_file(path_b),
            "n_items": n_items,
            "n_overlap": n_overlap,
            "seed": seed,
            "overlap_rate": overlap_rate,
            "city_counts": city_counts,
            "aspect_counts": aspect_counts,
            "unique_hotel_count": unique_hotel_count,
            "columns": CSV_COLUMNS,
            "allowed_labels": ALLOWED_LABELS,
            "status": "PILOT_UNANNOTATED",
            "source_provenance": "existing_pack_not_independently_verified",
            "no_gold_accuracy": True,
            "formula_injection_mitigation": FORMULA_INJECTION_NOTE,
            "limitations": LIMITATION_NOTE,
            "id_strategy": ID_STRATEGY,
        }

        meta_handle = path_meta.open("x", encoding="utf-8")
        created_files.append(path_meta)
        try:
            json.dump(metadata, meta_handle, indent=2, ensure_ascii=False)
            meta_handle.write("\n")
        finally:
            meta_handle.close()
    except Exception:
        _cleanup_output(resolved_output, created_files, created_output)
        raise

    return metadata


def _default_output_dir(private_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return private_root / "annotation_rounds" / stamp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export blinded human annotation CSV packs (pilot utility)."
    )
    parser.add_argument(
        "--input",
        default=str(PRIVATE_REL / "human_annotation_pack.json"),
        help="Input pack JSON under outputs/autonomous/private",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory under outputs/autonomous/private (must not exist)",
    )
    parser.add_argument("--overlap-rate", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    private_root = ROOT / PRIVATE_REL
    try:
        input_path = _resolve_within_private(Path(args.input), private_root)
        if args.output is None:
            output_dir = _default_output_dir(private_root)
            output_dir = _resolve_within_private(output_dir, private_root)
        else:
            output_dir = _resolve_within_private(Path(args.output), private_root)

        metadata = export_tasks(
            input_path,
            output_dir,
            private_root=private_root,
            overlap_rate=args.overlap_rate,
            seed=args.seed,
        )
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("error: unable to write output files", file=sys.stderr)
        return 1

    print(f"n_items={metadata['n_items']}")
    print(f"n_overlap={metadata['n_overlap']}")
    print(f"annotator_a={output_dir / 'annotator_a.csv'}")
    print(f"annotator_b={output_dir / 'annotator_b.csv'}")
    print(f"metadata={output_dir / 'metadata.json'}")
    print("status=PILOT_UNANNOTATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
