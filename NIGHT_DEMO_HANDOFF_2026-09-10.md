# Night Demo Handoff — 2026-09-10

## Repository State

| Item | Value |
|---|---|
| repository | `/Users/xubosmell/Desktop/FYP1` |
| branch | `demo/provider-side-20260910-grok` |
| starting HEAD | none (directory was not a git repo) → first commit `be17fc4707c772d8ef19f962c7b9a26c42ca7764` |
| feat commit | `7bcf28be416fffe2b18e1b40ed36a73a78f7030f` |
| final HEAD | bd3198b5d7924ac20609b521170c90a09551301b |
| working tree | see `git status` after docs commit |
| remote | **none**. `gh auth` token in keyring is invalid. Push expected to fail. |

Local git identity (repo-only, not global): `Bowen XU` / `xubosmell@users.noreply.github.com`

## What I Found

- Real processed assets: 24-hotel `aspect_features.csv`, 34-row `compsets.csv`, 3,620-row `review_aspects.jsonl` (no review text), 822-row scrape table.
- ABSA weights exist (`models/absa/model.safetensors`, ~738MB) but were **not** used tonight.
- No time panel, no treatment, no effect estimates, no CI, no tourist ranker, no `run.py`.
- Docs (AUTORUN / PAPER_STRATEGY) describe causal / Figure 1 work that **does not exist on disk**.
- Default brew Python has no pandas; Demo core is stdlib. Streamlit runs in `.venv-demo` (gitignored).

## What I Built

Manager Demo: hotel vs labelled peers, four policies, assumed crowding scenario, DESCRIPTIVE banner, limitations, provenance JSON.

| Path | Role |
|---|---|
| `demo/app.py` | Streamlit UI |
| `demo/data_adapter.py` | CSV/JSONL → snapshot |
| `demo/scoring.py` | Four strategies |
| `demo/evidence.py` | Level gate |
| `conf/demo.json` | Weights / thresholds |
| `scripts/build_demo_snapshot.py` | Snapshot builder |
| `tests/test_demo_*.py` | Adapter / scoring / evidence / smoke |

## Data Used

| File | Rows | In git? | sha256 |
|---|---|---|---|
| `data/processed/aspect_features.csv` | 24 | no (local) | `cade2650c6edbe2181d18aaf7c58b111f039884dd9a3d8bcf650af67af5734aa` |
| `data/processed/compsets.csv` | 34 | no | `598d4488b5a366d7eb56e6d700776800ac39a0f129b0de8dcb3cc7f6a788f6b3` |
| `data/processed/brussels_hotels.csv` | 36 | no | `53f2d9c0fd9c215aeeb261fbcf4a8be0862b901d48ab787baeebfbe35f1a2ca2` |
| `data/processed/review_aspects.jsonl` | 3,620 | no (derived labels; no text, still not committed) | `62331a2c0b320e64b88e6e21a5771680c500d5380b2be8847ece5359ca6c03fc` |
| `outputs/night_demo/demo_snapshot.json` | 24 hotels / 22 eligible | **yes** | aggregated nets/mentions only |

Schema in snapshot: hotel_id, url, name, city, compset_id, n_reviews, n_negative, aspects{net, mention_count, neg_mentions, gap, peer_median_net, percentile, reliability, peer_weakest_share}.

## Evidence Level

**DESCRIPTIVE**

Why: cross-section aspect nets + researcher-defined DBSCAN∩price-tier peer sets. No time-split model. No identified treatment. Filename tokens such as “did” were not treated as causal proof.

Forbidden tonight: causal effect, causal gain, demand lift, ROI, guaranteed improvement.

## Scoring and Policies

Config: `conf/demo.json`

