# P2 cross-fit effect estimation

**Verdict: AMBER_ASSOCIATIONAL**

**Reading:** Contemporaneous cross-fold association is strong and survives fold separation, so it is a genuine hotel-quarter quality signal, not same-review mechanics. The LEAD specification (aspect change -> next-quarter rating change) is indistinguishable from zero, so these data do not support 'improving aspect X raises later ratings'.

## Specification

- unit: hotel x aspect x quarter (complete quarters only)
- treatment: aspect sentiment (smoothed_net) on detection fold F
- outcome: mean reviewer score on the other fold G (disjoint reviews)
- FE: hotel x aspect (absorbed), period dummies; cluster: hotel
- min scored reviews per fold: 3
- both directions (A->B and B->A) estimated and averaged

## Results by timing (cross-fit)

- lagged_change — x=d_sn_F(t-1->t), y=ms_G(t->t+1)  [temporal precedence]: beta=-0.0340 se=0.0224 p=0.13 95%CI=[-0.0779, +0.0100] n=24732
- contemp_change — x=d_sn_F(t-1->t), y=ms_G(t-1->t)  [contemporaneous]: beta=+0.1007 se=0.0196 p=3.103e-07 95%CI=[+0.0623, +0.1391] n=30222
- lagged_level — x=sn_F(t), y=ms_G(t+1)  [temporal precedence, levels]: beta=+0.0571 se=0.0189 p=0.002537 95%CI=[+0.0201, +0.0942] n=34224
- contemp_level — x=sn_F(t), y=ms_G(t)  [contemporaneous, levels]: beta=+0.1870 se=0.0171 p=7.535e-27 95%CI=[+0.1535, +0.2205] n=41497

Permutation of x within period x aspect (lead spec): mean=-0.0000 sd=0.0247 two-sided p=0.0600 (n=200)

## Own-fold contrast (mechanical coupling check)

Same fold on both sides; not a valid estimate, shown only to size the artefact.

- lagged_change: beta=-0.3766 se=0.0239 p=3.14e-51 95%CI=[-0.4235, -0.3298] n=24732
- contemp_change: beta=+0.7551 se=0.0242 p=1.08e-160 95%CI=[+0.7077, +0.8025] n=30222
- lagged_level: beta=-0.0718 se=0.0188 p=0.0001395 95%CI=[-0.1087, -0.0350] n=34224
- contemp_level: beta=+0.8335 se=0.0208 p=4.145e-237 95%CI=[+0.7928, +0.8742] n=41497

## Location negative control (immutable aspect)

- lagged_change: beta=-0.0103 se=0.0526 p=0.8441 95%CI=[-0.1134, +0.0927] n=5201
- contemp_change: beta=+0.0427 se=0.0468 p=0.361 95%CI=[-0.0489, +0.1344] n=6356
- lagged_level: beta=+0.0380 se=0.0422 p=0.3677 95%CI=[-0.0447, +0.1207] n=6765
- contemp_level: beta=+0.0797 se=0.0398 p=0.04553 95%CI=[+0.0017, +0.1577] n=8190

## Sensitivity: min scored reviews per fold

- min_reviews=1 lagged_change: beta=-0.0332 se=0.0235 p=0.1588 95%CI=[-0.0794, +0.0130] n=26302
- min_reviews=1 contemp_change: beta=+0.0963 se=0.0202 p=1.979e-06 95%CI=[+0.0568, +0.1358] n=32056
- min_reviews=5 lagged_change: beta=-0.0317 se=0.0216 p=0.1426 95%CI=[-0.0740, +0.0106] n=22556
- min_reviews=5 contemp_change: beta=+0.0970 se=0.0189 p=3.426e-07 95%CI=[+0.0599, +0.1340] n=27356

## Per aspect (cross-fit)

- location / lagged_change: beta=-0.0103 se=0.0526 p=0.8441 95%CI=[-0.1134, +0.0927] n=5201
- location / contemp_change: beta=+0.0427 se=0.0468 p=0.361 95%CI=[-0.0489, +0.1344] n=6356
- cleanliness / lagged_change: beta=-0.0432 se=0.0443 p=0.3299 95%CI=[-0.1299, +0.0436] n=3838
- cleanliness / contemp_change: beta=+0.0755 se=0.0433 p=0.08162 95%CI=[-0.0094, +0.1605] n=4704
- breakfast / lagged_change: beta=+0.0105 se=0.0412 p=0.7993 95%CI=[-0.0702, +0.0912] n=4222
- breakfast / contemp_change: beta=+0.0601 se=0.0364 p=0.09884 95%CI=[-0.0112, +0.1314] n=5155
- service / lagged_change: beta=-0.0591 se=0.0472 p=0.211 95%CI=[-0.1516, +0.0334] n=5286
- service / contemp_change: beta=+0.1910 se=0.0425 p=7.534e-06 95%CI=[+0.1077, +0.2742] n=6458
- noise / lagged_change: beta=-0.0655 se=0.0442 p=0.139 95%CI=[-0.1522, +0.0212] n=2795
- noise / contemp_change: beta=+0.0689 se=0.0403 p=0.0873 95%CI=[-0.0100, +0.1478] n=3421
- room / lagged_change: beta=-0.0363 se=0.0504 p=0.4721 95%CI=[-0.1351, +0.0626] n=5339
- room / contemp_change: beta=+0.0972 se=0.0434 p=0.02521 95%CI=[+0.0122, +0.1822] n=6531
- value / lagged_change: beta=-0.0261 se=0.0457 p=0.5686 95%CI=[-0.1157, +0.0635] n=3252
- value / contemp_change: beta=+0.0904 se=0.0375 p=0.01629 95%CI=[+0.0168, +0.1640] n=3953

## Caveats

- Observational. Fold separation removes same-review mechanical coupling but does not randomise hotel quality, and mean reversion in hotel quality depresses the lead coefficient. Outcome is guest RATING, not revenue: no price, room-night or cost fields exist in this dataset.
- Treatment is measured with sampling error independent of the outcome error (classical errors-in-variables), so |beta| is biased toward zero: estimates are lower bounds in magnitude.
- No price, room-night or cost fields exist, so nothing here is ROI.
