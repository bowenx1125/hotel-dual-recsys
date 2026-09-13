#!/usr/bin/env python3
"""Evaluate the four descriptive recommendation policies on a Demo snapshot.

The evaluator deliberately measures coverage, abstention, constraint checks and
agreement on a common denominator.  It does not score outcomes, estimate an
effect, or use a policy's own score as evidence that the policy is useful.

The input snapshot contains aggregate aspect fields only.  This module does
not read review text, annotation files, or provider configuration.  Scoring is
provided by the shared recommendation package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.recommendation.scoring import all_policies  # type: ignore


STRATEGIES = (
    "fix_weakest",
    "largest_peer_gap",
    "most_criticized",
    "peer_relative",
)
EVALUATOR_VERSION = "policy-evaluation-v1"
DEFAULT_MIN_MENTIONS = 5
DEFAULT_MIN_RELIABILITY = 0.3


def _finite(value: Any) -> bool:
    """Return whether *value* can be represented as a finite number."""

    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _json_safe(value: Any) -> Any:
    """Convert a result to JSON-safe values, including non-finite floats.

    ``None`` is used for an undefined value.  This keeps the output valid JSON
    and makes missing denominators explicit instead of silently writing NaN.
    """

    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value, key=str)]
    return value


def _canonical_json(value: Any) -> bytes:
    """Return deterministic JSON bytes for hashing configuration objects."""

    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    """Hash a JSON-compatible object deterministically."""

    return hashlib.sha256(_canonical_json(value)).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash one file in chunks."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ratio(numerator: int, denominator: int) -> float | None:
    """Return a rate, or ``None`` when there is no defined denominator."""

    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _normalise_choice(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        choice = value.strip()
        return choice or None
    return str(value)


def _city_name(hotel: Mapping[str, Any]) -> str:
    value = hotel.get("city")
    if value is None or not str(value).strip():
        value = hotel.get("city_label")
    if value is None or not str(value).strip():
        return "<missing>"
    return str(value)


def _is_eligible(hotel: Mapping[str, Any]) -> bool:
    """Read the snapshot's already-computed display/evaluation eligibility."""

    value = hotel.get("eligible", False)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _hotel_sort_key(item: tuple[int, Mapping[str, Any]]) -> tuple[str, str, int]:
    index, hotel = item
    return (str(hotel.get("hotel_id") or ""), _city_name(hotel), index)


def _hotel_ref(index: int, hotel: Mapping[str, Any]) -> str:
    """Make a stable internal reference even for a synthetic hotel without an ID."""

    hotel_id = hotel.get("hotel_id")
    if hotel_id is not None and str(hotel_id):
        return str(hotel_id)
    return f"<row-{index}>"


