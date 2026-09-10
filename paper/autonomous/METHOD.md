# Method

1. Complete vs partial quarters from actual `Review_Date` min/max (expected partial: 2015Q3, 2017Q3).
2. Review fingerprint SHA1 → folds A/B, disjoint at review level. Detect on one fold, measure outcome on the other.
3. Strict events (Wave 2) with Location held out as a negative control.
4. Peer validity: k=5/10/20, mutual, radius, random, shuffled, non-local.
5. Fair predictive benchmark: rolling origin, train-only imputation/standardization, Ridge alpha on validation, hotel-clustered bootstrap, shuffled-peer falsification.
6. Exploratory matched event-time differences if n≥100; otherwise scientifically skipped.
7. Track-specific policy: currently Track B.
8. ABSA vs structurally weak section labels only (never gold accuracy); HUMAN_VALIDATION_REQUIRED remains.
