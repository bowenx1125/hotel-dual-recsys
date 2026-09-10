# PEER SET REPORT

## Terminology

These are **geo reference sets / candidate peer sets**.
They are **not** validated competitors or economic substitutes.

## Construction (main)

- Same city only
- Nearest **k=10** by Haversine
- Exclude self
- Deterministic tie-break: distance then `hotel_id`

## Scale

- Cities: **6**
- Hotels with coords: **1476**
- Main edges: **14760**
- Self-edges: **0** (must be 0)
- Cross-city errors: **0** (must be 0)
- Median distance km: **0.370052791789781**
- P90 distance km: **1.4242080166393154**
- Top-1 stability knn5 vs knn10: **1.000**

## Sensitivity metrics

```json
{
  "knn5": {
    "n_edges": 7380,
    "self_edges": 0,
    "cross_city_errors": 0,
    "n_hotels_with_peers": 1476,
    "mean_degree": 5.0,
    "median_distance_km": 0.2611200179833261,
    "p90_distance_km": 1.0148510177251113
  },
  "knn10": {
    "n_edges": 14760,
    "self_edges": 0,
    "cross_city_errors": 0,
    "n_hotels_with_peers": 1476,
    "mean_degree": 10.0,
    "median_distance_km": 0.370052791789781,
    "p90_distance_km": 1.4242080166393154
  },
  "knn20": {
    "n_edges": 29520,
    "self_edges": 0,
    "cross_city_errors": 0,
    "n_hotels_with_peers": 1476,
    "mean_degree": 20.0,
    "median_distance_km": 0.5325553882794263,
    "p90_distance_km": 1.9008516819430044
  },
  "mutual10": {
    "n_edges": 10634,
    "self_edges": 0,
    "cross_city_errors": 0,
    "n_hotels_with_peers": 1473,
    "mean_degree": 7.21928038017651,
    "median_distance_km": 0.2859438792580072,
    "p90_distance_km": 0.8255868024619912
  },
  "radius_1_5": {
    "n_edges": 88024,
    "self_edges": 0,
    "cross_city_errors": 0,
    "n_hotels_with_peers": 1452,
    "mean_degree": 60.62258953168044,
    "median_distance_km": 0.9589021320916912,
    "p90_distance_km": 1.3993649814389197
  }
}
```

## Limitation

Geographic proximity ≠ verified competitive substitution. Do not use within-set share summing to 1 as evidence of competition.
