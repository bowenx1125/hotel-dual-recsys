# Night Demo Audit — 2026-09-10

## Repository / Git

| Item | Value |
|---|---|
| Path | `/Users/xubosmell/Desktop/FYP1` |
| Starting HEAD | **none** — this directory was **not a git repository** (`fatal: not a git repository`) |
| Uncommitted tracked changes | N/A (no `.git`) |
| Remotes | none |
| `gh auth` | GitHub account present but **token in keyring is invalid**; push is expected to fail without re-auth |
| Working-tree protection | No pre-existing git changes to preserve. Local `git init` + branch `demo/provider-side-20260910-grok` used for this spike. No reset/clean/stash. |

## Python / tests

| Item | Value |
|---|---|
| `python3` | `/opt/homebrew/bin/python3` 3.12.3 |
| Anaconda numpy conflict | Documented; brew Python here has **no pandas/sklearn** |
| Existing venv | `.venv-absa` (transformers/torch; used historically for ABSA) |
| Project tests | **none** (no `tests/` in the FYP tree) |
| MPS / torch | available inside `.venv-absa`, **not used tonight** (no retraining) |

## Actual directory structure (maxdepth 3, excluding venv/node_modules/html)

```
FYP1/
  BG.md CLAUDE.md HANDOFF.md RESEARCH_*.md CODE_PLAN.md PAPER_STRATEGY.md
  AUTORUN_SPEC.md SPRINT_44D.md SCRAPING_SPEC.md Steps
  src/{scrape,compset,aspect,thesis}/*.py
  data/processed/{hotels_all,brussels_hotels,compsets,aspect_features,review_aspects.jsonl,clean_report.txt}
  data/scraped/{hotel_attributes,hotel_attributes_all,failed_urls*,geocode_cache.json,html/*.gz}
  data/booking_reviews copy.csv
  models/absa/{model.safetensors ~738MB, tokenizer, config}
  figures/*.png
```

## Data files and sizes

| Path | Size | Rows | Role |
|---|---|---|---|
| `data/booking_reviews copy.csv` | 49.2 MB | 26,675 | Raw reviews (text). **Not loaded into Demo snapshot.** |
| `data/processed/hotels_all.csv` | 194 KB | 822 | Scraped hotel attributes (Belgium-heavy) |
| `data/processed/brussels_hotels.csv` | 6.7 KB | 36 | Brussels subset used to build compsets |
| `data/processed/compsets.csv` | 5.6 KB | 34 | Geographic+price-tier peer labels |
| `data/processed/aspect_features.csv` | 5.7 KB | 24 | Hotel-level aspect nets + mention rates |
| `data/processed/review_aspects.jsonl` | 902 KB | 3,620 | Review×aspect sentiment (**no review text**) |
| `data/processed/clean_report.txt` | 1 KB | — | Scrape coverage summary |
| `data/scraped/hotel_attributes_all.csv` | 231 KB | 822 | Raw scrape table |
| `data/scraped/failed_urls_all.csv` | 10 KB | 77 | Failed scrape URLs |
| `models/absa/model.safetensors` | 738 MB | — | DeBERTa-ABSA weights (not used tonight) |

## Candidate table schemas

### `aspect_features.csv` (24 hotels)
`hotel_url, hotel_name, compset_id, n_reviews, n_negative, {aspect}_net, {aspect}_mention_rate, neg_{aspect}_share`  
Aspects: `location, cleanliness, breakfast, service, noise, room, value`  
Missing: some `*_net` when an aspect is never mentioned; `neg_*_share` empty when `n_negative=0` (6 hotels).

### `compsets.csv` (34 hotels)
`hotel_url, hotel_name, lat, lon, star, price, price_imputed, price_is_proxy, geo_cluster, price_tier, compset_id, compset_valid`  
`compset_valid=1` only for `geo0_{low,mid,high}` (Brussels centre). `geo1_*` and `isolated` are invalid.

### `review_aspects.jsonl` (3,620 records)
`review_id, hotel_url, rating, is_negative, aspects{aspect: {sentiment, conf}}`  
No `review_text`. Usable for mention counts without committing raw comments.

### Time panel / treatment / effects
**Not present.** No monthly/quarterly panel, no treatment file, no peer-exposure series, no DiD/IV/OPE outputs, no CI.

## Counts that matter for the Demo

- Hotels with coordinates (processed): 745 / 822 (91%)
- Hotels with price: 321 / 822 (39%)
- Compset table: 34 Brussels hotels
- Valid competition sets: **3** (`geo0_low`, `geo0_mid`, `geo0_high`), all one geographic cluster
- Hotels with aspect vectors: **24** (all in valid `geo0_*` sets)
- Reviews with ABSA labels: 3,620 (valid-compset hotels only)

## Document claims vs assets

| Claim in docs | Supported? |
|---|---|
| Dual-perspective FYP; Phase 0 scrape done | **Yes** — 822-row `hotels_all.csv`, HTML archives |
| Local comp sets from geo + price tier | **Partial** — MVP exists; only 1 effective geo cluster |
| Aspect vectors + complaint mix | **Yes** — 24 hotels, 7 aspects, jsonl detail |
| Shared tourist/manager representation | **No runtime** |
| LightGBM tourist ranker | **No** |
| Manager LLM diagnosis | **No** |
| Time-split predictive model | **No** |
| Causal estimates, event study, placebo, Figure 1 | **No files, no numbers** |
| AUTORUN 10-day pipeline / `run.py` | **Not started** |

## Evidence level for tonight

**DESCRIPTIVE only.**

Reasons: cross-section aspect scores + researcher-defined peer sets; no temporal holdout; no identified treatment; no effect + CI reproducible from code.

Peer sets are **labelled competition sets from DBSCAN∩price-tier**, not validated economic substitutes.

## Demo source selection

| Use | Path | Why |
|---|---|---|
| Aspect scores | `data/processed/aspect_features.csv` | Only hotel×aspect table |
| Peer membership | `data/processed/compsets.csv` | Only compset labels |
| Mention/neg counts | `data/processed/review_aspects.jsonl` | Review-level sentiment without text |
| City / stars / price | `compsets.csv` + `brussels_hotels.csv` | Join keys via `hotel_url` |

Not used tonight: raw review CSV, ABSA weights, hotels outside the 24-hotel aspect table, any synthetic default.

## Blockers (non-fatal)

1. No git history / remote.
2. No pandas in default Python — Demo core is stdlib-only.
3. Compset coverage too small for paper-level claims; enough for a 3+ hotel manager Demo.
