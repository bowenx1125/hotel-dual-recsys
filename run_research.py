#!/usr/bin/env python3
"""Autonomous research runner: waves 0–10, resumable, fixture-capable."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.autonomous.common import atomic_write_json, load_config, out_dir, panel_v2_path, peers_v2_path, update_state
from src.autonomous.ledger import index_artifact, init_ledgers, merge_facts
from src.autonomous.panel import build_measurement_v2, run_wave0
from src.autonomous.absa import run_absa_audit
from src.autonomous.infer import (
    build_main_peers,
    run_wave2,
    run_wave3,
    run_wave4,
    run_wave5,
    run_wave6,
    run_wave7,
)
from src.autonomous.report import (
    adversarial_review,
    capture_demo_screenshots,
    generate_paper,
    synthetic_estimator_probe,
    write_finals,
)


DEFAULT_REPRODUCTION_OUT = "outputs/autonomous/reproduced"
FIXTURE_REPRODUCTION_OUT = "outputs/autonomous/fixtures/out"


def _resolve_path(root: Path, raw: str | os.PathLike[str]) -> Path:
    """Resolve a user or environment path without changing unrelated env vars."""
    candidate = Path(raw).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _safe_path_ref(root: Path, path: Path) -> str:
    """Return a repo-relative path, or an opaque external marker."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(root.resolve()))
    except ValueError:
        # Do not echo even an external basename: deployments may encode a
        # private account, token, or mount name there.  Asset keys and the
        # path digest retain enough identity for reproducibility checks.
        return "<external>"


