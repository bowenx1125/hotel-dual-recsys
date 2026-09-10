#!/usr/bin/env python3
"""Write a static HTML view of one hotel for browser screenshots (no websocket)."""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import eligible_hotels, load_snapshot
from demo.evidence import BANNER, decide_evidence_level
from demo.scoring import all_policies, ranking_under_intensity


def pick_hotel(hotels, cfg):
    for h in hotels:
        p = all_policies(h, cfg, 0.0)
        if p["fix_weakest"]["chosen_aspect"] != p["competition_aware"]["chosen_aspect"]:
            return h
    return hotels[0]


def main() -> None:
    snap = load_snapshot(ROOT / "outputs" / "night_demo" / "demo_snapshot.json")
    cfg = snap["config"]
    labels = cfg.get("aspect_labels") or {}
    ev = decide_evidence_level(snap)
    hotel = pick_hotel(eligible_hotels(snap), cfg)
    pol0 = all_policies(hotel, cfg, 0.0)
    rows = []
    for a in cfg["aspects"]:
        r = hotel["aspects"][a]
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(x)) if x is not None else 'missing'}</td>"
                for x in [
                    labels.get(a, a),
                    r.get("net"),
                    r.get("peer_median_net"),
                    r.get("gap"),
                    None if r.get("percentile") is None else round(r["percentile"], 1),
                    r.get("mention_count"),
                    r.get("neg_mentions"),
                    None if r.get("neg_rate") is None else round(r["neg_rate"], 3),
                    round(r.get("reliability") or 0, 3),
                    round(r.get("peer_weakest_share") or 0, 2),
                ]
            )
            + "</tr>"
        )
    cards = []
    for k in ("fix_weakest", "largest_peer_gap", "most_criticized", "competition_aware"):
        a = pol0[k]["chosen_aspect"]
        cards.append(
            f"<div class='card'><div class='k'>{html.escape(pol0[k]['label'])}</div>"
            f"<div class='v'>{html.escape(labels.get(a, a) if a else 'n/a')}</div></div>"
        )
    scen = []
    for g in (0.0, 0.25, 0.5, 0.75, 1.0):
        rnk = ranking_under_intensity(hotel, cfg, g)
        top = labels.get(rnk[0][0], rnk[0][0]) if rnk else "n/a"
        scen.append(f"<tr><td>{g}</td><td>{html.escape(str(top))}</td><td>{rnk[0][1]:.4f}</td></tr>")
    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Provider Demo</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:24px;color:#222}}
.banner{{background:#FDECEC;border:1px solid #C0392B;padding:12px 16px;border-radius:8px}}
.sel{{margin:12px 0;padding:10px;background:#f4f6f8;border-radius:8px}}
.row{{display:flex;gap:12px;flex-wrap:wrap}}
.card{{flex:1;min-width:180px;border:1px solid #ddd;border-radius:8px;padding:12px}}
.k{{font-size:12px;color:#666}} .v{{font-size:20px;font-weight:600}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #ddd;padding:6px 8px;text-align:left}}
.warn{{background:#fff6d6;border:1px solid #e0c35a;padding:10px;border-radius:8px}}
h1{{margin-bottom:4px}}
</style></head><body>
<h1>Competition-Aware Provider-Side Hotel Improvement</h1>
<p>Manager Demo · NOT SYNTHETIC · no external API</p>
<div class="banner"><b>{html.escape(BANNER)}</b><br>level={ev['level']} · {html.escape(ev['why'])}</div>
<div class="sel"><b>Hotel Selector</b> · city={html.escape(hotel['city'])} ·
compset={html.escape(hotel['compset_id'])} · hotel={html.escape(hotel['hotel_name'])}
· hotel_id={html.escape(hotel['hotel_id'])} · peers={hotel['peer_count']}
· labelled reviews={hotel['n_reviews']}<br>
sources: aspect_features.csv · compsets.csv · review_aspects.jsonl</div>
<h2>Hotel vs peers</h2>
<table><thead><tr>
<th>aspect</th><th>hotel_net</th><th>peer_median</th><th>gap</th><th>percentile</th>
<th>mentions</th><th>neg_mentions</th><th>neg_rate</th><th>reliability</th><th>peer_weakest_share</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Four strategies (assumed_intensity=0)</h2>
<div class="row">{''.join(cards)}</div>
<p>Weights: gap={cfg['weights']['gap']}, criticism={cfg['weights']['criticism']},
unreliable={cfg['weights']['unreliable']}. Formula is a heuristic, not a fitted model.</p>
<h2>Peer-exposure scenario</h2>
<div class="warn">SCENARIO ANALYSIS — assumed / illustrative. Not an empirical crowding elasticity.</div>
<table><thead><tr><th>assumed_intensity</th><th>top aspect</th><th>top score</th></tr></thead>
<tbody>{''.join(scen)}</tbody></table>
<h2>Limitations</h2>
<ul>
<li>Review counts are not bookings.</li>
<li>Sentiment is not a verified management intervention.</li>
<li>Peer sets are labelled, not validated substitutes.</li>
<li>No causal estimate or CI is available in this repository.</li>
</ul>
</body></html>
"""
    out = ROOT / "outputs" / "night_demo" / "demo_static.html"
    out.write_text(page, encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
