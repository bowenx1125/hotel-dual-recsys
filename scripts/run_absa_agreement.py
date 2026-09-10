#!/usr/bin/env python3
"""Offline ABSA vs weak section labels. Never gold accuracy. No git-tracked text.

Designed to run under FYP1/.venv-absa (transformers+torch). Avoids pandas so the
Anaconda ABI-broken scientific stack is not required.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.temporal.aspect_gate import gate_aspects, is_placeholder
from src.temporal.geo_parse import parse_city_country
from src.temporal.io_util import load_temporal_config, resolve_europe_csv


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def cohen_kappa(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    idx = {l: i for i, l in enumerate(labels)}
    k = len(labels)
    cm = [[0.0] * k for _ in range(k)]
    n = 0.0
    for a, b in zip(y_true, y_pred):
        if a not in idx or b not in idx:
            continue
        cm[idx[a]][idx[b]] += 1
        n += 1
    if n == 0:
        return float("nan")
    po = sum(cm[i][i] for i in range(k)) / n
    row = [sum(cm[i]) for i in range(k)]
    col = [sum(cm[i][j] for i in range(k)) for j in range(k)]
    pe = sum(row[i] * col[i] for i in range(k)) / (n * n)
    if pe >= 1:
        return 1.0 if po >= 1 else 0.0
    return float((po - pe) / (1 - pe))


def sample_pairs(csv_path: Path, cfg: dict, target: int = 2800) -> list[dict]:
    pos_ph = cfg["placeholders"]["positive"]
    neg_ph = cfg["placeholders"]["negative"]
    buckets: dict[tuple, list] = defaultdict(list)
    cap_per = 80
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            city, _ = parse_city_country(row.get("Hotel_Address") or "")
            if not city:
                continue
            pos = row.get("Positive_Review") or ""
            neg = row.get("Negative_Review") or ""
            if not is_placeholder(pos, pos_ph):
                for a in gate_aspects(pos):
                    key = (city, a, "positive")
                    if len(buckets[key]) < cap_per:
                        buckets[key].append(
                            {"city": city, "aspect": a, "section": "positive", "text": pos[:700]}
                        )
            if not is_placeholder(neg, neg_ph):
                for a in gate_aspects(neg):
                    key = (city, a, "negative")
                    if len(buckets[key]) < cap_per:
                        buckets[key].append(
                            {"city": city, "aspect": a, "section": "negative", "text": neg[:700]}
                        )
            if i % 100000 == 0:
                n = sum(len(v) for v in buckets.values())
                print(f"  sample 已完成/总数/失败数 = {i}/515738/0 buckets={n}", flush=True)
    items = []
    for lst in buckets.values():
        items.extend(lst)
    items.sort(
        key=lambda d: hashlib.sha1(
            f"{d['city']}|{d['aspect']}|{d['section']}|{d['text'][:40]}".encode()
        ).hexdigest()
    )
    return items[:target]


def main() -> int:
    cfg = load_temporal_config(ROOT)
    csv_path = resolve_europe_csv(cfg)
    model_dir = Path(os.environ.get("FYP_PRIVATE_MODEL_ROOT", "/Users/xubosmell/Desktop/FYP1/models")) / "absa"
    out_dir = ROOT / "outputs" / "autonomous" / "wave1"
    private = ROOT / "outputs" / "autonomous" / "private"
    out_dir.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)

    if not (model_dir / "model.safetensors").exists():
        _atomic_write_json(
            out_dir / "absa_audit.json",
            {
                "attempted": True,
                "never_gold_accuracy": True,
                "HUMAN_VALIDATION_REQUIRED": True,
                "status": "SKIPPED_NO_LOCAL_WEIGHTS",
                "model_dir": str(model_dir),
            },
        )
        print("SKIPPED_NO_LOCAL_WEIGHTS", file=sys.stderr)
        return 2

    print(f"Sampling pairs from {csv_path}", flush=True)
    pairs = sample_pairs(csv_path, cfg, 2800)
    print(f"  sampled {len(pairs)} pairs", flush=True)
    _atomic_write_json(
        private / "absa_sample_meta.json",
        {
            "n": len(pairs),
            "cities": sorted({p["city"] for p in pairs}),
            "aspects": sorted({p["aspect"] for p in pairs}),
        },
    )

    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch

    tok = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir), local_files_only=True)
    model.eval()
    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    model.to(device)
    id2lab = {int(i): str(l).lower() for i, l in model.config.id2label.items()}

    y_weak: list[str] = []
    y_pred: list[str] = []
    confs: list[float] = []
    aspects: list[str] = []
    cities: list[str] = []
    bs = 16
    n_fail = 0
    with torch.no_grad():
        for i in range(0, len(pairs), bs):
            batch = pairs[i : i + bs]
            texts = [p["text"] for p in batch]
            asps = [p["aspect"] for p in batch]
            try:
                inp = tok(texts, asps, return_tensors="pt", truncation=True, padding=True, max_length=256)
                inp = {k: v.to(device) for k, v in inp.items()}
                probs = torch.softmax(model(**inp).logits, dim=1)
                idx = probs.argmax(dim=1)
                for j, p in enumerate(batch):
                    lab = id2lab.get(int(idx[j]), "neutral")
                    if lab.startswith("pos"):
                        pred = "positive"
                    elif lab.startswith("neg"):
                        pred = "negative"
                    else:
                        pred = "neutral"
                    y_pred.append(pred)
                    y_weak.append("positive" if p["section"] == "positive" else "negative")
                    confs.append(float(probs[j, int(idx[j])]))
                    aspects.append(p["aspect"])
                    cities.append(p["city"])
            except Exception as e:
                n_fail += len(batch)
                print(f"  batch fail at {i}: {type(e).__name__}: {e}", flush=True)
            done = min(i + bs, len(pairs))
            if done % 160 == 0 or done == len(pairs):
                print(f"  ABSA 已完成/总数/失败数 = {done}/{len(pairs)}/{n_fail}", flush=True)

    n = len(y_pred)
    agree = (sum(a == b for a, b in zip(y_pred, y_weak)) / n) if n else float("nan")
    kappa = cohen_kappa(y_weak, y_pred, ["positive", "negative", "neutral"])
    f1s: dict[str, float] = {}
    for lab in ("positive", "negative"):
        tp = sum((p == lab and w == lab) for p, w in zip(y_pred, y_weak))
        fp = sum((p == lab and w != lab) for p, w in zip(y_pred, y_weak))
        fn = sum((p != lab and w == lab) for p, w in zip(y_pred, y_weak))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s[lab] = 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)
    per_asp: dict[str, float] = {}
    per_city: dict[str, float] = {}
    for a in sorted(set(aspects)):
        idx_a = [j for j, x in enumerate(aspects) if x == a]
        per_asp[a] = sum(y_pred[j] == y_weak[j] for j in idx_a) / len(idx_a)
    for c in sorted(set(cities)):
        idx_c = [j for j, x in enumerate(cities) if x == c]
        per_city[c] = sum(y_pred[j] == y_weak[j] for j in idx_c) / len(idx_c)
    high_dis = sum(
        (p != w and conf >= 0.8) for p, w, conf in zip(y_pred, y_weak, confs)
    )
    out = {
        "attempted": True,
        "never_gold_accuracy": True,
        "HUMAN_VALIDATION_REQUIRED": True,
        "status": "RAN",
        "n_pairs": int(n),
        "agreement_vs_weak_section_label": agree,
        "cohens_kappa_vs_weak": kappa,
        "weak_reference_f1": f1s,
        "per_aspect_agreement": per_asp,
        "per_city_agreement": per_city,
        "mean_confidence": (sum(confs) / len(confs)) if confs else None,
        "high_confidence_disagreements": int(high_dis),
        "failures": n_fail,
        "device": str(device),
        "wording": "agreement with structurally weak section labels; not gold accuracy",
    }
    _atomic_write_json(out_dir / "absa_audit.json", out)
    _atomic_write_text(
        out_dir / "ABSA_AUDIT.md",
        f"# ABSA vs weak labels\n\nStatus: **RAN** (not gold accuracy)\n\n"
        f"n={out['n_pairs']} agreement={agree:.4f} kappa={kappa:.4f}\n"
        f"weak-reference F1={f1s}\n"
        f"HUMAN_VALIDATION_REQUIRED remains true.\n",
    )
    print(json.dumps({k: out[k] for k in ("n_pairs", "agreement_vs_weak_section_label", "cohens_kappa_vs_weak", "status")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