def _provenance_path(path: Path | str | None) -> str | None:
    if path is None:
        return None
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _aspects_map(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    nested = value.get("aspects")
    if isinstance(nested, Mapping):
        return nested
    return value


def load_actionability(
    cfg: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    snapshot_path: Path | None = None,
) -> dict[str, Mapping[str, Any]]:
    """Resolve actionability metadata without requiring a real snapshot.

    Synthetic tests can provide ``snapshot['actionability']`` or
    ``cfg['actionability']`` directly.  A normal Demo snapshot points to the
    public ``conf/actionability.json`` file, which is resolved relative to the
    repository and then relative to the snapshot for portable fixtures.
    """

    candidates: list[Any] = []
    for source in (snapshot, cfg):
        if isinstance(source, Mapping):
            for key in ("actionability", "actionability_config"):
                if key in source:
                    candidates.append(source[key])

    paths: list[Path] = []
    for candidate in candidates:
        direct = _aspects_map(candidate)
        if direct is not None and all(isinstance(k, str) for k in direct):
            return {str(k): v for k, v in direct.items() if isinstance(v, Mapping)}
        if isinstance(candidate, (str, Path)):
            raw = Path(candidate)
            if raw.is_absolute():
                paths.append(raw)
            else:
                if snapshot_path is not None:
                    paths.append(snapshot_path.parent / raw)
                paths.append(ROOT / raw)

    seen: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        direct = _aspects_map(data)
        if direct is not None:
            return {str(k): v for k, v in direct.items() if isinstance(v, Mapping)}

    # Location is the one fixed non-actionable aspect in the public contract.
    # Any other selected aspect absent from this map is reported as
    # ``unknown_actionability`` by _choice_checks.  It is never silently
    # treated as actionable.
    return {"location": {"eligible_for_direct_action": False}}


def _choice_checks(
    hotel: Mapping[str, Any],
    choice: str | None,
    actionability: Mapping[str, Mapping[str, Any]],
    *,
    min_mentions: int,
    min_reliability: float,
) -> tuple[bool, bool, bool]:
    """Return ``(non_actionable, low_evidence, unknown_actionability)``."""

    if choice is None:
        return False, False, False

    metadata = actionability.get(choice)
    unknown_actionability = not isinstance(metadata, Mapping) or not isinstance(
        metadata.get("eligible_for_direct_action"), bool
    )
    non_actionable = choice == "location" or (
        not unknown_actionability and metadata.get("eligible_for_direct_action") is False
    )

    aspects = hotel.get("aspects")
    rec = aspects.get(choice) if isinstance(aspects, Mapping) else None
    if not isinstance(rec, Mapping):
        # The low-evidence audit is intentionally scoped to finite net values;
        # a missing net is reported by the policy as an abstention when the
        # shared scorer applies its evidence gate.
        return non_actionable, False, unknown_actionability
    if not _finite(rec.get("net")):
        return non_actionable, False, unknown_actionability

    mentions = rec.get("mention_count")
    reliability = rec.get("reliability")
    low_evidence = (
        not _finite(mentions)
        or float(mentions) < min_mentions
        or not _finite(reliability)
        or float(reliability) < min_reliability
    )
    return non_actionable, low_evidence, unknown_actionability


def _policy_payload(raw: Any, strategy: str) -> tuple[str | None, str | None]:
    """Extract a choice and abstention reason from a policy result."""

    if not isinstance(raw, Mapping):
        return None, "missing_policy_output"
    policy = raw.get(strategy)
    if not isinstance(policy, Mapping):
        return None, "missing_policy_output"
    choice = _normalise_choice(policy.get("chosen_aspect"))
    if choice is not None:
        return choice, None
    reason = policy.get("abstention_reason")
    if reason is None or not str(reason).strip():
        reason = "no_recommendation"
    return None, str(reason)


def _empty_city_stats() -> dict[str, Any]:
    return {
        "all_hotel_count": 0,
        "eligible_hotel_count": 0,
        "recommendation_count": 0,
        "abstention_count": 0,
        "coverage": None,
        "coverage_of_all_hotels": None,
    }


def _empty_strategy_stats() -> dict[str, Any]:
    return {
        "all_hotel_count": 0,
        "eligible_hotel_count": 0,
        "recommendation_count": 0,
        "abstention_count": 0,
        "coverage": None,
        "coverage_of_all_hotels": None,
        "choice_counts": {},
        "abstention_reasons": {},
        "checks": {
            "non_actionable_choice_count": 0,
            "low_evidence_choice_count": 0,
            "unknown_actionability_choice_count": 0,
            "by_city": {},
        },
        "by_city": {},
    }


def _assert_distinct_paths(snapshot_path: Path | str, output_path: Path | str) -> None:
    """Reject an output path that resolves to the input snapshot."""

    source = Path(snapshot_path)
    target = Path(output_path)
    try:
        source_resolved = source.resolve(strict=False)
        target_resolved = target.resolve(strict=False)
    except OSError:
        # Keep the guard effective for unusual symlink loops while avoiding any
        # filesystem mutation.  Normal paths use resolve(strict=False) above.
        source_resolved = Path(os.path.abspath(os.path.normpath(str(source))))
        target_resolved = Path(os.path.abspath(os.path.normpath(str(target))))
    if source_resolved == target_resolved:
        raise ValueError("output path must differ from the input snapshot path")
    try:
        if source.is_file() and target.is_file() and os.path.samefile(source, target):
            raise ValueError("output path must differ from the input snapshot path")
    except OSError:
        # A missing or dangling output is handled by write_evaluation's strict
        # symlink guard; samefile is only an additional hard-link safeguard.
        pass


def evaluate_snapshot(
    snapshot: Mapping[str, Any],
    *,
    scorer: Callable[[Mapping[str, Any], Mapping[str, Any], float], Mapping[str, Any]] | None = None,
    assumed_intensity: float = 0.0,
    input_sha256: str | None = None,
    input_path: Path | str | None = None,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate the four policies on a loaded snapshot.

    Only hotels with the snapshot's ``eligible`` flag contribute policy
    recommendation or abstention counts.  The all-hotel count is retained in
    each summary so that coverage denominators are auditable.  ``scorer`` is
    injectable for synthetic tests and defaults to the shared implementation.
    """

    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be a JSON object")
    hotels_value = snapshot.get("hotels")
    if not isinstance(hotels_value, Sequence) or isinstance(hotels_value, (str, bytes)):
        raise ValueError("snapshot.hotels must be a list")
    cfg_value = snapshot.get("config") or {}
    if not isinstance(cfg_value, Mapping):
        raise ValueError("snapshot.config must be an object")
    cfg = dict(cfg_value)
    run_scorer = scorer or all_policies

    min_mentions_raw = cfg.get("min_mentions", DEFAULT_MIN_MENTIONS)
    try:
        min_mentions = int(min_mentions_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("config.min_mentions must be an integer") from exc
    min_reliability_raw = cfg.get("min_reliability", DEFAULT_MIN_RELIABILITY)
    try:
        min_reliability = float(min_reliability_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("config.min_reliability must be numeric") from exc
    if not math.isfinite(min_reliability):
        raise ValueError("config.min_reliability must be finite")

    actionability = load_actionability(cfg, snapshot, snapshot_path=snapshot_path)
    rows: list[dict[str, Any]] = []
    indexed_hotels: list[tuple[int, Mapping[str, Any]]] = []
    for index, hotel_value in enumerate(hotels_value):
        if not isinstance(hotel_value, Mapping):
            raise ValueError(f"snapshot.hotels[{index}] must be an object")
        indexed_hotels.append((index, hotel_value))

    seen_hotel_ids: dict[str, int] = {}
    for index, hotel in indexed_hotels:
        raw_hotel_id = hotel.get("hotel_id")
        if raw_hotel_id is None or not str(raw_hotel_id).strip():
            continue
        hotel_id = str(raw_hotel_id).strip()
        previous = seen_hotel_ids.get(hotel_id)
        if previous is not None:
            raise ValueError(
                f"duplicate hotel_id {hotel_id!r} at rows {previous} and {index}; "
                "evaluation counts hotels, not duplicate rows"
            )
        seen_hotel_ids[hotel_id] = index

    # Sorting makes aggregate dictionaries and the common set independent of
    # the order in which a producer happened to serialise its hotels.
    indexed_hotels.sort(key=_hotel_sort_key)
    for index, hotel in indexed_hotels:
        eligible = _is_eligible(hotel)
        choices: dict[str, str | None] = {strategy: None for strategy in STRATEGIES}
        reasons: dict[str, str] = {}
        non_actionable: dict[str, bool] = {strategy: False for strategy in STRATEGIES}
        low_evidence: dict[str, bool] = {strategy: False for strategy in STRATEGIES}
        unknown_actionability: dict[str, bool] = {strategy: False for strategy in STRATEGIES}

        if eligible:
            policy_results = run_scorer(hotel, cfg, float(assumed_intensity))
            for strategy in STRATEGIES:
                choice, reason = _policy_payload(policy_results, strategy)
                choices[strategy] = choice
                if reason is not None:
                    reasons[strategy] = reason
                (
                    non_actionable[strategy],
                    low_evidence[strategy],
                    unknown_actionability[strategy],
                ) = _choice_checks(
                    hotel,
                    choice,
                    actionability,
                    min_mentions=min_mentions,
                    min_reliability=min_reliability,
                )

        rows.append(
            {
                "ref": _hotel_ref(index, hotel),
                "hotel_id": str(hotel.get("hotel_id")) if hotel.get("hotel_id") is not None else None,
                "city": _city_name(hotel),
                "eligible": eligible,
                "choices": choices,
                "reasons": reasons,
                "non_actionable": non_actionable,
                "low_evidence": low_evidence,
                "unknown_actionability": unknown_actionability,
            }
        )

    total_hotels = len(rows)
    eligible_rows = [row for row in rows if row["eligible"]]
    eligible_count = len(eligible_rows)
    strategies: dict[str, dict[str, Any]] = {}

    for strategy in STRATEGIES:
        stats = _empty_strategy_stats()
        stats["all_hotel_count"] = total_hotels
        stats["eligible_hotel_count"] = eligible_count
        city_stats: dict[str, dict[str, Any]] = defaultdict(_empty_city_stats)
        choice_counts: Counter[str] = Counter()
        abstention_reasons: Counter[str] = Counter()
        check_city: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "non_actionable_choice_count": 0,
                "low_evidence_choice_count": 0,
                "unknown_actionability_choice_count": 0,
            }
        )

        for row in rows:
            city = row["city"]
            city_stats[city]["all_hotel_count"] += 1
            if not row["eligible"]:
                continue
            city_stats[city]["eligible_hotel_count"] += 1
            choice = row["choices"][strategy]
            if choice is None:
                stats["abstention_count"] += 1
                city_stats[city]["abstention_count"] += 1
                abstention_reasons[row["reasons"].get(strategy, "no_recommendation")] += 1
            else:
                stats["recommendation_count"] += 1
                city_stats[city]["recommendation_count"] += 1
                choice_counts[choice] += 1

            if row["non_actionable"][strategy]:
                stats["checks"]["non_actionable_choice_count"] += 1
                check_city[city]["non_actionable_choice_count"] += 1
            if row["low_evidence"][strategy]:
                stats["checks"]["low_evidence_choice_count"] += 1
                check_city[city]["low_evidence_choice_count"] += 1
            if row["unknown_actionability"][strategy]:
                stats["checks"]["unknown_actionability_choice_count"] += 1
                check_city[city]["unknown_actionability_choice_count"] += 1

        stats["coverage"] = _ratio(stats["recommendation_count"], eligible_count)
        stats["coverage_of_all_hotels"] = _ratio(stats["recommendation_count"], total_hotels)
        for city, city_record in sorted(city_stats.items()):
            city_record["coverage"] = _ratio(
                city_record["recommendation_count"],
                city_record["eligible_hotel_count"],
            )
            city_record["coverage_of_all_hotels"] = _ratio(
                city_record["recommendation_count"],
                city_record["all_hotel_count"],
            )
        stats["by_city"] = {city: city_stats[city] for city in sorted(city_stats)}
        stats["choice_counts"] = dict(sorted(choice_counts.items()))
        stats["abstention_reasons"] = dict(sorted(abstention_reasons.items()))
        stats["checks"]["by_city"] = {
            city: check_city[city] for city in sorted(check_city)
        }
        strategies[strategy] = stats

    common_rows = [
        row
        for row in eligible_rows
        if all(row["choices"][strategy] is not None for strategy in STRATEGIES)
    ]
    common_refs = [row["ref"] for row in common_rows]
    common_ids = [row["hotel_id"] for row in common_rows if row["hotel_id"] is not None]
    pairwise: dict[str, dict[str, Any]] = {}
    for left_index, left in enumerate(STRATEGIES):
        for right in STRATEGIES[left_index + 1 :]:
            denominator = len(common_rows)
            agreement_count = sum(
                1 for row in common_rows if row["choices"][left] == row["choices"][right]
            )
            disagreement_count = denominator - agreement_count
            pairwise[f"{left}__{right}"] = {
                "strategy_a": left,
                "strategy_b": right,
                "denominator": denominator,
                "agreement_count": agreement_count,
                "disagreement_count": disagreement_count,
                "agreement_rate": _ratio(agreement_count, denominator),
                "disagreement_rate": _ratio(disagreement_count, denominator),
            }

    if input_sha256 is None:
        # Pure callers without a file still receive a reproducible provenance
        # value.  The CLI always supplies the byte hash of the input file.
        input_sha256 = sha256_json(snapshot)
        input_hash_basis = "canonical_snapshot_json"
    else:
        input_hash_basis = "input_file_bytes"
    cfg_hash = sha256_json(cfg)
    policy_version = str(
        cfg.get("policy_version")
        or snapshot.get("policy_version")
        or "unspecified"
    )
    configured_aspects = cfg.get("aspects")
    if isinstance(configured_aspects, Sequence) and not isinstance(configured_aspects, (str, bytes)):
        configured_aspect_names = sorted({str(aspect) for aspect in configured_aspects})
    else:
        configured_aspect_names = []
    missing_actionability = sorted(set(configured_aspect_names) - set(actionability))
    unknown_selected_total = sum(
        int(stats["checks"]["unknown_actionability_choice_count"])
        for stats in strategies.values()
    )

    result: dict[str, Any] = {
        "schema_version": EVALUATOR_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "policy_version": policy_version,
        "evidence_level": "DESCRIPTIVE",
        "descriptive_only": True,
        "interpretation": (
            "Descriptive policy outputs only. There is no independent truth label, "
            "outcome evaluation, causal effect, demand lift, ROI, or business-gain claim."
        ),
        "input": {
            "path": _provenance_path(input_path),
            "sha256": input_sha256,
            "hash_basis": input_hash_basis,
            "snapshot_schema_version": snapshot.get("schema_version"),
        },
        # Short aliases keep provenance easy to find for downstream consumers.
        "input_sha256": input_sha256,
        "config_sha256": cfg_hash,
        "hashes": {
            "input_sha256": input_sha256,
            "config_sha256": cfg_hash,
        },
        "thresholds": {
            "min_mentions": min_mentions,
            "min_reliability": min_reliability,
        },
        "actionability_audit": {
            "known_aspects": sorted(actionability),
            "configured_aspects_without_metadata": missing_actionability,
            "unknown_selected_choice_count": unknown_selected_total,
            "note": (
                "A selected aspect without explicit boolean actionability metadata is "
                "reported as unknown_actionability and is not treated as actionable."
            ),
        },
        "population": {
            "all_hotel_count": total_hotels,
            "eligible_hotel_count": eligible_count,
        },
        "strategies": strategies,
        "common_comparison": {
            "strategy_set": list(STRATEGIES),
            "hotel_count": len(common_rows),
            "hotel_refs": common_refs,
            "hotel_ids": common_ids,
            "pairwise": pairwise,
            "note": (
                "All pairwise rates use this same set of eligible hotels where all four "
                "strategies returned a recommendation. Rates are agreement/disagreement "
                "of choices, not accuracy."
            ),
        },
        "notes": [
            "Counts are descriptive outputs of the configured deterministic policies.",
            "Recommendation coverage is recommendation_count / eligible_hotel_count.",
            "Non-actionable and low-evidence checks are audits of chosen aspects; they are not outcome metrics.",
            "No independent ground truth is available; do not call agreement accuracy or infer superiority, effect, or收益.",
        ],
    }
    return _json_safe(result)


def load_snapshot(path: Path | str) -> dict[str, Any]:
    """Load one JSON snapshot and validate the top-level shape."""

    p = Path(path)
    try:
        raw = p.read_bytes()
        snapshot = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON snapshot: {p}") from exc
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    return snapshot


def write_evaluation(
    result: Mapping[str, Any],
    path: Path | str,
    *,
    overwrite: bool = False,
) -> None:
    """Write deterministic JSON, refusing existing output unless requested."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        _json_safe(result),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if not overwrite:
        if target.is_symlink():
            # O_EXCL behaviour for a dangling symlink varies by platform; make
            # the strict no-overwrite rule explicit before opening the path.
            raise FileExistsError(f"output exists (including symlink): {target}")
        # Exclusive creation makes the default refusal race-safe and preserves
        # the existing file byte-for-byte when it already exists.
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        return

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def evaluate_file(
    snapshot_path: Path | str,
    output_path: Path | str,
    *,
    overwrite: bool = False,
    assumed_intensity: float = 0.0,
    scorer: Callable[[Mapping[str, Any], Mapping[str, Any], float], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Load, evaluate and write one snapshot; return the written result."""

    source = Path(snapshot_path)
    target = Path(output_path)
    _assert_distinct_paths(source, target)
    # Read and hash the same stable byte sequence so provenance cannot point
    # at a different version if a producer replaces the file during a run.
    raw = source.read_bytes()
    input_hash = hashlib.sha256(raw).hexdigest()
    try:
        snapshot = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON snapshot: {source}") from exc
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    result = evaluate_snapshot(
        snapshot,
        scorer=scorer,
        assumed_intensity=assumed_intensity,
        input_sha256=input_hash,
        input_path=snapshot_path,
        snapshot_path=source,
    )
    write_evaluation(result, target, overwrite=overwrite)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        default="outputs/demo/research_snapshot.json",
        help="JSON Demo snapshot (default: outputs/demo/research_snapshot.json)",
    )
    parser.add_argument(
        "--output",
        default="outputs/demo/policy_evaluation.json",
        help="evaluation JSON output (default: outputs/demo/policy_evaluation.json)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing output atomically; default is strict refusal",
    )
    parser.add_argument(
        "--assumed-intensity",
        type=float,
        default=0.0,
        help="scenario intensity passed to peer_relative (default: 0.0)",
    )
    args = parser.parse_args(argv)
    source = Path(args.snapshot)
    output = Path(args.output)
    if not source.is_absolute():
        source = ROOT / source
    if not output.is_absolute():
        output = ROOT / output
    result = evaluate_file(
        source,
        output,
        overwrite=args.overwrite,
        assumed_intensity=args.assumed_intensity,
    )
    print(
        f"wrote {output} | hotels={result['population']['all_hotel_count']} "
        f"eligible={result['population']['eligible_hotel_count']} "
        f"common={result['common_comparison']['hotel_count']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI exercised by smoke tests
    raise SystemExit(main())
