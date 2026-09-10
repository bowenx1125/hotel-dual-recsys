# PANEL BUILD REPORT

## Labeling

Structurally weak-labeled aspect sentiment from Positive_Review / Negative_Review sections
+ keyword aspect gate. **Not** human gold-standard ABSA.

## Source

- File: `Hotel_Reviews.csv`
- SHA256: `a4810c2757934f0a826a1b16a437eb67a38be45b1a22ad56772afce0b6c11af9`
- Bytes: 238154765
- Rows streamed: 515738
- Date OK: 515738 | Date fail: 0

## Placeholders

- Positive placeholders filtered: 38070
- Negative placeholders filtered: 154434
- Positive sections used: 477668
- Negative sections used: 361304

## Panel sizes

| Granularity | Rows (hotel×period×aspect) | Hotels | Periods | Cities | Mention cells |
|---|---:|---:|---:|---:|---:|
| Month (exploratory) | 233485 | 1493 | 25 | 6 | 185365 |
| Quarter (primary) | 89075 | 1493 | 9 | 6 | 80686 |

## Shrinkage

- Method: Beta-Binomial empirical Bayes toward neutral
- Main prior_strength: **10.0** (fixed a priori)
- Sensitivity corr with main: {"5": {"mean_smoothed_net": 0.15706444388497925, "std_smoothed_net": 0.301494557561217, "corr_with_main": 0.9879045167707076}, "10": {"mean_smoothed_net": 0.12525785770861642, "std_smoothed_net": 0.23988144014715124, "corr_with_main": 1.0}, "20": {"mean_smoothed_net": 0.09281923671110176, "std_smoothed_net": 0.18221518095116343, "corr_with_main": 0.9876001884624508}}

## Gate keyword audit note

Removed overly broad terms `area` (location) and bare `hear`/`heard` (noise) vs original extract_aspects.py.
See `outputs/overnight/DECISIONS.md`.

## Artifacts

- `data/interim/hotel_aspect_month.parquet`
- `data/processed/hotel_aspect_quarter.parquet`
- No raw review text in aggregates.
