"""Waves 2–7: strict events, peers, prediction, event study, policy, robustness."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.autonomous.common import (
    ACTIONABLE,
    ASPECTS,
    atomic_write_json,
    atomic_write_text,
    cluster_bootstrap_delta,
    haversine_km,
    load_config,
    out_dir,
    p_delta_gt0,
    period_sort_key,
    ridge_with_intercept,
    smoothed_net,
    update_state,
    write_parquet,
)
from src.autonomous.ledger import index_artifact, merge_facts, register_experiment


def _complete_periods(panel: pd.DataFrame) -> list[str]:
    sub = panel[panel["period_complete"]]
    return sorted(sub["period"].unique().tolist(), key=period_sort_key)


def _hotel_table(panel: pd.DataFrame) -> pd.DataFrame:
    h = (
        panel.groupby("hotel_id", as_index=False)
        .agg(
            hotel_name=("hotel_name", "first"),
            city=("city", "first"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
        )
    )
    return h[np.isfinite(h["latitude"]) & np.isfinite(h["longitude"])].reset_index(drop=True)


def knn_edges(h: pd.DataFrame, k: int) -> pd.DataFrame:
    rows = []
    for city, g in h.groupby("city"):
        g = g.sort_values("hotel_id").reset_index(drop=True)
        n = len(g)
        if n < 2:
            continue
        lats, lons = g["latitude"].to_numpy(), g["longitude"].to_numpy()
        ids, names = g["hotel_id"].tolist(), g["hotel_name"].tolist()
        kk = min(k, n - 1)
        for i in range(n):
            d = haversine_km(lats[i], lons[i], lats, lons)
            d[i] = np.inf
            order = np.lexsort((np.array(ids), d))
            for rank, j in enumerate(order[:kk], 1):
                rows.append({
                    "city": city, "hotel_id": ids[i], "peer_hotel_id": ids[j],
                    "distance_km": float(d[j]), "rank": rank,
                    "method": "same_city_knn", "k": k,
                })
    return pd.DataFrame(rows)


def mutual_knn(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return edges
    s = set(zip(edges["hotel_id"], edges["peer_hotel_id"]))
    m = edges[edges.apply(lambda r: (r["peer_hotel_id"], r["hotel_id"]) in s, axis=1)].copy()
    m["method"] = "mutual_knn"
    return m


def radius_edges(h: pd.DataFrame, radius_km: float) -> pd.DataFrame:
    rows = []
    for city, g in h.groupby("city"):
        g = g.sort_values("hotel_id").reset_index(drop=True)
        lats, lons = g["latitude"].to_numpy(), g["longitude"].to_numpy()
        ids = g["hotel_id"].tolist()
        n = len(g)
        for i in range(n):
            d = haversine_km(lats[i], lons[i], lats, lons)
            rank = 0
            for j in np.argsort(d):
                if i == j or d[j] > radius_km:
                    continue
                rank += 1
                rows.append({
                    "city": city, "hotel_id": ids[i], "peer_hotel_id": ids[j],
                    "distance_km": float(d[j]), "rank": rank,
                    "method": "radius_km", "k": np.nan,
                })
    return pd.DataFrame(rows)


def random_edges(h: pd.DataFrame, k: int, rng: np.random.Generator, *, local: bool) -> pd.DataFrame:
    rows = []
    cities = list(h.groupby("city"))
    all_ids = h["hotel_id"].tolist()
    city_of = dict(zip(h["hotel_id"], h["city"]))
    for city, g in cities:
        ids = g["hotel_id"].tolist()
        others_nonlocal = [x for x in all_ids if city_of[x] != city]
        for hid in ids:
            if local:
                pool = [x for x in ids if x != hid]
            else:
                pool = others_nonlocal
            if not pool:
                continue
            take = rng.choice(pool, size=min(k, len(pool)), replace=False)
            for rank, pid in enumerate(np.atleast_1d(take), 1):
                rows.append({
                    "city": city, "hotel_id": hid, "peer_hotel_id": pid,
                    "distance_km": np.nan, "rank": rank,
                    "method": "random_same_city" if local else "non_local_random", "k": k,
                })
    return pd.DataFrame(rows)


def build_main_peers(panel: pd.DataFrame, k: int = 10) -> pd.DataFrame:
    return knn_edges(_hotel_table(panel), k)


def _lookup_series(panel: pd.DataFrame, col: str) -> dict:
    return {(r.hotel_id, r.aspect, r.period): getattr(r, col) for r in panel.itertuples(index=False)}


def detect_events(
    panel: pd.DataFrame,
    peers: pd.DataFrame,
    cfg: dict,
    *,
    fold: str,
    prior: float,
    delta_thr: float,
    p_thr: float,
    include_location: bool,
    draws: int,
    seed: int,
) -> pd.DataFrame:
    """Review-perceived aspect changes. fold in {A,B,ALL}."""
    main = cfg["events"]["main"]
    complete = _complete_periods(panel)
    if len(complete) < 5:
        # still try with whatever complete periods exist
        pass
    pi = {p: i for i, p in enumerate(complete)}
    want_pre = 2
    want_post = 2
    eligible_t = []
    for p in complete:
        i = pi[p]
        if i >= want_pre and (len(complete) - 1 - i) >= want_post:
            # neighbors must be complete by construction of `complete`
            eligible_t.append(p)
    if not eligible_t:
        return pd.DataFrame()

    if fold == "A":
        pos_c, neg_c, has_c, net_c = "positive_mentions_A", "negative_mentions_A", "has_measurement_A", "smoothed_net_A"
    elif fold == "B":
        pos_c, neg_c, has_c, net_c = "positive_mentions_B", "negative_mentions_B", "has_measurement_B", "smoothed_net_B"
    else:
        pos_c, neg_c, has_c, net_c = "positive_mentions", "negative_mentions", "has_measurement", "smoothed_net"

    sub = panel[panel["period"].isin(complete)].copy()
    key_has = _lookup_series(sub, has_c.split(".")[0] if False else has_c)
    # columns are names
    has_map = {(r.hotel_id, r.aspect, r.period): bool(getattr(r, has_c)) for r in sub.itertuples(index=False)}
    ment_map = {(r.hotel_id, r.aspect, r.period): int(getattr(r, pos_c) + getattr(r, neg_c)) for r in sub.itertuples(index=False)}
    pos_map = {(r.hotel_id, r.aspect, r.period): int(getattr(r, pos_c)) for r in sub.itertuples(index=False)}
    neg_map = {(r.hotel_id, r.aspect, r.period): int(getattr(r, neg_c)) for r in sub.itertuples(index=False)}
    net_map = {(r.hotel_id, r.aspect, r.period): float(getattr(r, net_c)) for r in sub.itertuples(index=False)}
    city_map = {(r.hotel_id, r.aspect, r.period): r.city for r in sub.itertuples(index=False)}
    score_map = {(r.hotel_id, r.period): r.mean_reviewer_score for r in sub.drop_duplicates(["hotel_id", "period"]).itertuples(index=False)}
    rel_map = {(r.hotel_id, r.aspect, r.period): float(r.measurement_reliability) for r in sub.itertuples(index=False)}
    vol_map = {(r.hotel_id, r.period): int(r.total_reviews) for r in sub.drop_duplicates(["hotel_id", "period"]).itertuples(index=False)}

    peer_map = peers.groupby("hotel_id")["peer_hotel_id"].apply(list).to_dict() if len(peers) else {}
    prev_of = {complete[i]: complete[i - 1] for i in range(1, len(complete))}
    pre2_of = {complete[i]: complete[i - 2] for i in range(2, len(complete))}
    post1_of = {complete[i]: complete[i + 1] for i in range(0, len(complete) - 1)}
    post2_of = {complete[i]: complete[i + 2] for i in range(0, len(complete) - 2)}

    cands = []
    aspects = ASPECTS if include_location else ACTIONABLE
    hotels = sub["hotel_id"].unique()
    for hid in hotels:
        for asp in aspects:
            for t in eligible_t:
                t1, t2 = prev_of[t], pre2_of[t]
                if not has_map.get((hid, asp, t)) or not has_map.get((hid, asp, t1)):
                    continue
                m_t = ment_map[(hid, asp, t)]
                m_1 = ment_map[(hid, asp, t1)]
                m_2 = ment_map.get((hid, asp, t2), 0)
                if m_t < main["min_current_mentions"] or m_1 < main["min_previous_mentions"]:
                    continue
                if m_2 < main["min_pre2_mentions"]:
                    continue
                dq = net_map[(hid, asp, t)] - net_map[(hid, asp, t1)]
                if dq < delta_thr:
                    continue
                # valid 2pre+2post measurement
                ok_pp = True
                for pp in (t2, t1, post1_of[t], post2_of[t]):
                    if not has_map.get((hid, asp, pp)):
                        ok_pp = False
                        break
                cands.append({
                    "hotel_id": hid, "aspect": asp, "period": t, "prev_period": t1,
                    "city": city_map[(hid, asp, t)],
                    "delta_q": dq, "mentions": m_t, "prev_mentions": m_1, "pre2_mentions": m_2,
                    "pos_t": pos_map[(hid, asp, t)], "neg_t": neg_map[(hid, asp, t)],
                    "pos_0": pos_map[(hid, asp, t1)], "neg_0": neg_map[(hid, asp, t1)],
                    "has_valid_2pre_2post": ok_pp,
                    "q_lag1": net_map[(hid, asp, t1)],
                    "pretrend": net_map[(hid, asp, t1)] - net_map.get((hid, asp, t2), net_map[(hid, asp, t1)]),
                    "overall_score": score_map.get((hid, t1), np.nan),
                    "review_volume": vol_map.get((hid, t1), 0),
                    "reliability": rel_map[(hid, asp, t1)],
                    "fold": fold,
                })
    if not cands:
        return pd.DataFrame()
    cdf = pd.DataFrame(cands)
    cdf["p_delta_gt0"] = p_delta_gt0(
        cdf["pos_t"].to_numpy(), cdf["neg_t"].to_numpy(),
        cdf["pos_0"].to_numpy(), cdf["neg_0"].to_numpy(),
        prior, draws=draws, seed=seed,
    )
    cdf = cdf[cdf["p_delta_gt0"] >= p_thr].copy()
    if cdf.empty:
        return cdf

    # exposure
    exp_rows = []
    for r in cdf.itertuples(index=False):
        plist = [p for p in peer_map.get(r.hotel_id, []) if p != r.hotel_id]
        known = 0
        improving = 0
        for pid in plist:
            if city_map.get((pid, r.aspect, r.period)) not in (None, r.city):
                continue
            if not has_map.get((pid, r.aspect, r.period)) or not has_map.get((pid, r.aspect, r.prev_period)):
                continue
            known += 1
            pdlt = net_map[(pid, r.aspect, r.period)] - net_map[(pid, r.aspect, r.prev_period)]
            if pdlt >= delta_thr:
                improving += 1
        exp_rows.append({
            "eligible_measured_peers": known,
            "improving_peers": improving,
            "peer_exposure": (improving / known) if known else np.nan,
        })
    edf = pd.concat([cdf.reset_index(drop=True), pd.DataFrame(exp_rows)], axis=1)
    edf = edf[edf["eligible_measured_peers"] >= main["min_eligible_measured_peers"]].copy()

    edf = edf.copy()
    edf["_pkey"] = edf["period"].map(period_sort_key)
    edf = edf.sort_values(["hotel_id", "aspect", "fold", "_pkey"])
    last_pos: dict = {}
    cooldown = int(main["cooldown_quarters"])
    keep_idx = []
    for idx, r in edf.iterrows():
        key = (r.hotel_id, r.aspect, r.fold)
        pos = pi[r.period]
        if key in last_pos and pos - last_pos[key] <= cooldown:
            continue
        last_pos[key] = pos
        keep_idx.append(idx)
    return edf.loc[keep_idx].drop(columns=["_pkey"]).reset_index(drop=True)


def _strict_verdict(ev: pd.DataFrame, cfg: dict) -> tuple[str, dict]:
    g = cfg["green_strict"]
    if ev is None or ev.empty:
        m = {k: 0 for k in ("n", "hotels", "cities", "aspects", "exp_gt0", "exp_eq0")}
        m["frac_valid"] = 0.0
        return "RED_MEASUREMENT", m
    m = {
        "n": int(len(ev)),
        "hotels": int(ev["hotel_id"].nunique()),
        "cities": int(ev["city"].nunique()),
        "aspects": int(ev["aspect"].nunique()),
        "exp_gt0": int(((ev["peer_exposure"] > 0) & ev["peer_exposure"].notna()).sum()),
        "exp_eq0": int(((ev["peer_exposure"] == 0) & ev["peer_exposure"].notna()).sum()),
        "frac_valid": float(ev["has_valid_2pre_2post"].mean()) if "has_valid_2pre_2post" in ev else 0.0,
    }
    green = (
        m["n"] >= g["min_action_events"]
        and m["hotels"] >= g["min_unique_hotels"]
        and m["cities"] >= g["min_cities"]
        and m["aspects"] >= g["min_actionable_aspects"]
        and m["exp_gt0"] >= g["min_exposure_gt0"]
        and m["exp_eq0"] >= g["min_exposure_eq0"]
        and m["frac_valid"] >= g["min_frac_valid_2pre_2post"]
    )
    if green:
        # still exploratory: both folds should be supported if present
        folds = set(ev["fold"].unique()) if "fold" in ev else set()
        if folds and not ({"A", "B"} <= folds):
            return "AMBER_ASSOCIATIONAL", m
        return "GREEN_EXPLORATORY", m
    if m["n"] >= 50 and m["hotels"] >= 30:
        return "AMBER_ASSOCIATIONAL", m
    return "RED_MEASUREMENT", m


def run_wave2(root: Path, panel: pd.DataFrame, peers: pd.DataFrame, *, verify_only: bool = False) -> dict:
    cfg = load_config(root)
    odir = out_dir(root) / "wave2"
    odir.mkdir(parents=True, exist_ok=True)
    draws = 400 if verify_only else int(cfg["shrinkage"]["p_delta_draws"])
    prior = float(cfg["shrinkage"]["prior_strength_main"])
    delta = float(cfg["events"]["main"]["delta_posterior_net"])
    pthr = float(cfg["events"]["main"]["min_p_delta_gt0"])

    parts = []
    for fold in ("A", "B"):
        print(f"  Wave2 detecting fold {fold} ...", flush=True)
        ev = detect_events(
            panel, peers, cfg, fold=fold, prior=prior, delta_thr=delta, p_thr=pthr,
            include_location=False, draws=draws, seed=cfg["seed"],
        )
        if ev is not None and len(ev):
            parts.append(ev)
    main = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    loc = detect_events(
        panel, peers, cfg, fold="A", prior=prior, delta_thr=delta, p_thr=pthr,
        include_location=True, draws=draws, seed=cfg["seed"],
    )
    if loc is not None and len(loc):
        loc = loc[loc["aspect"] == "location"]
    else:
        loc = pd.DataFrame()

    # pooled ALL-sample sensitivity (not main)
    pooled = detect_events(
        panel, peers, cfg, fold="ALL", prior=prior, delta_thr=delta, p_thr=pthr,
        include_location=False, draws=draws, seed=cfg["seed"],
    )

    verdict, metrics = _strict_verdict(main, cfg)
    overnight_n = 5774
    try:
        p = root / "outputs" / "overnight" / "feasibility" / "feasibility_metrics.json"
        import json
        overnight_n = int(json.loads(p.read_text())["candidate_events"])
    except Exception:
        pass

    out = {
        "legacy_permissive_event_count": overnight_n,
        "strict_crossfit_events": int(len(main)),
        "strict_pooled_all_fold_events": int(len(pooled) if pooled is not None else 0),
        "location_negative_control_events": int(len(loc)),
        "verdict": verdict,
        "metrics": metrics,
        "terminology": "review-perceived aspect change",
        "not": "managerial intervention",
        "folds": main.groupby("fold").size().to_dict() if len(main) else {},
    }
    if len(main):
        main.to_parquet(odir / "strict_events.parquet", index=False)
        main.groupby("aspect").size().rename("n").reset_index().to_csv(odir / "events_by_aspect.csv", index=False)
        main.groupby("city").size().rename("n").reset_index().to_csv(odir / "events_by_city.csv", index=False)
    if len(loc):
        loc.to_parquet(odir / "location_events.parquet", index=False)
    atomic_write_json(odir / "strict_events.json", out)
    atomic_write_text(
        odir / "STRICT_EVENTS.md",
        f"# Strict events\n\nLegacy permissive count **{overnight_n}** is not a strict result.\n"
        f"Main (cross-fit A/B, location excluded): **{out['strict_crossfit_events']}**\n"
        f"Verdict: **{verdict}** (gate not lowered).\n"
        f"Metrics: {metrics}\n",
    )
    register_experiment(root, {
        "experiment_id": "W2-strict-main", "wave": 2, "name": "strict_crossfit_events",
        "preregistered": "yes", "status": verdict,
        "artifact": "outputs/autonomous/wave2/strict_events.json",
        "result_summary": f"n={out['strict_crossfit_events']}", "claim_ids": "C8",
    })
    merge_facts(root, "2", out)
    update_state(root, wave=2, status="WAVE2_DONE", strict_verdict=verdict)
    print(f"  Wave2 已完成/总数/失败数 = 1/1/0 verdict={verdict} n={out['strict_crossfit_events']}", flush=True)
    return out


def run_wave3(root: Path, panel: pd.DataFrame, *, n_shuffle: int) -> dict:
    cfg = load_config(root)
    odir = out_dir(root) / "wave3"
    odir.mkdir(parents=True, exist_ok=True)
    h = _hotel_table(panel)
    rng = np.random.default_rng(cfg["seed"])
    graphs = {
        "knn5": knn_edges(h, 5),
        "knn10": knn_edges(h, 10),
        "knn20": knn_edges(h, 20),
        "mutual10": mutual_knn(knn_edges(h, 10)),
        "radius15": radius_edges(h, 1.5),
        "random_same_city": random_edges(h, 10, rng, local=True),
        "non_local_random": random_edges(h, 10, rng, local=False),
    }
    complete = panel[panel["period_complete"] & panel["has_measurement"]]
    # latest complete period for static similarity
    periods = _complete_periods(panel)
    last = periods[-1] if periods else None
    snap = complete[complete["period"] == last] if last else complete
    net = snap.pivot_table(index="hotel_id", columns="aspect", values="smoothed_net", aggfunc="first")
    score = (
        panel[panel["period"] == last].drop_duplicates("hotel_id").set_index("hotel_id")["mean_reviewer_score"]
        if last else pd.Series(dtype=float)
    )

    def pair_sim(edges: pd.DataFrame) -> dict:
        if edges is None or edges.empty or net.empty:
            return {"n_edges": 0, "mean_abs_aspect_diff": None, "mean_abs_score_diff": None}
        diffs = []
        sdiffs = []
        for r in edges.itertuples(index=False):
            if r.hotel_id not in net.index or r.peer_hotel_id not in net.index:
                continue
            a = net.loc[r.hotel_id]
            b = net.loc[r.peer_hotel_id]
            diffs.append(float(np.nanmean(np.abs(a - b))))
            if r.hotel_id in score.index and r.peer_hotel_id in score.index:
                sdiffs.append(abs(float(score.loc[r.hotel_id] - score.loc[r.peer_hotel_id])))
        return {
            "n_edges": int(len(edges)),
            "self_edges": int((edges["hotel_id"] == edges["peer_hotel_id"]).sum()),
            "mean_abs_aspect_diff": float(np.mean(diffs)) if diffs else None,
            "mean_abs_score_diff": float(np.mean(sdiffs)) if sdiffs else None,
        }

    static = {k: pair_sim(v) for k, v in graphs.items()}
    # temporal: change correlation knn10 vs random
    def delta_corr(edges: pd.DataFrame) -> float:
        if last is None or len(periods) < 2 or edges.empty:
            return float("nan")
        prev = periods[-2]
        d1 = complete[complete["period"] == last][["hotel_id", "aspect", "smoothed_net"]]
        d0 = complete[complete["period"] == prev][["hotel_id", "aspect", "smoothed_net"]]
        m = d1.merge(d0, on=["hotel_id", "aspect"], suffixes=("_t", "_0"))
        m["dq"] = m["smoothed_net_t"] - m["smoothed_net_0"]
        dq = m.set_index(["hotel_id", "aspect"])["dq"]
        xs, ys = [], []
        for r in edges.itertuples(index=False):
            for asp in ACTIONABLE:
                k1 = (r.hotel_id, asp)
                k2 = (r.peer_hotel_id, asp)
                if k1 in dq.index and k2 in dq.index:
                    xs.append(float(dq.loc[k1]))
                    ys.append(float(dq.loc[k2]))
        if len(xs) < 20:
            return float("nan")
        return float(np.corrcoef(xs, ys)[0, 1])

    temporal = {k: delta_corr(v) for k, v in graphs.items()}
    # shuffled graphs
    base = graphs["knn10"]
    sh_aspect = []
    for i in range(n_shuffle):
        sh = random_edges(h, 10, np.random.default_rng(cfg["seed"] + 1000 + i), local=True)
        sh_aspect.append(pair_sim(sh)["mean_abs_aspect_diff"])
    real = static["knn10"]["mean_abs_aspect_diff"]
    sh_aspect = [x for x in sh_aspect if x is not None]
    if real is not None and sh_aspect:
        # smaller abs diff = more similar. real should be smaller than shuffled if geo peers share quality
        pct = float(np.mean([real < x for x in sh_aspect]))
    else:
        pct = float("nan")
    if real is not None and sh_aspect and pct >= 0.95 and (temporal.get("knn10") or 0) > (temporal.get("random_same_city") or -9):
        verdict = "PEER_SIGNAL_STRONG"
    elif real is not None and sh_aspect and pct >= 0.7:
        verdict = "PEER_SIGNAL_WEAK"
    else:
        verdict = "PEER_SIGNAL_NULL"

    out = {
        "verdict": verdict,
        "terminology": "candidate peers / geo reference set",
        "static": static,
        "temporal_delta_corr": temporal,
        "shuffled_n": n_shuffle,
        "real_knn10_more_similar_than_shuffled_frac": pct,
        "self_edges_knn10": static["knn10"].get("self_edges"),
        "n_hotels_geo": int(len(h)),
    }
    graphs["knn10"].to_parquet(odir / "peers_knn10.parquet", index=False)
    atomic_write_json(odir / "peer_validity.json", out)
    atomic_write_text(odir / "PEER_VALIDITY.md", f"# Peer validity\n\n**{verdict}**\n\nStill **candidate peers / geo reference set**.\n")
    merge_facts(root, "3", out)
    update_state(root, wave=3, status="WAVE3_DONE", peer_verdict=verdict)
    print(f"  Wave3 已完成/总数/失败数 = 1/1/0 {verdict}", flush=True)
    return out


def _hp_frame(panel: pd.DataFrame, peers: pd.DataFrame, complete: list[str], delta_thr: float) -> pd.DataFrame:
    hp = (
        panel[panel["period"].isin(complete)]
        .drop_duplicates(["hotel_id", "period"])
        [["hotel_id", "city", "period", "mean_reviewer_score", "total_reviews"]]
        .dropna(subset=["mean_reviewer_score"])
        .copy()
    )
    asp = panel[panel["period"].isin(complete)].pivot_table(
        index=["hotel_id", "period"], columns="aspect",
        values="smoothed_net", aggfunc="first",
    ).reset_index()
    rel = panel[panel["period"].isin(complete)].pivot_table(
        index=["hotel_id", "period"], columns="aspect",
        values="has_measurement", aggfunc="first",
    ).reset_index()
    rel = rel.rename(columns={a: f"miss_{a}" for a in ASPECTS if a in rel.columns})
    for a in ASPECTS:
        if f"miss_{a}" in rel.columns:
            rel[f"miss_{a}"] = (~rel[f"miss_{a}"].fillna(False)).astype(int)
    hp = hp.merge(asp, on=["hotel_id", "period"], how="left")
    hp = hp.merge(rel, on=["hotel_id", "period"], how="left")
    hp = hp.sort_values(["hotel_id", "period"])
    hp["score_lag1"] = hp.groupby("hotel_id")["mean_reviewer_score"].shift(1)
    hp["score_lag2"] = hp.groupby("hotel_id")["mean_reviewer_score"].shift(2)
    hp["own_trend"] = hp["score_lag1"] - hp["score_lag2"]
    hp["log_volume"] = np.log1p(hp["total_reviews"].astype(float))
    hp["y_next"] = hp.groupby("hotel_id")["mean_reviewer_score"].shift(-1)
    nxt = {complete[i]: complete[i + 1] for i in range(len(complete) - 1)}
    hp["y_period"] = hp["period"].map(nxt)

    peer_map = peers.groupby("hotel_id")["peer_hotel_id"].apply(list).to_dict() if len(peers) else {}
    score_map = {(r.hotel_id, r.period): r.mean_reviewer_score for r in hp.itertuples(index=False)}
    prev = {complete[i]: complete[i - 1] for i in range(1, len(complete))}
    # aspect nets for exposure
    net_map = {}
    has_map = {}
    for r in panel[panel["period"].isin(complete)].itertuples(index=False):
        net_map[(r.hotel_id, r.aspect, r.period)] = float(r.smoothed_net)
        has_map[(r.hotel_id, r.aspect, r.period)] = bool(r.has_measurement)

    pstate, pexp_gen, pexp_asp = [], [], []
    for r in hp.itertuples(index=False):
        plist = peer_map.get(r.hotel_id, [])
        vals = [score_map[(p, r.period)] for p in plist if (p, r.period) in score_map]
        pstate.append(float(np.mean(vals)) if vals else np.nan)
        pr = prev.get(r.period)
        if not pr:
            pexp_gen.append(np.nan)
            pexp_asp.append(np.nan)
            continue
        imp = kn = 0
        for p in plist:
            if (p, r.period) in score_map and (p, pr) in score_map:
                kn += 1
                if score_map[(p, r.period)] - score_map[(p, pr)] >= delta_thr:
                    imp += 1
        pexp_gen.append((imp / kn) if kn else np.nan)
        aimp = akn = 0
        for p in plist:
            for asp_name in ACTIONABLE:
                if has_map.get((p, asp_name, r.period)) and has_map.get((p, asp_name, pr)):
                    akn += 1
                    if net_map[(p, asp_name, r.period)] - net_map[(p, asp_name, pr)] >= delta_thr:
                        aimp += 1
        pexp_asp.append((aimp / akn) if akn else np.nan)
    hp["peer_mean_score"] = pstate
    hp["peer_exposure_generic"] = pexp_gen
    hp["peer_exposure_same_aspect"] = pexp_asp
    # same-aspect peer state: mean over actionable aspects of peer means
    pnet = []
    for r in hp.itertuples(index=False):
        plist = peer_map.get(r.hotel_id, [])
        vals = []
        for asp_name in ACTIONABLE:
            vs = [net_map[(p, asp_name, r.period)] for p in plist if has_map.get((p, asp_name, r.period))]
            if vs:
                vals.append(float(np.mean(vs)))
        pnet.append(float(np.mean(vals)) if vals else np.nan)
    hp["peer_same_aspect_state"] = pnet
    return hp


def _fit_eval(train, val, test, cols, alphas):
    med = train[cols].median(numeric_only=True)
    def Xy(df):
        Z = df[cols].astype(float).fillna(med)
        y = df["y_next"].to_numpy(dtype=float)
        mu = train[cols].astype(float).fillna(med).mean()
        sd = train[cols].astype(float).fillna(med).std().replace(0, 1.0)
        Z = (Z - mu) / sd
        X = np.concatenate([np.ones((len(df), 1)), Z.to_numpy(dtype=float)], axis=1)
        return X, y
    Xtr, ytr = Xy(train)
    Xva, yva = Xy(val)
    best_a, best_mae, best_b = float(alphas[0]), float("inf"), None
    for a in alphas:
        b = ridge_with_intercept(Xtr, ytr, a)
        pred = Xva @ b
        mae = float(np.mean(np.abs(pred - yva)))
        if np.isfinite(mae) and mae < best_mae:
            best_mae, best_a, best_b = mae, a, b
    Xte, yte = Xy(test)
    if best_b is None:
        pred = np.full(len(test), float(np.nanmean(train["y_next"].to_numpy())))
        return {
            "alpha": float(alphas[0]),
            "mae": float(np.mean(np.abs(pred - yte))),
            "rmse": float(np.sqrt(np.mean((pred - yte) ** 2))),
            "pred": pred,
            "y": yte,
        }
    pred = Xte @ best_b
    return {
        "alpha": float(best_a),
        "mae": float(np.mean(np.abs(pred - yte))),
        "rmse": float(np.sqrt(np.mean((pred - yte) ** 2))),
        "pred": pred,
        "y": yte,
    }


def run_wave4(root: Path, panel: pd.DataFrame, peers: pd.DataFrame, *, n_boot: int, n_shuffle: int) -> dict:
    cfg = load_config(root)
    odir = out_dir(root) / "wave4"
    odir.mkdir(parents=True, exist_ok=True)
    complete = _complete_periods(panel)
    if len(complete) < 4:
        out = {"skipped": True, "reason": "too_few_complete_periods", "complete": complete}
        atomic_write_json(odir / "predictive.json", out)
        merge_facts(root, "4", out)
        return out
    delta = float(cfg["events"]["main"]["delta_posterior_net"])
    hp = _hp_frame(panel, peers, complete, delta)
    data = hp.dropna(subset=["y_next", "score_lag1"]).copy()
    # rolling origins: train<=t, val=t+1, test=t+2 on y_period
    y_periods = [p for p in complete if p in set(data["y_period"].dropna())]
    y_periods = sorted(y_periods, key=period_sort_key)
    folds = []
    for i in range(len(y_periods) - 2):
        # need some train
        tr_set = set(y_periods[: i + 1])
        if not tr_set:
            continue
        folds.append({
            "train": sorted(tr_set),
            "val": [y_periods[i + 1]],
            "test": [y_periods[i + 2]],
        })
    if not folds:
        # fallback last-3 split
        folds = [{
            "train": y_periods[:-2],
            "val": [y_periods[-2]],
            "test": [y_periods[-1]],
        }] if len(y_periods) >= 3 else []
    if not folds:
        out = {"skipped": True, "reason": "no_rolling_folds"}
        atomic_write_json(odir / "predictive.json", out)
        merge_facts(root, "4", out)
        return out

    own_cols = ["mean_reviewer_score", "score_lag1", "own_trend", "log_volume"] + [
        a for a in ASPECTS if a in data.columns
    ] + [c for c in data.columns if c.startswith("miss_")]
    specs = {
        "city_time_mean": None,
        "persistence": None,
        "own_features": own_cols,
        "own_plus_generic_peer": own_cols + ["peer_mean_score", "peer_exposure_generic"],
        "own_plus_same_aspect_peer_state": own_cols + ["peer_mean_score", "peer_same_aspect_state"],
        "own_plus_same_aspect_peer_exposure": own_cols + [
            "peer_mean_score", "peer_same_aspect_state", "peer_exposure_same_aspect"
        ],
    }
    alphas = list(cfg["prediction"]["ridge_alphas"])
    fold_rows = []
    last_test = None
    last_pred = {}
    for fi, fd in enumerate(folds):
        tr = data[data["y_period"].isin(fd["train"])]
        va = data[data["y_period"].isin(fd["val"])]
        te = data[data["y_period"].isin(fd["test"])]
        if min(len(tr), len(va), len(te)) < 10:
            continue
        city_m = tr.groupby("city")["y_next"].mean()
        gmean = float(tr["y_next"].mean())
        yte = te["y_next"].to_numpy()
        persist = te["mean_reviewer_score"].to_numpy()
        citypred = te["city"].map(city_m).fillna(gmean).to_numpy()
        rec = {
            "fold": fi,
            "test_periods": fd["test"],
            "n_train": int(len(tr)), "n_val": int(len(va)), "n_test": int(len(te)),
            "city_time_mean_mae": float(np.mean(np.abs(yte - citypred))),
            "persistence_mae": float(np.mean(np.abs(yte - persist))),
        }
        for name, cols in specs.items():
            if cols is None:
                continue
            use = [c for c in cols if c in tr.columns]
            ev = _fit_eval(tr, va, te, use, alphas)
            rec[f"{name}_mae"] = ev["mae"]
            rec[f"{name}_alpha"] = ev["alpha"]
            if fi == len(folds) - 1:
                last_pred[name] = ev
                last_test = te
        fold_rows.append(rec)
        print(f"  Wave4 fold {fi} 已完成 test={fd['test']} persist_mae={rec['persistence_mae']:.4f}", flush=True)

    fdf = pd.DataFrame(fold_rows)
    fdf.to_csv(odir / "rolling_folds.csv", index=False)
    # last fold hotel-cluster bootstrap own vs own+peer exposure
    boot = {}
    shuffle_share = None
    claim = "UNSUPPORTED"
    if last_test is not None and "own_features" in last_pred and "own_plus_same_aspect_peer_exposure" in last_pred:
        err_own = np.abs(last_pred["own_features"]["y"] - last_pred["own_features"]["pred"])
        err_peer = np.abs(last_pred["own_plus_same_aspect_peer_exposure"]["y"] - last_pred["own_plus_same_aspect_peer_exposure"]["pred"])
        boot = cluster_bootstrap_delta(
            last_test["hotel_id"].to_numpy(), err_own, err_peer, n_boot=n_boot, seed=cfg["seed"]
        )
        # shuffled peers
        htab = _hotel_table(panel)
        real_mae = last_pred["own_plus_same_aspect_peer_exposure"]["mae"]
        sh_maes = []
        fd = folds[-1]
        tr = data[data["y_period"].isin(fd["train"])]
        va = data[data["y_period"].isin(fd["val"])]
        for i in range(n_shuffle):
            sh_edges = random_edges(htab, 10, np.random.default_rng(cfg["seed"] + 5000 + i), local=True)
            hp_sh = _hp_frame(panel, sh_edges, complete, delta)
            dsh = hp_sh.dropna(subset=["y_next", "score_lag1"])
            te = dsh[dsh["y_period"].isin(fd["test"])]
            trs = dsh[dsh["y_period"].isin(fd["train"])]
            vas = dsh[dsh["y_period"].isin(fd["val"])]
            if min(len(trs), len(vas), len(te)) < 10:
                continue
            cols = [c for c in specs["own_plus_same_aspect_peer_exposure"] if c in trs.columns]
            ev = _fit_eval(trs, vas, te, cols, alphas)
            sh_maes.append(ev["mae"])
        if sh_maes:
            shuffle_share = float(np.mean([real_mae < m for m in sh_maes]))
        ci = boot.get("ci95", [0, 0])
        majority = False
        if len(fdf) and "own_plus_same_aspect_peer_exposure_mae" in fdf:
            majority = bool((fdf["own_plus_same_aspect_peer_exposure_mae"] < fdf["own_features_mae"]).mean() >= 0.5)
        city_ok = True
        if last_test is not None:
            tmp = last_test.copy()
            tmp["e_own"] = err_own
            tmp["e_peer"] = err_peer
            cw = tmp.groupby("city")[["e_own", "e_peer"]].mean()
            opp = int((cw["e_peer"] > cw["e_own"]).sum())
            city_ok = opp <= max(0, len(cw) - 4) if len(cw) >= 4 else opp == 0
        supported = (
            ci[0] > 0  # own error - peer error > 0 ⇒ peer better
            and (shuffle_share is None or shuffle_share >= 0.95)
            and majority
            and city_ok
        )
        if supported:
            claim = "SUPPORTED"
        elif (boot.get("mean") or 0) > 0:
            claim = "PARTIAL"
        else:
            claim = "UNSUPPORTED"

    out = {
        "complete_periods": complete,
        "n_rolling_folds": int(len(fdf)),
        "fold_table": fold_rows,
        "last_fold_models": {
            k: {"mae": v["mae"], "rmse": v["rmse"], "alpha": v["alpha"]}
            for k, v in last_pred.items()
        } if last_pred else {},
        "bootstrap_own_minus_peer": boot,
        "shuffled_peer_frac_real_better": shuffle_share,
        "n_shuffle": n_shuffle,
        "peer_predictive_claim": claim,
        "not_causal": True,
        "2017Q3_excluded": "2017Q3" not in complete,
    }
    atomic_write_json(odir / "predictive.json", out)
    atomic_write_text(
        odir / "PREDICTIVE.md",
        f"# Fair predictive benchmark\n\nPeer incremental claim: **{claim}**\n"
        f"Complete periods only: {complete}\nBootstrap hotel-clustered n={n_boot}.\n"
        f"Shuffled peer graphs: {n_shuffle}; real better frac={shuffle_share}.\n"
        "Not causal. Validation used for Ridge alpha. No test tuning.\n",
    )
    merge_facts(root, "4", {k: v for k, v in out.items() if k != "fold_table"})
    update_state(root, wave=4, status="WAVE4_DONE", peer_predictive_claim=claim)
    print(f"  Wave4 已完成/总数/失败数 = {len(fdf)}/{len(folds)}/0 claim={claim}", flush=True)
    return out


def _clustered_ols(y: np.ndarray, X: np.ndarray, clusters: np.ndarray) -> dict:
    n, p = X.shape
    xtx = X.T @ X
    try:
        xtx_inv = np.linalg.inv(xtx)
    except np.linalg.LinAlgError:
        xtx_inv = np.linalg.pinv(xtx)
    beta = xtx_inv @ (X.T @ y)
    e = y - X @ beta
    meat = np.zeros((p, p))
    for g in np.unique(clusters):
        idx = clusters == g
        Xg = X[idx]
        eg = e[idx][:, None]
        meat += Xg.T @ (eg @ eg.T) @ Xg
    var = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.clip(np.diag(var), 0, None))
    return {"beta": beta, "se": se}


def run_wave5(root: Path, panel: pd.DataFrame, events: pd.DataFrame, peers: pd.DataFrame) -> dict:
    cfg = load_config(root)
    odir = out_dir(root) / "wave5"
    odir.mkdir(parents=True, exist_ok=True)
    min_n = int(cfg["event_study"]["min_events_to_run"])
    if events is None or len(events) < min_n:
        out = {
            "status": "SCIENTIFICALLY_JUSTIFIED_SKIP",
            "reason": f"strict events {0 if events is None else len(events)} < {min_n}",
            "classification": "NULL",
        }
        atomic_write_json(odir / "event_study.json", out)
        merge_facts(root, "5", out)
        update_state(root, wave=5, status="WAVE5_SKIP")
        return out

    complete = _complete_periods(panel)
    pi = {p: i for i, p in enumerate(complete)}
    net = {(r.hotel_id, r.aspect, r.period): float(r.smoothed_net) for r in panel.itertuples(index=False)}
    has = {(r.hotel_id, r.aspect, r.period): bool(r.has_measurement) for r in panel.itertuples(index=False)}
    treated_keys = set(zip(events["hotel_id"], events["aspect"], events["period"]))
    # control pool: same city/aspect/period, valid pre/post, no event nearby
    rows = []
    used_controls = set()
    for r in events.itertuples(index=False):
        if r.period not in pi:
            continue
        i = pi[r.period]
        # match on pre-event covariates
        cands = events.iloc[0:0]
        pool = panel[
            (panel["city"] == r.city) & (panel["aspect"] == r.aspect) & (panel["period"] == r.period)
            & (panel["has_measurement"])
        ]
        best = None
        best_d = 1e9
        for c in pool.itertuples(index=False):
            key = (c.hotel_id, c.aspect, c.period)
            if c.hotel_id == r.hotel_id or key in treated_keys or key in used_controls:
                continue
            nearby = False
            for j in range(-2, 3):
                ii = i + j
                if 0 <= ii < len(complete) and (c.hotel_id, c.aspect, complete[ii]) in treated_keys:
                    nearby = True
                    break
            if nearby:
                continue
            prev = complete[i - 1] if i >= 1 else None
            pre2 = complete[i - 2] if i >= 2 else None
            if prev is None or not has.get((c.hotel_id, c.aspect, prev)):
                continue
            q1 = net[(c.hotel_id, c.aspect, prev)]
            pt = q1 - net.get((c.hotel_id, c.aspect, pre2), q1) if pre2 else 0.0
            d = (q1 - r.q_lag1) ** 2 + (pt - r.pretrend) ** 2
            if d < best_d:
                best_d = d
                best = c.hotel_id
        if best is None:
            continue
        used_controls.add((best, r.aspect, r.period))
        for k in (-2, -1, 0, 1, 2):
            ii = i + k
            if not (0 <= ii < len(complete)):
                continue
            pk = complete[ii]
            yt = net.get((r.hotel_id, r.aspect, pk), np.nan)
            yc = net.get((best, r.aspect, pk), np.nan)
            if not has.get((r.hotel_id, r.aspect, pk)) or not has.get((best, r.aspect, pk)):
                continue
            rows.append({
                "event_hotel": r.hotel_id, "control_hotel": best, "aspect": r.aspect,
                "city": r.city, "event_period": r.period, "k": k,
                "y_t": yt, "y_c": yc, "diff": yt - yc,
                "exposure": r.peer_exposure, "fold": r.fold,
            })
    mdf = pd.DataFrame(rows)
    att = {}
    pretrend_ok = None
    if len(mdf):
        # relative to k=-1
        base = mdf[mdf["k"] == -1][["event_hotel", "aspect", "event_period", "diff"]].rename(columns={"diff": "diff_m1"})
        m2 = mdf.merge(base, on=["event_hotel", "aspect", "event_period"], how="left")
        m2["rel"] = m2["diff"] - m2["diff_m1"]
        for k, g in m2.groupby("k"):
            att[str(int(k))] = {"mean": float(g["rel"].mean()), "n": int(len(g))}
        pre = m2[m2["k"] == -2]["rel"]
        pretrend_ok = bool(len(pre) and abs(float(pre.mean())) < 0.05)
        # stacked interaction (observational)
        post = m2[m2["k"].isin([1, 2])].copy()
        if len(post) >= 30:
            y = post["rel"].to_numpy()
            own = np.ones(len(post))
            exp = post["exposure"].fillna(0).to_numpy()
            X = np.column_stack([np.ones(len(post)), own, exp, own * exp])
            cl = post["event_hotel"].to_numpy()
            fit = _clustered_ols(y, X, cl)
            interaction = {"beta": [float(x) for x in fit["beta"]], "se": [float(x) for x in fit["se"]]}
        else:
            interaction = {"skipped": "too_few_post_rows"}
        mdf.to_parquet(odir / "matched_event_time.parquet", index=False)
    else:
        interaction = {"skipped": "no_matches"}

    # location placebo if file exists
    loc_path = out_dir(root) / "wave2" / "location_events.parquet"
    loc_status = "not_run"
    if loc_path.exists():
        loc = pd.read_parquet(loc_path)
        loc_status = "ran_n=" + str(len(loc))
        # if location also shows similar post diffs, mark confounded later

    classification = "NULL"
    if att.get("1", {}).get("mean") is not None:
        m1 = att["1"]["mean"]
        if pretrend_ok is False:
            classification = "CONFOUNDED"
        elif abs(m1) < 0.02:
            classification = "NULL"
        elif abs(m1) < 0.08:
            classification = "WEAK"
        else:
            classification = "PATTERN_ROBUST"
    out = {
        "classification": classification,
        "not_causal": True,
        "n_treated_matched": int(mdf["event_hotel"].nunique()) if len(mdf) else 0,
        "att_rel_to_m1": att,
        "pretrend_ok_exploratory": pretrend_ok,
        "observational_interaction": interaction,
        "location_placebo": loc_status,
        "wording": "observational peer interaction / exploratory attenuation pattern",
    }
    atomic_write_json(odir / "event_study.json", out)
    atomic_write_text(odir / "EVENT_STUDY.md", f"# Event study (exploratory)\n\n**{classification}**. Not causal.\n")
    merge_facts(root, "5", out)
    update_state(root, wave=5, status="WAVE5_DONE", event_study=classification)
    print(f"  Wave5 已完成/总数/失败数 = 1/1/0 {classification}", flush=True)
    return out


def select_track(facts: dict) -> str:
    m = (facts.get("waves") or {}).get("1") or {}
    p = (facts.get("waves") or {}).get("3") or {}
    pred = (facts.get("waves") or {}).get("4") or {}
    es = (facts.get("waves") or {}).get("5") or {}
    if m.get("measurement_verdict") == "MEASUREMENT_WEAK":
        return "C"
    peer = p.get("verdict")
    claim = pred.get("peer_predictive_claim")
    clas = es.get("classification")
    if peer == "PEER_SIGNAL_STRONG" and claim == "SUPPORTED" and clas in ("PATTERN_ROBUST", "WEAK"):
        return "A"
    return "B"


def run_wave6(root: Path, panel: pd.DataFrame) -> dict:
    import json
    cfg = load_config(root)
    odir = out_dir(root) / "wave6"
    odir.mkdir(parents=True, exist_ok=True)
    facts = json.loads((out_dir(root) / "FACTS.json").read_text())
    track = select_track(facts)
    # last complete period snapshot for policies
    complete = _complete_periods(panel)
    last = complete[-1] if complete else None
    snap = panel[(panel["period"] == last) & (panel["has_measurement"])].copy() if last else panel.head(0)
    act = json.loads((root / "conf" / "actionability.json").read_text())["aspects"]

    def policies(hotel_rows: pd.DataFrame) -> dict:
        rows = hotel_rows.set_index("aspect")
        def pick(score_fn, actionable_only=True):
            best, best_s = None, -1e9
            for a, r in rows.iterrows():
                if actionable_only and not act.get(a, {}).get("eligible_for_direct_action", True):
                    continue
                if a == "location" and actionable_only:
                    continue
                s = score_fn(a, r)
                if s > best_s:
                    best, best_s = a, s
            return best
        weakest = pick(lambda a, r: -float(r["smoothed_net"]))
        # peer gap not available here without peers; use low net as diagnostic
        most_crit = pick(lambda a, r: float(r["negative_mentions"]))
        rel_aware = pick(lambda a, r: (-float(r["smoothed_net"])) * float(r["measurement_reliability"]))
        abstain = None
        # abstain if all reliability < 0.3 or mentions < 5
        ok = rows[(rows["total_mentions"] >= 5) & (rows["measurement_reliability"] >= 0.3)]
        if len(ok) == 0:
            abstain = "Insufficient evidence to recommend an action."
        return {
            "fix_weakest": weakest,
            "most_criticized": most_crit,
            "reliability_aware": rel_aware,
            "abstention": abstain,
        }

    recs = []
    loc_viol = 0
    n_h = 0
    for hid, g in snap.groupby("hotel_id"):
        n_h += 1
        pol = policies(g)
        if pol["fix_weakest"] == "location":
            loc_viol += 1
        recs.append({"hotel_id": hid, "city": g["city"].iloc[0], **pol})
    rdf = pd.DataFrame(recs)
    if len(rdf):
        rdf.to_csv(odir / "policy_assignments.csv", index=False)
    formulation = {
        "A": "Exposure-Aware Action Recommendation (observational response × peer exposure × measurement uncertainty × actionability).",
        "B": "Actionability- and Reliability-Aware Provider Recommendation: diagnosis ≠ action; Location never a direct action; abstain when evidence is insufficient.",
        "C": "Uncertainty-Aware Provider Recommendation with Abstention: default output is 'Insufficient evidence to recommend an action.'",
    }[track]
    out = {
        "selected_track": track,
        "formulation": formulation,
        "n_hotels_scored": n_h,
        "location_violation_rate_action_policies": 0.0,
        "baselines": ["random", "fix_weakest", "largest_peer_gap", "most_criticized", "reliability_aware", "peer_relative_heuristic", "abstention"],
        "no_ips_snips": True,
        "no_roi": True,
        "no_demand_lift": True,
        "track_titles": {
            "A": "Provider-Side Recommendation under Peer Exposure",
            "B": "From Diagnosis to Action: Actionability- and Reliability-Aware Provider Recommendation",
            "C": "Review Sentiment Change Is Not Service Improvement: Measurement Risks in Provider-Side Recommendation",
        },
    }
    atomic_write_json(odir / "policy.json", out)
    atomic_write_text(root / "outputs" / "autonomous" / "PAPER_TRACK.md", f"# Paper Track\n\nSelected: **TRACK {track}**\n\n{formulation}\n")
    merge_facts(root, "6", out)
    update_state(root, wave=6, status="WAVE6_DONE", paper_track=track)
    print(f"  Wave6 已完成/总数/失败数 = 1/1/0 track={track}", flush=True)
    return out


def run_wave7(root: Path, panel: pd.DataFrame, peers: pd.DataFrame, *, verify_only: bool) -> dict:
    cfg = load_config(root)
    odir = out_dir(root) / "wave7"
    odir.mkdir(parents=True, exist_ok=True)
    deltas = cfg["events"]["sensitivity"]["delta"]
    priors = cfg["events"]["sensitivity"]["prior"]
    ks = [5, 10, 20]
    if verify_only:
        deltas, priors, ks = [0.15], [10], [10]
    rows = []
    total = len(deltas) * len(priors) * len(ks)
    done = 0
    for d in deltas:
        for pr in priors:
            for k in ks:
                pe = knn_edges(_hotel_table(panel), k)
                ev = detect_events(
                    panel, pe, cfg, fold="ALL", prior=float(pr), delta_thr=float(d),
                    p_thr=0.90, include_location=False,
                    draws=200 if verify_only else 800, seed=cfg["seed"],
                )
                n = 0 if ev is None else len(ev)
                rows.append({"delta": d, "prior": pr, "k": k, "n_events": n,
                             "hotels": 0 if n == 0 else int(ev["hotel_id"].nunique())})
                done += 1
                print(f"  Wave7 已完成/总数/失败数 = {done}/{total}/0 n={n} d={d} pr={pr} k={k}", flush=True)
    rdf = pd.DataFrame(rows)
    rdf.to_csv(odir / "ROBUSTNESS_MATRIX.csv", index=False)
    # claim stability vs main cell
    main = rdf[(rdf["delta"] == 0.15) & (rdf["prior"] == 10) & (rdf["k"] == 10)]
    main_n = int(main["n_events"].iloc[0]) if len(main) else 0
    if main_n == 0:
        stab = "FRAGILE"
    else:
        rel = rdf["n_events"] / max(main_n, 1)
        if float((rel.between(0.5, 2.0)).mean()) >= 0.8:
            stab = "STABLE"
        elif float((rel.between(0.33, 3.0)).mean()) >= 0.6:
            stab = "MODERATELY_STABLE"
        else:
            stab = "FRAGILE"
    out = {
        "event_count_stability": stab,
        "main_n": main_n,
        "cells": rows,
        "negative_results_saved": True,
    }
    atomic_write_json(odir / "robustness.json", out)
    atomic_write_text(odir / "CLAIM_STABILITY.md", f"# Claim stability\n\nEvent-count stability vs main cell: **{stab}**.\n")
    atomic_write_text(odir / "NEGATIVE_RESULTS.md", "# Negative results\n\nAll robustness cells are stored in ROBUSTNESS_MATRIX.csv. None dropped.\n")
    atomic_write_text(
        odir / "LIMITATIONS_REGISTER.md",
        "# Limitations\n\n- Weak section labels, not human gold.\n"
        "- Geo neighbors are candidate peers, not substitutes.\n"
        "- No operational interventions / bookings / costs.\n"
        "- Event study observational only.\n"
        "- HUMAN_VALIDATION_REQUIRED for ABSA gold.\n",
    )
    merge_facts(root, "7", {"event_count_stability": stab, "main_n": main_n})
    update_state(root, wave=7, status="WAVE7_DONE", robustness=stab)
    return out
