"""Wave 1 ABSA agreement audit vs weak section labels. Never gold accuracy."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.autonomous.common import atomic_write_json, atomic_write_text, out_dir
from src.autonomous.ledger import merge_facts


def _base_out() -> dict:
    return {
        "attempted": True,
        "never_gold_accuracy": True,
        "reference_type": "weak_section_labels",
        "independent_accuracy_not_established": True,
        "fixed_sampler_2800": True,
        "wording": "agreement with structurally weak section labels; not gold accuracy",
    }


def _write(odir: Path, out: dict) -> None:
    atomic_write_json(odir / "absa_audit.json", out)
    atomic_write_text(
        odir / "ABSA_AUDIT.md",
        f"# ABSA vs weak labels\n\nStatus: **{out.get('status')}**\n\n"
        "This compares model predictions to **weak section labels** (positive/negative column), "
        "not human gold. Independent accuracy is not established.\n\n"
        f"Agreement: {out.get('agreement_vs_weak_section_label')}\n"
        f"Cohen's kappa: {out.get('cohens_kappa_vs_weak')}\n",
    )


def _absa_interpreter(root: Path) -> Path | None:
    explicit = os.environ.get("FYP_ABSA_PYTHON")
    if explicit:
        return Path(explicit)
    absa_py = root / ".venv-absa" / "bin" / "python"
    if absa_py.is_file():
        return absa_py
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return None
    return Path(sys.executable)


def _sanitize_audit(result: dict) -> dict:
    clean = {
        k: v
        for k, v in result.items()
        if k not in ("model_dir", "HUMAN_VALIDATION_REQUIRED", "error")
    }
    clean.setdefault("reference_type", "weak_section_labels")
    clean.setdefault("independent_accuracy_not_established", True)
    clean.setdefault("fixed_sampler_2800", True)
    clean.setdefault("never_gold_accuracy", True)
    return clean


def _merge_wave1b(root: Path, payload: dict) -> dict:
    merge_facts(root, "1b_absa", payload)
    return payload


def run_absa_audit(root: Path, *, verify_only: bool = False) -> dict:
    odir = out_dir(root) / "wave1"
    odir.mkdir(parents=True, exist_ok=True)
    out = _base_out()
    if verify_only:
        out["status"] = "SKIPPED_VERIFY_ONLY"
        _write(odir, out)
        return _merge_wave1b(root, out)

    script = root / "scripts" / "run_absa_agreement.py"
    absa_py = _absa_interpreter(root)
    if not script.is_file():
        out["status"] = "SKIPPED_NO_SCRIPT"
        _write(odir, out)
        return _merge_wave1b(root, out)
    if absa_py is None:
        out["status"] = "SKIPPED_NO_ABSA_ENV"
        _write(odir, out)
        return _merge_wave1b(root, out)

    env = {
        **os.environ,
        "FYP_AUTONOMOUS_OUT": str(out_dir(root)),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "FYP_PRIVATE_MODEL_ROOT": os.environ.get("FYP_PRIVATE_MODEL_ROOT", str(root / "models")),
        "FYP_DATA_CACHE_ROOT": os.environ.get("FYP_DATA_CACHE_ROOT", str(root / "data" / "cache")),
    }
    audit_path = odir / "absa_audit.json"
    print("  ABSA subprocess run_absa_agreement.py", flush=True)
    try:
        proc = subprocess.run(
            [str(absa_py), str(script)],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        out["status"] = "FAILED_SUBPROCESS"
        out["error"] = type(exc).__name__
        _write(odir, out)
        return _merge_wave1b(root, out)

    if proc.returncode != 0:
        out["status"] = "FAILED_SUBPROCESS"
        out["returncode"] = int(proc.returncode)
        _write(odir, out)
        return _merge_wave1b(root, out)

    if not audit_path.is_file():
        out["status"] = "FAILED_NO_AUDIT_OUTPUT"
        _write(odir, out)
        return _merge_wave1b(root, out)

    try:
        result = json.loads(audit_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        out["status"] = "FAILED_INVALID_AUDIT_OUTPUT"
        out["error"] = type(exc).__name__
        _write(odir, out)
        return _merge_wave1b(root, out)

    status = str(result.get("status") or "")
    if status.startswith("FAILED_"):
        clean = _sanitize_audit({**_base_out(), **result})
        _write(odir, clean)
        return _merge_wave1b(root, clean)

    if status != "RAN" or result.get("n_pairs") != 2800:
        out["status"] = "FAILED_UNEXPECTED_AUDIT_OUTPUT"
        _write(odir, out)
        return _merge_wave1b(root, out)
    clean = _sanitize_audit(result)
    _write(odir, clean)
    return _merge_wave1b(root, clean)
