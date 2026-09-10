# OVERNIGHT RESEARCH HANDOFF — 2026-09-11

## Repository State

| Item | Value |
|---|---|
| Worktree | `/Users/xubosmell/Desktop/FYP1-temporal` |
| Branch | `research/temporal-feasibility-20260910-grok` |
| Base SHA | `c6a33d79d3441028a3d54292bcc96f0a763d1f37` |
| Final SHA | 365b5488011abf02613f2647d1345318f6dc1dcc |
| Original Demo checkout | `/Users/xubosmell/Desktop/FYP1` left untouched |
| Push policy | feature branch only; no force; no merge to default |

### Commits on branch (since base)

1. `d6fa81e` chore(research): initialize overnight mission state
2. `1260074` fix(demo): separate diagnostic gaps from actionable recommendations
3. `a066c12` chore(data): audit dated review sources and join integrity
4. `5f3e439` feat(panel): build weak-labeled hotel aspect time panel
5. `fa8f6e6` feat(peers): add multi-city geographic reference sets
6. `6e2e6ef` research(feasibility): quantify temporal and peer-exposure support
7. `9ec5dd1` experiment(predictive): add temporal holdout pilot
8. `46ca74d` feat(demo): add temporal feasibility research lab
9. `a38a185` test(research): validate panel peers policies and wording
10. docs(handoff): record overnight evidence and next decisions

## Existing Demo Corrections

- Actionability schema: Location diagnostic-visible / not direct action.
- Heuristic renamed to **Peer-Relative Evidence-Weighted (heuristic)**.
- Crowding under **Competition Crowding Hypothesis** (assumed/illustrative).
- Weight sensitivity: 12/22 hotels stable; switching rate 45.45%.
- Criticism reports count + rate + per-review.
- `conf/demo.json` canonical; yaml generated.

## Data Source

- Belgium private raw: dates usable; join aspects 100%; too small for multi-city temporal main line.
- Primary: HuggingFace dataset `Dricz/515k-Hotel-Reviews-In-Europe` cached as `Hotel_Reviews.csv` under `FYP_DATA_CACHE_ROOT/d1_europe/`.
- SHA256 `a4810c2757934f0a826a1b16a437eb67a38be45b1a22ad56772afce0b6c11af9`
- 515738 rows; ~1492 hotels; 6 cities; 2015-08-04 → 2017-08-03
- **Not committed** to git.

## Temporal Panel

- Labeling: structurally weak-labeled aspect sentiment (pos/neg sections + keyword gate)
- Month rows: 233485 (interim, gitignored)
- Quarter rows: 89075 (committed parquet)
- Hotels: 1493; periods: 9 quarters; cities: 6
- Mention cells: 80686
- Shrinkage prior_strength main=10; sensitivity corr ~0.988

## Peer Sets

- same-city Haversine k=10; 1476 hotels with coords; 14760 edges
- self-edges=0; cross-city errors=0; median distance ≈0.37 km
- Sensitivity: k=5/20, mutual kNN, radius 1.5km

## Feasibility Verdict

**GREEN**

| Gate | Value | Required |
|---|---:|---:|
| Hotels ≥4 periods | 1458 | 500 |
| Valid cells | 80686 | 20000 |
| Candidate events | 5774 | 300 |
| Event hotels | 1288 | 200 |
| Event cities | 6 | 4 |
| Event aspects | 7 | 4 |
| Exposure>0 | 4894 | 100 |
| Exposure=0 | 880 | 100 |
| Frac 2pre+2post | 1.0 | 0.70 |

May proceed: exploratory event-study **design**; predictive association.
Must stop: confirmatory causal claims without identification.

## Predictive Pilot

- Executed (GREEN)
- Split by y-period: train through 2016Q3; val 2016Q4–2017Q1; test 2017Q2–2017Q3
- Test MAE: persistence 0.492; own_features 0.459; own+peer_exposure 0.458
- Peer beats persistence; **negligible** gain over own features
- Manager Demo evidence level remains **DESCRIPTIVE**

## Demo

Launch:

```bash
cd /Users/xubosmell/Desktop/FYP1-temporal
export FYP_DATA_CACHE_ROOT="/Users/xubosmell/Desktop/FYP_DATA_CACHE"
/Users/xubosmell/Desktop/FYP1/.venv-demo/bin/streamlit run demo/app.py
```

Tabs: Manager Diagnostic Demo · Temporal Research Feasibility Lab  
Screenshots: `outputs/overnight/demo/manager_tab.png`, `outputs/overnight/demo/temporal_lab_tab.png`

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Result at handoff: **42 passed** (after legacy test updates).  
CI: `.github/workflows/research-smoke.yml` (no 515K download).

## Claims Ledger Summary

- SUPPORTED: C1–C6
- PARTIAL: C7, C8
- FORBIDDEN: C9 causal wording

## Failures

- Initial city parse invented many false cities → fixed to known 6-city detector.
- Playwright locator strict-mode → fixed with `.first`.
- Legacy demo tests expected old policy count/rule → updated.

## Highest-Value Next Actions

1. **Exploratory event-study design + placebos** — high research value; depends on GREEN panel; need pre-period balance diagnostics.
2. **ABSA agreement audit on dated subsample** — high for measurement credibility; depends on local ABSA model; need agreement vs weak labels.
3. **Hotel/city-period FE predictive check** — medium; depends on pilot code; evidence: peer lift after FE.
4. **Operational event linkage** (renovation/news) — high for leaving review-perceived-only changes; currently unavailable.
5. **Keep Demo DESCRIPTIVE; cite claim IDs in UI** — medium value; low cost; FACTS/CLAIMS already exist.
