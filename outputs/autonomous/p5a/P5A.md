# P5-A Revealed interventions and the size of the remaining gap

Route A reframes the target as *the recommended action is one a manager would adopt, and adopting it raises revenue*. That needs an adoption log and a revenue series; **neither exists in this dataset**. What follows is (1) the closest estimable stand-in and (2) a measurement of how big the missing piece is.

**Verdict: IMPROVEMENT_PAYS_REPLICATED_ACROSS_FOLDS__SPECIFICITY_DIRECTION_DEPENDENT**

Two separate claims, each judged on whether it replicates across the two fold directions (detect-on-A/score-on-B and its mirror). They do not agree, and that disagreement is the result.

| claim | A->B | B->A | verdict |
|---|---|---|---|
| pooled effect of an improvement | +0.0656 (t=3.46) | +0.0652 (t=3.43) | **REPLICATED_ACROSS_FOLDS** |
| between-aspect gap vs placebo | 0.1152 / 0.1119 (ratio 1.029, p=0.402) | 0.2035 / 0.1092 (ratio 1.863, p=0.008) | **DIRECTION_DEPENDENT** |
| best aspect named | cleanliness | value | DISAGREE |
| pre-trend (should be ~0) | -0.021 (t=-0.94) | -0.0425 (t=-2.11) | |

- P3 value vector under this estimand: NO_TRANSFER

## Q1 Are real interventions visible?

- events at tau=0.25: **1607** across 800 hotels
- median jump 0.3326315789473685, median persistence 0.2685185185185185 (net sentiment units, range -1..1)

| aspect | events |
|---|---|
| service | 371 |
| room | 294 |
| breakfast | 259 |
| location | 227 |
| cleanliness | 220 |
| value | 137 |
| noise | 99 |

## Q2 Is the rating payoff aspect-specific?

| aspect | n | ATT (rating pts) | clustered se | t | P(>0) |
|---|---|---|---|---|---|
| location | 227 | +0.0491 | 0.0431 | 1.14 | 85% |
| cleanliness | 220 | +0.1238 | 0.0345 | 3.59 | 100% |
| breakfast | 259 | +0.0515 | 0.0301 | 1.71 | 95% |
| service | 371 | +0.1188 | 0.0358 | 3.32 | 100% |
| noise | 99 | +0.0086 | 0.0473 | 0.18 | 58% |
| room | 292 | +0.0852 | 0.0405 | 2.1 | 99% |
| value | 137 | +0.0740 | 0.0403 | 1.84 | 97% |

- **Pooled (any improvement)**: +0.0656 (se 0.0189, t=3.46)
- **Pre-trend (t-2 -> t-1, treated - control)**: -0.0210 (se 0.0223, t=-0.94)
- best-minus-worst gap: +0.1152 (bootstrap se 0.0423)
- permutation placebo gap: 0.1119 (p95 0.1799)
- **ratio 1.0294336900175067, p=0.40166666666666667**

### Guards

- specificity: event aspect moves +0.0386 more than the other aspects (t=8.23, 58% positive) -> events ARE aspect-specific
- deterioration arm (persistent drops): best location +0.0461, worst cleanliness -0.0611

### Threshold sensitivity

| tau | events | pooled ATT | t | pre-trend | gap | placebo | ratio | p |
|---|---|---|---|---|---|---|---|---|
| 0.2 | 2506 | +0.0735 | 4.45 | -0.0257 | 0.1214 | 0.0906 | 1.34 | 0.155 |
| 0.25 | 1605 | +0.0656 | 3.48 | -0.0210 | 0.1152 | 0.1107 | 1.04 | 0.420 |
| 0.3 | 969 | +0.0737 | 3.49 | -0.0308 | 0.1671 | 0.1414 | 1.18 | 0.235 |
| 0.4 | 288 | +0.0818 | 2.57 | -0.0625 | 0.1410 | 0.2121 | 0.66 | 0.810 |

## Q3 Does P3's value vector transfer to this estimand?

- cross-fit replicates: 24
- V(value_aware) - V(peer_relative) under the event gamma: **+0.02088** (se 0.00323, 92% positive)
- scrambled-gamma null: mean +0.00045, sd 0.02714
- z vs scrambled = 0.7530659034199271, p = 0.22708333333333333

## Q4 How much external data would close the gap?

- outcome noise per hotel-quarter: sigma = 0.909 rating points
- current median events per aspect: 227
- **minimum detectable between-aspect difference now: 0.171 rating points**

| target effect (rating pts) | n per aspect | total for 6 actionable | detectable now |
|---|---|---|---|
| 0.02 | 32437 | 194622 | no |
| 0.05 | 5190 | 31140 | no |
| 0.1 | 1298 | 7788 | no |
| 0.2 | 325 | 1950 | yes |
| 0.5 | 52 | 312 | yes |

Revenue translation (ADR anchor 129.0 from scraped Booking prices, Belgium sample (NOT the panel cities -- scale anchor only, not joined)). Elasticity is an **external assumption**:

| assumed % revenue per rating point | implied MDE (% revenue) |
|---|---|
| 1% | 0.171 |
| 2% | 0.343 |
| 5% | 0.857 |

## What this means

- Persistent improvements ARE followed by higher ratings, and it replicates across both fold directions: A->B +0.0656 (t=3.46) / B->A +0.0652 (t=3.43). Events are also aspect-specific (the event aspect moves more than the others, specificity t=8.2+).
- Which aspect pays most is DIRECTION-DEPENDENT: A->B gap ratio 1.029 (p=0.402, best=cleanliness); B->A gap ratio 1.863 (p=0.008, best=value). One fold direction clears the placebo, the other does not, and they do not name the same aspect. Targeting is NOT established -- reporting either direction alone would be cherry-picking.
- The direction that shows specificity (B->A) is also the one with an unresolved pre-trend (t=-2.11): those hotels were already moving before the event, so part of that gap is mean reversion, not payoff.
- So the defensible claim is 'act on your weakest reliably measured aspect', NOT 'act on aspect X because it pays more'. The shipped peer-relative ranking already implements the first.
- P3's cross-sectional value vector does not transfer to this intervention estimand (scrambled-gamma z=0.7530659034199271), which is consistent: it was estimated on levels, not on changes.
- The smallest between-aspect difference detectable with the current sample is 0.1714 rating points; anything smaller needs more logged interventions, not a better estimator.
- Adoption probability and revenue remain unidentified: there is no adoption log and no ADR/occupancy for these hotels. Closing the original goal requires logged interventions, not a better estimator.
