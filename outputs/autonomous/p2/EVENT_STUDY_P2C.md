# P2c matched DiD robustness

**Verdict: AMBER_ASSOCIATIONAL** — 456 events concentrated in 2016Q2-Q4; after requiring fold-outcome coverage the matched sample is small and this check is low-powered. It is a consistency check on the P2b continuous estimates, not a standalone result.

- design: matched DiD, nearest neighbour on pre-event level and pre-trend
- matching covariates: detection-fold smoothed_net at t-1 and pre-trend (t-2 -> t-1)
- min scored reviews per fold: 3

## wave5_pooled_net

- matched events: 315 (rows 2432)
- pre-trend check at k=-2 (|ATT|<0.05): True
- k=-2: ATT=-0.0449 se=0.0063 p=6.119e-12 n=485
- k=-1: ATT=+0.0000 se=0.0000 p=nan n=488
- k=0: ATT=+0.1697 se=0.0115 p=5.694e-38 n=488
- k=1: ATT=+0.0434 se=0.0123 p=0.0004945 n=486
- k=2: ATT=+0.0232 se=0.0123 p=0.06088 n=485

## crossfit_rating

- matched events: 308 (rows 2326)
- pre-trend check at k=-2 (|ATT|<0.05): True
- k=-2: ATT=-0.0219 se=0.0370 p=0.5541 n=459
- k=-1: ATT=+0.0000 se=0.0000 p=nan n=476
- k=0: ATT=+0.1139 se=0.0364 p=0.001903 n=472
- k=1: ATT=+0.0437 se=0.0373 p=0.2422 n=463
- k=2: ATT=+0.0564 se=0.0373 p=0.1323 n=456

## Comparison

- Wave 5 style (pooled smoothed_net, self-referential) ATT at k=0: 0.16971589236138307
- Cross-fit (other-fold guest rating) ATT at k=0: 0.1139333059953554

wave5_pooled_net is self-referential (events detected per fold, outcome measured on the pooled index that contains that fold). crossfit_rating uses the other fold's guest rating: a downstream, disjoint-review outcome. Units are NOT comparable (smoothed_net vs 0-10 rating points).