- **Fix Weakest**: argmin aspect net among aspects with `mention_count >= 5`
- **Largest Peer Gap**: argmax (peer_median_net − hotel_net)
- **Most Criticized**: argmax aspect-level negative-sentiment mention count
- **Competition-Aware (heuristic)**:
  `score = 0.45*gap_norm + 0.35*criticism_norm - 0.20*(1-reliability) - assumed_intensity*0.50*peer_weakest_share`
  - `peer_weakest_share` = share of peers whose own weakest eligible aspect is this aspect (descriptive)
  - `assumed_intensity` is a scenario slider, **not** a fitted lambda
  - tie-break: aspect name ascending

## Actual Results

- Eligible hotels: **22**
- Compsets: **3** (`geo0_low`, `geo0_mid`, `geo0_high`)
- Compset size: min 6, median 7, max 11
- Labelled reviews: min 11, median 95.5, max 846
- Aspect coverage (mentions≥5): location 100%, room 95%, cleanliness/service 91%, breakfast 86%, noise 82%, value 77%
- Fix Weakest ≠ Largest Peer Gap: **14/22 (63.6%)**
- Fix Weakest ≠ Competition-Aware: **10/22 (45.5%)**
- All four agree: **3/22**
- Fix Weakest most often picks **noise (16/22)** — the “always repair the worst item” pile-on
- Competition-Aware spreads: noise 8, breakfast 4, location 3, cleanliness 3, …

### Case studies (real hotels)

1. **Aloft Brussels Schuman** (`geo0_mid`, 223 reviews): all four pick **Breakfast**.
2. **B&B Place Jourdan** (`geo0_low`, 24 reviews): Fix Weakest=Room, Largest Peer Gap=Location, Most Criticized=Cleanliness, CA=Location. At assumed intensity=1, CA flips to Room (scenario only).
3. **Mercure Hotel Brussels Centre Midi** (`geo0_high`, 97 reviews): Fix Weakest=Noise, Largest Peer Gap=Cleanliness, Most Criticized=Room, CA=Cleanliness.

## Validation

```
.venv-demo/bin/python -m unittest tests.test_demo_data_adapter tests.test_demo_scoring tests.test_demo_evidence tests.test_demo_smoke tests.test_demo -v
```

- 25 tests, **0 failed** (see `outputs/night_demo/test_output.txt`)
- Launch: `.venv-demo/bin/python -m streamlit run demo/app.py --server.headless true --server.port 8501`
- `GET /` HTTP 200; `GET /_stcore/health` HTTP 200
- Chrome headless of live Streamlit captured only the loading skeleton (`demo_screenshot_streamlit.png`)
- Usable screenshots: `outputs/night_demo/demo_screenshot.png` (static UI) and `demo_screenshot_charts.png`

## Known Limitations

- Competition sets are one Brussels centre cluster; not a validated market.
- Price for some hotels is imputed; stars sometimes missing.
- ABSA is keyword-gated DeBERTa from June; no gold-set F1 tonight.
- No panel → no predictive/causal upgrade path without new data work.
- Streamlit live Chrome screenshot is unreliable (websocket hydrate).
- Git history started tonight; original project files remain mostly untracked.
- No usable GitHub token for push.

## Highest-Value Next Actions

Ranked by research value / cost / deps.

1. **Rebuild competition sets on a geo-complete hotel table (D1 515K Europe or full `hotels_all.csv` with coords)** — unblocks more than 3 sets. Cost: 1–2 days. Deps: download/parse D1 or reuse 745 coords.
2. **Build a monthly hotel–aspect panel from dated reviews** — required for anything beyond DESCRIPTIVE. Cost: 1 day. Deps: `booking_reviews copy.csv` dates + jsonl join.
3. **Report ABSA reliability vs a small gold sample or HotelRec sub-ratings** — currently mention nets are unvalidated. Cost: 0.5–1 day.
4. **Event-study / pretrend on the panel (still observational until design is clean)** — only after (2). Cost: 2–3 days.
5. **Do not fit a crowding lambda on 22 hotels** — sample is too small; keep scenario analysis until (1)+(2) exist.
