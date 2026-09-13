#!/usr/bin/env python3
"""Read-only check for the external assets required by full reproduction.

The command never downloads, modifies, or prints the contents of an asset. It
reports only existence, byte size, and SHA-256 digests so a fresh clone can
fail clearly before a long research run starts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

# These are the local model files used for the current audited reference. The
# model directory also contains small tracked config/tokenizer metadata; these
# two files are the large ignored assets that a clone cannot provide.
MODEL_ASSET_SHA256 = {
    "model.safetensors": "270559fb59fec507f6a105d2c7765af0b61c685670dbbcf52e551c6fa160601e",
    "spm.model": "c679fbf93643d19aab7ee10c0b99e460bdbc02fedf34b92b05af343b4af586fd",
}


def _resolve(root: Path, raw: str | os.PathLike[str]) -> Path:
    candidate = Path(raw).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _safe_ref(root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(root.resolve()))
    except ValueError:
        # Keep external mount/account names out of the report.  The asset key
        # identifies what to provide, while path_sha256 preserves identity.
        return "<external>"


def _path_sha256(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _record(
    root: Path,
    path: Path,
    *,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": _safe_ref(root, path),
        "path_sha256": _path_sha256(path),
        "exists": path.is_file(),
        "required": True,
    }
    if not path.is_file():
        record.update(
            {
                "status": "MISSING",
                "bytes": None,
                "sha256": None,
                "expected_bytes": expected_bytes,
                "expected_sha256": expected_sha256,
            }
        )
        return record

    actual_bytes = path.stat().st_size
    actual_sha = _file_sha256(path)
    bytes_ok = expected_bytes is None or actual_bytes == int(expected_bytes)
    sha_ok = expected_sha256 is None or actual_sha == expected_sha256
    record.update(
        {
            "status": "OK" if bytes_ok and sha_ok else "MISMATCH",
            "bytes": int(actual_bytes),
            "sha256": actual_sha,
            "expected_bytes": expected_bytes,
            "expected_sha256": expected_sha256,
            "matches_expected": bool(bytes_ok and sha_ok),
        }
    )
    return record


def build_report(root: Path, *, cache_root: Path, model_root: Path) -> dict[str, Any]:
    config_path = root / "conf" / "autonomous_research.json"
    if not config_path.is_file():
        return {
            "schema_version": "reproduction-assets-v1",
            "status": "MISSING_CONFIG",
            "config": _safe_ref(root, config_path),
            "assets": {},
        }

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        dataset = config["dataset"]
        relative = str(dataset["relative_path"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {
            "schema_version": "reproduction-assets-v1",
            "status": "INVALID_CONFIG",
            "config": _safe_ref(root, config_path),
            "error_type": type(exc).__name__,
            "assets": {},
        }

    assets = {
        "dataset_csv": _record(
            root,
            cache_root / relative,
            expected_sha256=dataset.get("expected_sha256"),
            expected_bytes=dataset.get("expected_bytes"),
        ),
        "absa_model_weights": _record(
            root,
            model_root / "absa" / "model.safetensors",
            expected_sha256=MODEL_ASSET_SHA256["model.safetensors"],
        ),
        "absa_sentencepiece": _record(
            root,
            model_root / "absa" / "spm.model",
            expected_sha256=MODEL_ASSET_SHA256["spm.model"],
        ),
    }
    valid = all(item["status"] == "OK" for item in assets.values())
    return {
        "schema_version": "reproduction-assets-v1",
        "status": "OK" if valid else "MISSING_OR_MISMATCHED",
        "root": _safe_ref(root, root),
        "config": _safe_ref(root, config_path),
        "effective_paths": {
            "data_cache_root": _safe_ref(root, cache_root),
            "data_cache_root_path_sha256": _path_sha256(cache_root),
            "private_model_root": _safe_ref(root, model_root),
            "private_model_root_path_sha256": _path_sha256(model_root),
        },
        "assets": assets,
        "notes": [
            "Read-only: no download and no file writes.",
            "Only existence, byte size, and SHA-256 are inspected; raw review text is never emitted.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--cache-root", default=None)
    parser.add_argument("--model-root", default=None)
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    cache_root = _resolve(
        root,
        args.cache_root
        or os.environ.get("FYP_DATA_CACHE_ROOT")
        or str(root / "data" / "cache"),
    )
    model_root = _resolve(
        root,
        args.model_root
        or os.environ.get("FYP_PRIVATE_MODEL_ROOT")
        or str(root / "models"),
    )
    report = build_report(root, cache_root=cache_root, model_root=model_root)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
