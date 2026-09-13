#!/usr/bin/env python3
"""Build a research/demo snapshot JSON from quarterly panel + geo peer reference sets."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.recommendation.panel_adapter import build_panel_snapshot  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def read_stable_bytes(path: Path) -> bytes:
    before = sha256_file(path)
    data = path.read_bytes()
    after = sha256_bytes(data)
    if before != after:
        raise RuntimeError(f"input file changed during read: {path.name}")
    return data


def resolve_input_path(raw: str, root: Path) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (root / candidate).resolve()


def resolve_output_path(raw: str, root: Path) -> Path:
    """Absolute output path without resolving the final component (preserves symlinks)."""
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.absolute()


def source_ref(path: Path, root: Path) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        return str(resolved.relative_to(root_resolved))
    except ValueError:
        return resolved.name


def _json_default(obj: Any) -> Any:
    import numpy as np

    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        value = float(obj)
        if value != value:  # NaN
            raise ValueError("snapshot contains non-finite float")
        return value
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    raise TypeError(type(obj))


def publish_json(path: Path, obj: dict, *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        obj,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    ) + "\n"
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        tmp.write_text(payload, encoding="utf-8")
        if path.exists() or path.is_symlink():
            if not overwrite:
                raise FileExistsError(f"output exists: {path.name}")
            os.replace(tmp, path)
        else:
            try:
                os.link(tmp, path)
            except FileExistsError:
                if not overwrite:
                    raise FileExistsError(f"output exists: {path.name}") from None
                os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel", default="data/processed/hotel_aspect_quarter_v2.parquet")
    ap.add_argument("--peers", default="data/processed/geo_reference_sets_v2.parquet")
    ap.add_argument("--config", default="conf/demo.json")
    ap.add_argument("--period", default=None, help="Complete quarter label, e.g. 2017Q2")
    ap.add_argument("--output", default="outputs/demo/research_snapshot.json")
    ap.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file")
    ap.add_argument(
        "--synthetic",
        action="store_true",
        help="Mark snapshot as synthetic/test input (default assumes real panel data)",
    )
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    panel_path = resolve_input_path(args.panel, root)
    peers_path = resolve_input_path(args.peers, root)
    config_path = resolve_input_path(args.config, root)
    output_path = resolve_output_path(args.output, root)

    input_paths = {
        "panel": panel_path,
        "peers": peers_path,
        "config": config_path,
    }

    if output_path.is_symlink():
        print(f"error: output path is a symlink (refusing to write): {output_path.name}", file=sys.stderr)
        return 3

    if output_path.exists() and not args.overwrite:
        print(f"error: output exists (use --overwrite): {output_path.name}", file=sys.stderr)
        return 3

    try:
        config_bytes = read_stable_bytes(config_path)
        cfg = json.loads(config_bytes.decode("utf-8"))
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    actionability_payload: dict | None = None
    actionability_path: Path | None = None
    actionability_bytes: bytes | None = None
    if "actionability" not in cfg:
        act_ref = cfg.get("actionability_config", "conf/actionability.json")
        actionability_path = resolve_input_path(act_ref, root)
        input_paths["actionability"] = actionability_path

    for label, path in input_paths.items():
        if not path.is_file():
            print(f"error: missing {label} file: {path.name}", file=sys.stderr)
            return 2

    output_resolved = output_path.resolve()
    if output_resolved in {p.resolve() for p in input_paths.values()}:
        print("error: output path must not match any input path", file=sys.stderr)
        return 5

    try:
        import pandas as pd
    except ImportError:
        print("error: pandas is required to read parquet inputs", file=sys.stderr)
        return 4

    try:
        panel_bytes = read_stable_bytes(panel_path)
        peers_bytes = read_stable_bytes(peers_path)
        if actionability_path is not None:
            actionability_bytes = read_stable_bytes(actionability_path)
            actionability_payload = json.loads(actionability_bytes.decode("utf-8"))

        panel = pd.read_parquet(io.BytesIO(panel_bytes))
        peers = pd.read_parquet(io.BytesIO(peers_bytes))

        source_metadata = {
            "panel_path": source_ref(panel_path, root),
            "peers_path": source_ref(peers_path, root),
            "config_path": source_ref(config_path, root),
            "panel_sha256": sha256_bytes(panel_bytes),
            "peers_sha256": sha256_bytes(peers_bytes),
            "config_sha256": sha256_bytes(config_bytes),
            "dataset_id": cfg.get("dataset_id", "d1_europe"),
            "synthetic": bool(args.synthetic),
            "scoring_version": cfg.get("policy_version", "panel_adapter_v1"),
        }
        if actionability_path is not None and actionability_bytes is not None:
            source_metadata["actionability_path"] = source_ref(actionability_path, root)
            source_metadata["actionability_sha256"] = sha256_bytes(actionability_bytes)

        snapshot = build_panel_snapshot(
            panel,
            peers,
            cfg,
            period=args.period,
            source_metadata=source_metadata,
            actionability=actionability_payload,
        )
        publish_json(output_path, snapshot, overwrite=args.overwrite)
    except (ValueError, TypeError, RuntimeError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {output_path.name}")
    print(
        "period={period} source_panel={source_panel} in_period={in_period} "
        "absent_period={absent} eligible={eligible} excluded={excluded}".format(
            period=snapshot["period"],
            source_panel=snapshot["n_hotels_source_panel"],
            in_period=snapshot["n_hotels_total"],
            absent=snapshot["absent_selected_period_count"],
            eligible=snapshot["n_eligible_hotels"],
            excluded=snapshot["n_excluded_hotels"],
        )
    )
    print("exclusion_counts=", snapshot["exclusion_counts"])
    print("scoring_version=", snapshot["scoring_version"])
    print("synthetic=", snapshot["synthetic"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
