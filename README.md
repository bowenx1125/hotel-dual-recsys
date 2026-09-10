# Dual-View Hotel Recommender

BNBU FYP · Bowen XU (`bowenx1125`) · supervisor Dr. Sunny Jeong

A dual-perspective hotel recommendation system:
- **Tourist** (planned): pick the best hotel within a budget band
- **Manager** (working Demo): compare a hotel to its labelled local peer set and contrast improvement heuristics

Current Demo evidence level is **DESCRIPTIVE** (relative aspect gaps and review evidence). It does **not** estimate causal effects, booking demand, or ROI. See `outputs/night_demo/` and `NIGHT_DEMO_HANDOFF_2026-09-10.md`.

Target venues (research plan, not a submitted paper): RecSys 2027 / CIKM 2027.

## Start here

If you are an agent or a collaborator taking over this repo, read in this order:

1. [`CLAUDE.md`](CLAUDE.md) — operating rules
2. [`HANDOFF.md`](HANDOFF.md) — what to do first
3. [`RESEARCH_MASTER_PLAN.md`](RESEARCH_MASTER_PLAN.md) — research blueprint
4. [`CODE_PLAN.md`](CODE_PLAN.md) — engineering stages and gates
5. [`AUTORUN_SPEC.md`](AUTORUN_SPEC.md) — 40-step execution spec

## What is not in this repo

Large / local-only assets are gitignored:

- `models/absa/` weights
- `data/booking_reviews copy.csv` and scraped HTML
- virtualenvs, `node_modules/`, Office lock files

## Manager Demo (this branch)

```bash
python3 -m venv .venv-demo && source .venv-demo/bin/activate
pip install -r requirements-demo.txt
python3 scripts/build_demo_snapshot.py
python3 -m streamlit run demo/app.py --server.headless true --server.port 8501
```

Open http://localhost:8501

## Public dataset (not required for the current Demo)

```bash
kaggle datasets download -d jiashenliu/515k-hotel-reviews-data-in-europe -p data/raw/d1
```
