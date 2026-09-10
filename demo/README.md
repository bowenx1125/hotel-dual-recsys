# Provider-side Demo

Competition-aware **hotel manager** Demo. No tourist ranker. No external API.

## Launch

```bash
python3 scripts/build_demo_snapshot.py
python3 -m unittest tests.test_demo -v
python3 -m streamlit run demo/app.py --server.headless true --server.port 8501
```

Open http://localhost:8501

If Streamlit is not installed:

```bash
python3 -m venv .venv-demo
source .venv-demo/bin/activate
pip install streamlit matplotlib
python3 -m streamlit run demo/app.py --server.headless true --server.port 8501
```

## Evidence

Always **DESCRIPTIVE** with the current FYP assets. The UI banner says so. Do not read heuristic scores as causal effects.

## Config

Weights and thresholds: `conf/demo.json` (human-readable copy: `conf/demo.yaml`).