def _path_digest(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()


def _asset_record(root: Path, path: Path, *, expected_sha256: str | None = None) -> dict:
    record = {
        "path": _safe_path_ref(root, path),
        "path_sha256": _path_digest(path),
        "exists": path.is_file(),
    }
    if not path.is_file():
        record["bytes"] = None
        record["sha256"] = None
        record["matches_expected"] = False if expected_sha256 else None
        return record
    record["bytes"] = path.stat().st_size
    # This is a binary digest only; no input text is emitted into metadata.
    from src.autonomous.common import sha256_file

    record["sha256"] = sha256_file(path)
    record["matches_expected"] = (
        record["sha256"] == expected_sha256 if expected_sha256 else None
    )
    return record


def _configure_paths(
    root: Path,
    *,
    output_root: str | None,
    small_fixture: bool,
    skip_ui: bool,
) -> Path:
    """Set only project output/data defaults and return the effective output root.

    An explicit ``--output-root`` owns all derived output locations. Existing
    data/model overrides remain valid and are intentionally left untouched.
    """
    env_output = os.environ.get("FYP_AUTONOMOUS_OUT")
    if output_root is not None:
        effective = _resolve_path(root, output_root)
        os.environ["FYP_AUTONOMOUS_OUT"] = str(effective)
        os.environ["FYP_PANEL_V2"] = str(effective / "hotel_aspect_quarter_v2.parquet")
        os.environ["FYP_PEERS_V2"] = str(effective / "geo_reference_sets_v2.parquet")
        os.environ["FYP_PAPER_DIR"] = str(effective / "paper")
    elif small_fixture:
        effective = _resolve_path(root, FIXTURE_REPRODUCTION_OUT)
        os.environ["FYP_AUTONOMOUS_OUT"] = str(effective)
        # Keep the established CI fixture filenames for compatibility. An
        # explicitly selected output root gets fully nested derived files.
        fixture_base = effective.parent
        os.environ["FYP_PANEL_V2"] = str(fixture_base / "hotel_aspect_quarter_v2.parquet")
        os.environ["FYP_PEERS_V2"] = str(fixture_base / "geo_reference_sets_v2.parquet")
        os.environ["FYP_PAPER_DIR"] = str(effective / "paper")
    elif env_output:
        effective = _resolve_path(root, env_output)
        os.environ["FYP_AUTONOMOUS_OUT"] = str(effective)
        # Bind all derived outputs to the selected run root.  A stale
        # FYP_PANEL_V2/FYP_PEERS_V2 from an older run must not redirect this
        # invocation into data/processed; data/model input overrides remain
        # caller-controlled below.
        os.environ["FYP_PANEL_V2"] = str(effective / "hotel_aspect_quarter_v2.parquet")
        os.environ["FYP_PEERS_V2"] = str(effective / "geo_reference_sets_v2.parquet")
        os.environ["FYP_PAPER_DIR"] = str(effective / "paper")
    else:
        effective = _resolve_path(root, DEFAULT_REPRODUCTION_OUT)
        os.environ["FYP_AUTONOMOUS_OUT"] = str(effective)
        os.environ["FYP_PANEL_V2"] = str(effective / "hotel_aspect_quarter_v2.parquet")
        os.environ["FYP_PEERS_V2"] = str(effective / "geo_reference_sets_v2.parquet")
        os.environ["FYP_PAPER_DIR"] = str(effective / "paper")

    os.environ.setdefault("FYP_DATA_CACHE_ROOT", str(root / "data" / "cache"))
    os.environ.setdefault("FYP_PRIVATE_DATA_ROOT", str(root / "data"))
    os.environ.setdefault("FYP_PRIVATE_MODEL_ROOT", str(root / "models"))
    if small_fixture:
        os.environ["FYP_SMALL_FIXTURE"] = "1"
    else:
        # Avoid an inherited fixture marker changing full-run ABSA fallback.
        os.environ.pop("FYP_SMALL_FIXTURE", None)
    if skip_ui:
        os.environ["FYP_SKIP_UI"] = "1"
    else:
        os.environ.pop("FYP_SKIP_UI", None)
    return effective


def _guard_output_root(
    root: Path,
    output_root: Path,
    *,
    small_fixture: bool,
    resume: bool,
    force: bool,
) -> None:
    """Never let a normal run replace an existing scientific FACTS snapshot."""
    protected = {
        (root / "outputs" / "autonomous").resolve(),
        (root / "outputs" / "overnight").resolve(),
        (root / "data" / "processed").resolve(),
        (root / "data" / "processed" / "hotel_aspect_quarter_v2.parquet").resolve(),
        (root / "data" / "processed" / "geo_reference_sets_v2.parquet").resolve(),
    }
    if output_root.resolve() in protected:
        raise RuntimeError(
            f"Refusing protected output root {output_root}; choose a new run directory"
        )
    if output_root.exists() and not output_root.is_dir():
        raise RuntimeError(
            f"Refusing output root that is not a directory: {output_root}"
        )
    facts = output_root / "FACTS.json"
    if force and facts.exists():
        raise RuntimeError(
            f"Refusing --force because {facts} already exists; choose a fresh --output-root"
        )
    if small_fixture:
        return
    if not facts.exists():
        if output_root.exists() and any(output_root.iterdir()) and not resume:
            raise RuntimeError(
                f"Refusing to overwrite non-empty output root {output_root}; choose a fresh --output-root"
            )
        return
    if not resume:
        raise RuntimeError(
            f"Refusing to overwrite existing {facts}; choose a fresh --output-root or use --resume"
        )
    checkpoints = output_root / "checkpoints"
    if not checkpoints.is_dir() or not any(checkpoints.glob("wave*.done.json")):
        raise RuntimeError(
            f"Refusing --resume without checkpoints in {checkpoints}; choose a fresh --output-root"
        )


def _write_reproduction_manifest(
    root: Path,
    output_root: Path,
    cfg: dict,
    *,
    small_fixture: bool,
    verify_only: bool,
    resume: bool,
    skip_ui: bool,
) -> None:
    atomic_write_json(
        output_root / "reproduction_manifest.json",
        _build_reproduction_manifest(
            root,
            output_root,
            cfg,
            small_fixture=small_fixture,
            verify_only=verify_only,
            resume=resume,
            skip_ui=skip_ui,
        ),
    )


def _build_reproduction_manifest(
    root: Path,
    output_root: Path,
    cfg: dict,
    *,
    small_fixture: bool,
    verify_only: bool,
    resume: bool,
    skip_ui: bool,
) -> dict:
    """Build the same identity record used for writing and resume checks."""
    cache_root = _resolve_path(
        root,
        os.environ.get("FYP_DATA_CACHE_ROOT", str(root / "data" / "cache")),
    )
    model_root = _resolve_path(
        root,
        os.environ.get("FYP_PRIVATE_MODEL_ROOT", str(root / "models")),
    )
    dataset_path = cache_root / cfg["dataset"]["relative_path"]
    model_dir = model_root / "absa"
    records = {
        "dataset_csv": _asset_record(
            root,
            dataset_path,
            expected_sha256=cfg["dataset"].get("expected_sha256") if not small_fixture else None,
        ),
        "absa_model_weights": _asset_record(root, model_dir / "model.safetensors"),
        "absa_sentencepiece": _asset_record(root, model_dir / "spm.model"),
    }
    config_path = root / "conf" / "autonomous_research.json"
    from src.autonomous.common import sha256_file

    demo_config_path = root / "conf" / "demo.json"
    actionability_config_path = root / "conf" / "actionability.json"

    def config_record(path: Path) -> dict:
        return {
            "path": _safe_path_ref(root, path),
            "path_sha256": _path_digest(path),
            "sha256": sha256_file(path) if path.is_file() else None,
        }

    return {
        "schema_version": "reproduction-manifest-v1",
        "root": _safe_path_ref(root, root),
        "output_root": _safe_path_ref(root, output_root),
        "output_root_path_sha256": _path_digest(output_root),
        "config_path": _safe_path_ref(root, config_path),
        "config_path_sha256": _path_digest(config_path),
        "config_sha256": sha256_file(config_path) if config_path.is_file() else None,
        "demo_config_path": _safe_path_ref(root, demo_config_path),
        "demo_config_path_sha256": _path_digest(demo_config_path),
        "demo_config_sha256": sha256_file(demo_config_path) if demo_config_path.is_file() else None,
        "actionability_config_path": _safe_path_ref(root, actionability_config_path),
        "actionability_config_path_sha256": _path_digest(actionability_config_path),
        "actionability_config_sha256": (
            sha256_file(actionability_config_path)
            if actionability_config_path.is_file()
            else None
        ),
        "config_inputs": {
            "autonomous_research": config_record(config_path),
            "demo": config_record(demo_config_path),
            "actionability": config_record(actionability_config_path),
        },
        "small_fixture": small_fixture,
        "verify_only": verify_only,
        "resume": resume,
        "skip_ui": skip_ui,
        "effective_paths": {
            "data_cache_root": _safe_path_ref(root, cache_root),
            "data_cache_root_path_sha256": _path_digest(cache_root),
            "private_model_root": _safe_path_ref(root, model_root),
            "private_model_root_path_sha256": _path_digest(model_root),
            "panel_v2": _safe_path_ref(root, panel_v2_path(root)),
            "peers_v2": _safe_path_ref(root, peers_v2_path(root)),
        },
        "assets": records,
        "notes": [
            "Paths outside the repository are represented by opaque markers.",
            "No raw review text or credentials are recorded.",
        ],
    }


def _assert_resume_manifest(
    root: Path,
    output_root: Path,
    cfg: dict,
    *,
    small_fixture: bool,
    verify_only: bool,
    skip_ui: bool,
) -> None:
    manifest_path = output_root / "reproduction_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(
            f"Refusing --resume without {manifest_path}; start a new output root"
        )
    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Refusing --resume with invalid {manifest_path.name}") from exc
    current = _build_reproduction_manifest(
        root,
        output_root,
        cfg,
        small_fixture=small_fixture,
        verify_only=verify_only,
        resume=True,
        skip_ui=skip_ui,
    )
    keys = (
        "schema_version",
        "output_root_path_sha256",
        "config_sha256",
        "demo_config_sha256",
        "actionability_config_sha256",
        "config_inputs",
        "assets",
        "small_fixture",
        "verify_only",
        "skip_ui",
    )
    if any(previous.get(key) != current.get(key) for key in keys):
        raise RuntimeError(
            "Refusing --resume because configuration or input asset fingerprints changed; "
            "start a fresh --output-root"
        )


