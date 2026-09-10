"""Initialize and atomically update autonomous research ledgers."""
from __future__ import annotations

import csv
from pathlib import Path

from src.autonomous.common import atomic_write_json, atomic_write_text, out_dir, sha256_json, update_state


def init_ledgers(root: Path) -> None:
    d = out_dir(root)
    files = {
        "CLAIMS_LEDGER.md": "# Claims Ledger\n\n| ID | Claim | Status | Evidence | Exact metric | Allowed wording | Forbidden wording |\n|---|---|---|---|---|---|---|\n",
        "DECISIONS.md": "# Decisions\n\nPreregistered analysis choices. Do not retune to recover significance.\n",
        "FAILURES.md": "# Failures\n\n",
        "REVIEW_LOG.md": "# Review Log\n\n",
        "IDEA_LOG.md": "# Idea Log\n\nActive: provider-side recommendation under honest measurement and peer-reference sets.\n",
        "PAPER_TRACK.md": "# Paper Track\n\nMaintained tracks: A Peer Interference · B Diagnosis≠Action · C Measurement.\nSelected: UNDECIDED (before Wave 6).\n",
        "NEXT.md": "# NEXT\n\n1. Finish Wave 0 forensic + CI + commit/push.\n",
    }
    for name, text in files.items():
        p = d / name
        if not p.exists():
            atomic_write_text(p, text)
    if not (d / "FACTS.json").exists():
        atomic_write_json(d / "FACTS.json", {"schema_version": "2.0", "waves": {}})
    if not (d / "ARTIFACT_INDEX.json").exists():
        atomic_write_json(d / "ARTIFACT_INDEX.json", {"artifacts": []})
    reg = d / "EXPERIMENT_REGISTRY.csv"
    if not reg.exists():
        atomic_write_text(
            reg,
            "experiment_id,wave,name,preregistered,status,artifact,result_summary,claim_ids\n",
        )
    update_state(root, status="LEDGERS_INITIALIZED")


def register_experiment(root: Path, row: dict) -> None:
    path = out_dir(root) / "EXPERIMENT_REGISTRY.csv"
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "experiment_id", "wave", "name", "preregistered", "status",
                "artifact", "result_summary", "claim_ids",
            ],
        )
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in w.fieldnames})


def merge_facts(root: Path, wave: str, payload: dict) -> dict:
    path = out_dir(root) / "FACTS.json"
    facts = {}
    if path.exists():
        import json
        facts = json.loads(path.read_text(encoding="utf-8"))
    facts.setdefault("schema_version", "2.0")
    facts.setdefault("waves", {})
    facts["waves"][str(wave)] = payload
    facts["facts_sha256"] = ""
    digest = sha256_json(facts)
    facts["facts_sha256"] = digest
    atomic_write_json(path, facts)
    update_state(root, facts_sha256=digest)
    return facts


def index_artifact(root: Path, rel: str, kind: str, sha: str | None = None) -> None:
    import json
    path = out_dir(root) / "ARTIFACT_INDEX.json"
    obj = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"artifacts": []}
    obj["artifacts"] = [a for a in obj.get("artifacts", []) if a.get("path") != rel]
    rec = {"path": rel, "kind": kind}
    p = root / rel
    if p.exists():
        from src.autonomous.common import sha256_file
        rec["sha256"] = sha or sha256_file(p)
        rec["bytes"] = p.stat().st_size
    obj["artifacts"].append(rec)
    atomic_write_json(path, obj)
