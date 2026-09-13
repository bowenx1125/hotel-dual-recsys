"""Wave 1 ABSA agreement audit vs weak section labels. Never gold accuracy."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from src.autonomous.common import cohen_kappa, load_config, out_dir, update_state
from src.autonomous.ledger import merge_facts


def run_absa_audit(root: Path, *, verify_only: bool = False) -> dict:
    odir = out_dir(root) / "wave1"
    odir.mkdir(parents=True, exist_ok=True)
    private = out_dir(root) / "private"
    pack_path = private / "human_annotation_pack.json"
    model_root = Path(os.environ.get("FYP_PRIVATE_MODEL_ROOT") or (root / "models"))
    model_dir = model_root / "absa"
    weights = model_dir / "model.safetensors"
    out: dict = {
        "attempted": True,
        "never_gold_accuracy": True,
        "HUMAN_VALIDATION_REQUIRED": True,
    }
    if verify_only:
        out["status"] = "SKIPPED_VERIFY_ONLY"
        _write(odir, out)
        return out
    if not pack_path.exists():
        out["status"] = "SKIPPED_NO_PACK"
        _write(odir, out)
        return out
    if not weights.exists():
        out["status"] = "SKIPPED_NO_LOCAL_WEIGHTS"
        out["model_dir"] = str(model_dir)
        _write(odir, out)
        return out

    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    items = pack.get("items") or []
    # expand to review-aspect pairs already in pack
    pairs = items[:4200]
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch
    except Exception as e:
        absa_py = Path(os.environ.get("FYP_ABSA_PYTHON") or str(root / ".venv-absa" / "bin" / "python"))
        script = root / "scripts" / "run_absa_agreement.py"
        if absa_py.exists() and script.exists() and not os.environ.get("FYP_SMALL_FIXTURE"):
            import subprocess
            env = {
                **os.environ,
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "FYP_PRIVATE_MODEL_ROOT": os.environ.get("FYP_PRIVATE_MODEL_ROOT", str(root / "models")),
                "FYP_DATA_CACHE_ROOT": os.environ.get("FYP_DATA_CACHE_ROOT", str(root / "data" / "cache")),
            }
            print(f"  ABSA falling back to {absa_py}", flush=True)
            r = subprocess.run([str(absa_py), str(script)], cwd=str(root), env=env)
            audit_p = odir / "absa_audit.json"
            if r.returncode == 0 and audit_p.exists():
                out = json.loads(audit_p.read_text(encoding="utf-8"))
                merge_facts(root, "1b_absa", {k: v for k, v in out.items() if k != "error"})
                return out
        out["status"] = "SKIPPED_TRANSFORMERS_UNAVAILABLE"
        out["error"] = type(e).__name__
        _write(odir, out)
        return out

    print(f"  ABSA loading {model_dir} n={len(pairs)}", flush=True)
    tok = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()
    id2lab = {int(i): str(l).lower() for i, l in model.config.id2label.items()}
    y_weak, y_pred, confs = [], [], []
    n_fail = 0
    for i, it in enumerate(pairs, 1):
        text = it.get("text") or ""
        asp = it.get("aspect") or "room"
        weak = "positive" if it.get("section") == "positive" else "negative"
        try:
            with torch.no_grad():
                inp = tok(text, asp, return_tensors="pt", truncation=True, max_length=256)
                probs = torch.softmax(model(**inp).logits, dim=1)[0]
                idx = int(probs.argmax())
                lab = id2lab.get(idx, str(idx))
                conf = float(probs[idx])
        except Exception:
            n_fail += 1
            continue
        y_weak.append(weak)
        y_pred.append(lab)
        confs.append(conf)
        if i % 200 == 0 or i == len(pairs):
            print(f"  ABSA 已完成/总数/失败数 = {i}/{len(pairs)}/{n_fail}", flush=True)

    y_weak = np.array(y_weak)
    y_pred = np.array(y_pred)
    confs = np.array(confs)
    # map model labels
    pred_bin = np.array(["positive" if p.startswith("pos") else ("negative" if p.startswith("neg") else "neutral") for p in y_pred])
    agree = float((pred_bin == y_weak).mean()) if len(y_weak) else float("nan")
    kappa = cohen_kappa(y_weak, pred_bin, ["positive", "negative", "neutral"])
    # weak-reference F1 treating weak labels as reference (NOT gold)
    f1s = {}
    for lab in ("positive", "negative"):
        tp = int(((pred_bin == lab) & (y_weak == lab)).sum())
        fp = int(((pred_bin == lab) & (y_weak != lab)).sum())
        fn = int(((pred_bin != lab) & (y_weak == lab)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s[lab] = 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)
    high = confs >= 0.8 if len(confs) else np.array([])
    high_dis = int(((pred_bin != y_weak) & high).sum()) if len(high) else 0
    per_asp = {}
    for asp in sorted({it.get("aspect") for it in pairs}):
        idx = [j for j, it in enumerate(pairs[: len(pred_bin)]) if it.get("aspect") == asp]
        if not idx:
            continue
        per_asp[asp] = float((pred_bin[idx] == y_weak[idx]).mean())
    per_city = {}
    for city in sorted({it.get("city") for it in pairs}):
        idx = [j for j, it in enumerate(pairs[: len(pred_bin)]) if it.get("city") == city]
        if not idx:
            continue
        per_city[city] = float((pred_bin[idx] == y_weak[idx]).mean())

    out.update({
        "status": "RAN",
        "n_pairs": int(len(pred_bin)),
        "agreement_vs_weak_section_label": agree,
        "cohens_kappa_vs_weak": kappa,
        "weak_reference_f1": f1s,
        "per_aspect_agreement": per_asp,
        "per_city_agreement": per_city,
        "mean_confidence": float(confs.mean()) if len(confs) else None,
        "high_confidence_disagreements": high_dis,
        "failures": n_fail,
        "wording": "agreement with structurally weak section labels; not gold accuracy",
    })
    _write(odir, out)
    merge_facts(root, "1b_absa", {k: v for k, v in out.items() if k != "error"})
    return out


def _write(odir: Path, out: dict) -> None:
    from src.autonomous.common import atomic_write_json, atomic_write_text
    atomic_write_json(odir / "absa_audit.json", out)
    atomic_write_text(
        odir / "ABSA_AUDIT.md",
        f"# ABSA vs weak labels\n\nStatus: **{out.get('status')}**\n\n"
        "This is **not** gold accuracy.\n\n"
        f"Agreement: {out.get('agreement_vs_weak_section_label')}\n"
        f"Cohen's kappa: {out.get('cohens_kappa_vs_weak')}\n",
    )