def _artifact_ref(root: Path, path: Path) -> str:
    """Render an artifact path in the form expected by the ledger."""
    return _safe_path_ref(root, path)


def _resume_command(
    output_root: Path,
    last_wave: int,
    *,
    small_fixture: bool,
    verify_only: bool,
    skip_ui: bool,
) -> str:
    """Build a copyable resume command with the run's mode identity intact."""
    parts = [
        "python",
        "run_research.py",
        "--resume",
        "--from-wave",
        str(min(last_wave + 1, 10)),
        "--output-root",
        str(output_root),
    ]
    if small_fixture:
        parts.append("--small-fixture")
    if verify_only:
        parts.append("--verify-only")
    if skip_ui:
        parts.append("--skip-ui")
    return " ".join(shlex.quote(part) for part in parts)


def _ckpt(root: Path) -> Path:
    p = out_dir(root) / "checkpoints"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _done(root: Path, wave: int) -> bool:
    return (_ckpt(root) / f"wave{wave}.done.json").exists()


def _mark(root: Path, wave: int, payload: dict) -> None:
    atomic_write_json(_ckpt(root) / f"wave{wave}.done.json", payload)


def _load_panel(root: Path):
    import pandas as pd
    path = panel_v2_path(root)
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def run_wave(root: Path, wave: int, *, small_fixture: bool, verify_only: bool, force: bool) -> dict:
    cfg = load_config(root)
    n_shuf = 8 if verify_only else int(cfg["peers"]["n_shuffled_graphs"])
    n_boot = 80 if verify_only else int(cfg["prediction"]["bootstrap_hotel_cluster"])
    n_shuf_pred = 8 if verify_only else int(cfg["prediction"]["n_shuffled_peer_runs"])

    if wave == 0:
        findings = run_wave0(root)
        merge_facts(root, "0", {
            "legacy_reproduced_match": findings.get("legacy_reproduced_match"),
            "legacy_event_count_reproduced": findings.get("legacy_event_count_reproduced"),
            "legacy_event_count_artifact": findings.get("legacy_event_count_artifact"),
            "n_hotel_id": findings.get("n_hotel_id"),
            "n_hotel_name": findings.get("n_hotel_name"),
            "ci_cause": "matplotlib module-level import in run_temporal_feasibility",
        })
        index_artifact(root, _artifact_ref(root, out_dir(root) / "wave0" / "WAVE0_AUDIT.md"), "audit")
        _mark(root, 0, {"ok": True})
        return findings

    if wave == 1:
        meas = build_measurement_v2(root, small_fixture=small_fixture)
        merge_facts(root, "1", meas)
        index_artifact(root, _artifact_ref(root, panel_v2_path(root)), "panel")
        absa = run_absa_audit(root, verify_only=verify_only)
        absa_status = str(absa.get("status") or "")
        if absa_status.startswith("FAILED_"):
            raise RuntimeError(f"Wave1 ABSA failed with status {absa_status}")
        _mark(root, 1, {"ok": True, "measurement_verdict": meas.get("measurement_verdict"), "absa": absa.get("status")})
        return meas

    panel = _load_panel(root)
    peers = build_main_peers(panel, k=10)
    peer_path = peers_v2_path(root)
    peers.to_parquet(peer_path, index=False)

    if wave == 2:
        out = run_wave2(root, panel, peers, verify_only=verify_only)
        _mark(root, 2, out)
        return out
    if wave == 3:
        out = run_wave3(root, panel, n_shuffle=n_shuf)
        _mark(root, 3, out)
        return out
    if wave == 4:
        out = run_wave4(root, panel, peers, n_boot=n_boot, n_shuffle=n_shuf_pred)
        _mark(root, 4, out)
        return out
    if wave == 5:
        import pandas as pd
        evp = out_dir(root) / "wave2" / "strict_events.parquet"
        ev = pd.read_parquet(evp) if evp.exists() else pd.DataFrame()
        out = run_wave5(root, panel, ev, peers)
        _mark(root, 5, out)
        return out
    if wave == 6:
        out = run_wave6(root, panel)
        _mark(root, 6, out)
        return out
    if wave == 7:
        out = run_wave7(root, panel, peers, verify_only=verify_only)
        _mark(root, 7, out)
        return out
    if wave == 8:
        out = generate_paper(root)
        _mark(root, 8, out)
        return out
    if wave == 9:
        out = adversarial_review(root)
        _mark(root, 9, out)
        return out
    if wave == 10:
        syn = synthetic_estimator_probe(cfg["seed"])
        merge_facts(root, "10_synthetic", syn)
        shots = capture_demo_screenshots(
            root,
            # Let the report layer inspect FYP_SKIP_UI so it can distinguish
            # an explicit UI-only skip from verify-only/fixture capture.
            skip=verify_only or small_fixture,
        )
        merge_facts(root, "10_demo", shots)
        write_finals(root)
        snap = {
            "config": cfg,
            "small_fixture": small_fixture,
            "verify_only": verify_only,
            "synthetic": syn,
            "screenshots": shots,
        }
        atomic_write_json(out_dir(root) / "config_snapshot.json", snap)
        _mark(root, 10, {"ok": True, "synthetic": syn})
        update_state(root, wave=10, status="WAVE10_DONE")
        return snap
    raise ValueError(wave)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", type=int, default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--from-wave", type=int, default=0)
    ap.add_argument("--to-wave", type=int, default=10)
    ap.add_argument("--small-fixture", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument(
        "--skip-ui",
        action="store_true",
        help="Skip Wave 10 Playwright screenshots while keeping all scientific waves at full settings.",
    )
    ap.add_argument("--force", action="store_true")
    ap.add_argument(
        "--output-root",
        default=None,
        help=(
            "Directory for this run's FACTS, panels, peers, paper and checkpoints. "
            "Defaults to outputs/autonomous/reproduced for full runs."
        ),
    )
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root).resolve()
    effective_output = _configure_paths(
        root,
        output_root=args.output_root,
        small_fixture=args.small_fixture,
        skip_ui=args.skip_ui,
    )
    _guard_output_root(
        root,
        effective_output,
        small_fixture=args.small_fixture,
        resume=args.resume,
        force=args.force,
    )
    cfg = load_config(root)
    if args.resume:
        _assert_resume_manifest(
            root,
            effective_output,
            cfg,
            small_fixture=args.small_fixture,
            verify_only=args.verify_only,
            skip_ui=args.skip_ui,
        )
    _write_reproduction_manifest(
        root,
        effective_output,
        cfg,
        small_fixture=args.small_fixture,
        verify_only=args.verify_only,
        resume=args.resume,
        skip_ui=args.skip_ui,
    )
    init_ledgers(root)
    waves = [args.wave] if args.wave is not None else list(range(args.from_wave, args.to_wave + 1))
    if not waves:
        raise SystemExit("no waves selected; check --from-wave/--to-wave")
    for w in waves:
        if args.resume and not args.force and _done(root, w):
            print(f"skip wave {w} (checkpoint)", flush=True)
            continue
        print(f"==== WAVE {w} ====", flush=True)
        run_wave(root, w, small_fixture=args.small_fixture, verify_only=args.verify_only, force=args.force)
        print(f"==== WAVE {w} DONE ====", flush=True)
    nxt = out_dir(root) / "NEXT.md"
    last = waves[-1]
    atomic_write_json  # keep import used
    from src.autonomous.common import atomic_write_text
    resume_cmd = _resume_command(
        effective_output,
        last,
        small_fixture=args.small_fixture,
        verify_only=args.verify_only,
        skip_ui=args.skip_ui,
    )
    atomic_write_text(
        nxt,
        f"# NEXT\n\nLast completed wave in this invocation: {last}.\n"
        f"Resume: `{resume_cmd}`\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
