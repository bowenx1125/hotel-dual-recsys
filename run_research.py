#!/usr/bin/env python3
"""Autonomous research runner: waves 0–10, resumable, fixture-capable."""
from __future__ import annotations

import argparse
import json
import os
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
        index_artifact(root, "outputs/autonomous/wave0/WAVE0_AUDIT.md", "audit")
        _mark(root, 0, {"ok": True})
        return findings

    if wave == 1:
        meas = build_measurement_v2(root, small_fixture=small_fixture)
        merge_facts(root, "1", meas)
        index_artifact(root, "data/processed/hotel_aspect_quarter_v2.parquet", "panel")
        absa = run_absa_audit(root, verify_only=verify_only)
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
        shots = capture_demo_screenshots(root, skip=verify_only or small_fixture)
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
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root)
    os.environ.setdefault("FYP_DATA_CACHE_ROOT", "/Users/xubosmell/Desktop/FYP_DATA_CACHE")
    os.environ.setdefault("FYP_PRIVATE_DATA_ROOT", "/Users/xubosmell/Desktop/FYP1/data")
    os.environ.setdefault("FYP_PRIVATE_MODEL_ROOT", "/Users/xubosmell/Desktop/FYP1/models")
    if args.small_fixture:
        os.environ["FYP_AUTONOMOUS_OUT"] = "outputs/autonomous/fixtures/out"
        os.environ["FYP_PANEL_V2"] = "outputs/autonomous/fixtures/hotel_aspect_quarter_v2.parquet"
        os.environ["FYP_PEERS_V2"] = "outputs/autonomous/fixtures/geo_reference_sets_v2.parquet"
        os.environ["FYP_PAPER_DIR"] = "outputs/autonomous/fixtures/paper"
        os.environ["FYP_FINALS_DIR"] = "outputs/autonomous/fixtures"
        os.environ["FYP_SMALL_FIXTURE"] = "1"
    init_ledgers(root)
    waves = [args.wave] if args.wave is not None else list(range(args.from_wave, args.to_wave + 1))
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
    atomic_write_text(
        nxt,
        f"# NEXT\n\nLast completed wave in this invocation: {last}.\n"
        f"Resume: `python run_research.py --resume --from-wave {min(last+1,10)}`\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
