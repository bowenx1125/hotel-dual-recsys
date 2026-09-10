# RAW DATA AUDIT

## Raw reviews (private local file)

- Env path: `FYP_PRIVATE_DATA_ROOT/booking_reviews copy.csv`
- Bytes: **49244888**
- SHA256: `7dc95a900fad8f06025656dfa8943148bc7f0a9a402cd599776d504aa7d9826c`
- Rows: **26675**
- Fields: index, review_title, reviewed_at, reviewed_by, images, crawled_at, url, hotel_name, hotel_url, avg_rating, nationality, rating, review_text, raw_review_text, tags, meta
- Date field: `reviewed_at` range **2018-07-31 → 2021-07-19**
- Date missing rate: **1.0834%** (289)
- Unique review ids (`index`): **26675** (duplicate id rows: 0)
- Hotels: **822**
- Text fields present: ['review_text', 'raw_review_text'] (not written to outputs)

## Aspects JSONL

- Path: `data/processed/review_aspects.jsonl`
- Rows: **3620**
- Unique review_id: **3620** (dups: 0)
- Hotels: **24**

## Join integrity

- Matched unique ids: **3620**
- Aspect match rate: **100.00%**
- Unmatched aspect ids: **0**
- Raw ids not in aspects: **23055** (expected: aspects are a Brussels valid-compset subset)

## Decision

- Dates are usable on the Belgium raw file.
- Join key `index` ↔ `review_id` is safe for the aspect subset (high match rate).
- Belgium panel alone is small for multi-city feasibility; proceed to attempt 515K Europe for scale.
