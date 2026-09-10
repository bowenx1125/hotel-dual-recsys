# Claims Ledger

| ID | Claim | Status | Evidence | Exact metric | Allowed wording | Forbidden wording | Next evidence |
|---|---|---|---|---|---|---|---|
| C1 | Current Manager Demo is descriptive | SUPPORTED | demo/evidence.py + live Demo | evidence_level=DESCRIPTIVE | DESCRIPTIVE EVIDENCE | causal effect / ROI | — |
| C2 | Peer set is a reference set, not validated competition | SUPPORTED | geo_reference_sets + Demo wording | k=10 same-city Haversine; 14760 edges | geo reference set / candidate peer set | validated competitors / economic substitutes | demand-side substitution tests |
| C3 | Location is diagnostic, not a direct operational action | SUPPORTED | conf/actionability.json + tests | Location immutable; never default action | diagnostic disadvantage | improve/fix location as direct action | — |
| C4 | Weighted heuristic has no learned business return | SUPPORTED | conf/demo.json + WEIGHT_SENSITIVITY | weights 0.45/0.35/0.20; 12/22 stable | design-choice / Peer-Relative Evidence-Weighted (heuristic) | estimated return / learned weights | — |
| C5 | Temporal panel is sufficient for feasibility work | SUPPORTED | panel_manifest + feasibility | 89075 quarter cells; 80686 mention cells; 1458 hotels ≥4 periods | structurally weak-labeled panel | gold-standard ABSA / full causal panel | stronger ABSA labels |
| C6 | Peer exposure has usable variation | SUPPORTED | feasibility_metrics.json | exposure>0: 4894; exposure=0: 880 | review-perceived peer exposure | observed peer renovations | operational event data |
| C7 | Predictive pilot beats persistence | PARTIAL | predictive_pilot/metrics.json | MAE persist 0.492 vs peer 0.458; vs own-features ~0.459 | predictive association on temporal holdout | causal peer effect | larger holdout / aspect targets |
| C8 | Eligible to *explore* event-study designs | PARTIAL | GO_NO_GO GREEN | 5774 candidate events; gates passed | exploratory event-study design support | confirmatory causal identification complete | pre-period balance / placebos |
| C9 | Causal wording allowed | FORBIDDEN | no identification strategy executed | — | none | causal effect / ROI / demand lift / guaranteed improvement | credible design + diagnostics |
