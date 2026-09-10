#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1：竞争集构建（创新点 ②）

方法（见 RESEARCH_PLAN Phase 1）：
  1. 地理聚类：对布鲁塞尔酒店坐标做 DBSCAN（haversine 真实距离），
     把"地理上抢同一批客人"的酒店聚成地理组。
  2. 价格分档：在每个地理组内按价格分位切档（低/中[/高]）。
  3. comp set = 同地理组 ∩ 同价格档。
  4. 过滤：comp set 内 < MIN_COMPSET 家的标记为无效（不参与 Manager 分析）。

设计约束（MVP，数据量小）：
  - 纯 Python 实现 DBSCAN + haversine（避开当前环境 numpy 2.x / sklearn 二进制冲突）。
  - 缺价格的酒店用星级中位价代理（best-effort，论文需标注）。
  - 价格档数随簇大小自适应：簇 < 6 家切 2 档，否则切 3 档。

输入： data/processed/brussels_hotels.csv
输出： data/processed/compsets.csv
       并打印每个城市/簇形成多少有效竞争集、平均规模（论文关键表）。
"""
import os
import csv
import math
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
IN_CSV  = os.path.join(ROOT, "data", "processed", "brussels_hotels.csv")
OUT_CSV = os.path.join(ROOT, "data", "processed", "compsets.csv")

# ---- 可调参数 ----
EPS_KM        = 1.5    # DBSCAN 邻域半径（km）；地理组的尺度
MIN_SAMPLES   = 2      # DBSCAN 核心点最小邻居数
MIN_COMPSET   = 5      # 有效竞争集最小酒店数（RESEARCH_PLAN N=5）
SENSITIVITY   = [1.0, 1.5, 2.0, 3.0]  # 敏感性分析的 eps 候选


# ----------------------------------------------------------------------------
# haversine 距离（km）
# ----------------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
    return 2 * R * math.asin(math.sqrt(a))


# ----------------------------------------------------------------------------
# 纯 Python DBSCAN（标签：0,1,2,... 为簇；-1 为噪声）
# ----------------------------------------------------------------------------
def dbscan(points, eps_km, min_samples):
    """points: [(lat, lon), ...] → labels: [int, ...]"""
    n = len(points)
    labels = [None] * n

    def neighbors(i):
        out = []
        for j in range(n):
            if i != j and haversine(*points[i], *points[j]) <= eps_km:
                out.append(j)
        return out

    cid = -1
    for i in range(n):
        if labels[i] is not None:
            continue
        nbrs = neighbors(i)
        if len(nbrs) < min_samples:
            labels[i] = -1            # 暂标噪声（后续可能被吸收为边界点）
            continue
        cid += 1
        labels[i] = cid
        seeds = list(nbrs)
        k = 0
        while k < len(seeds):
            j = seeds[k]
            if labels[j] == -1:
                labels[j] = cid       # 噪声 → 边界点
            if labels[j] is None:
                labels[j] = cid
                jn = neighbors(j)
                if len(jn) >= min_samples:
                    seeds.extend(x for x in jn if x not in seeds)
            k += 1
    return labels


def price_tiers(prices, n_tiers):
    """给定价格列表，返回每个价格对应的档位标签 low/mid/high。
    用分位数切档。None 价格保持 None（调用方已用代理填充）。"""
    vals = sorted(p for p in prices if p is not None)
    if not vals or n_tiers < 2:
        return {p: "mid" for p in prices}
    cuts = []
    for t in range(1, n_tiers):
        idx = int(len(vals) * t / n_tiers)
        cuts.append(vals[min(idx, len(vals) - 1)])
    names = ["low", "mid", "high"][:n_tiers]

    def tier_of(p):
        if p is None:
            return None
        for c, name in zip(cuts, names):
            if p <= c:
                return name
        return names[-1]
    return {p: tier_of(p) for p in prices}


def load_hotels():
    rows = []
    with open(IN_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if int(r["is_outlier"]):          # 剔除 Mons/Antwerp 等硬离群
                continue
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except ValueError:
                continue
            rows.append({
                "hotel_url": r["hotel_url"],
                "hotel_name": r["hotel_name"],
                "lat": lat, "lon": lon,
                "star": int(r["star_rating"]) if r["star_rating"] else None,
                "price": int(r["price"]) if r["price"] else None,
            })
    return rows


def impute_price_by_star(rows):
    """缺价格的酒店：用同星级的中位价代理。"""
    by_star = defaultdict(list)
    for r in rows:
        if r["price"] and r["star"]:
            by_star[r["star"]].append(r["price"])
    star_med = {s: sorted(v)[len(v)//2] for s, v in by_star.items()}
    overall = sorted(r["price"] for r in rows if r["price"])
    overall_med = overall[len(overall)//2] if overall else None
    n_imp = 0
    for r in rows:
        if r["price"] is None:
            r["price_imputed"] = star_med.get(r["star"], overall_med)
            r["price_is_proxy"] = 1
            n_imp += 1
        else:
            r["price_imputed"] = r["price"]
            r["price_is_proxy"] = 0
    return n_imp


def main():
    rows = load_hotels()
    print(f"载入布鲁塞尔酒店（去离群）: {len(rows)} 家\n")

    pts = [(r["lat"], r["lon"]) for r in rows]

    # --- 敏感性分析：不同 eps 的聚类形态 ---
    print("=== DBSCAN 敏感性分析（min_samples=%d）===" % MIN_SAMPLES)
    print(f"{'eps(km)':>8} {'簇数':>5} {'噪声点':>6} {'最大簇':>6} {'各簇规模'}")
    for eps in SENSITIVITY:
        labels = dbscan(pts, eps, MIN_SAMPLES)
        sizes = Counter(l for l in labels if l != -1)
        noise = sum(1 for l in labels if l == -1)
        nclust = len(sizes)
        maxc = max(sizes.values()) if sizes else 0
        size_str = sorted(sizes.values(), reverse=True)
        print(f"{eps:>8.1f} {nclust:>5} {noise:>6} {maxc:>6}   {size_str}")
    print()

    # --- 用选定 eps 正式聚类 ---
    print(f"=== 采用 eps={EPS_KM}km 构建竞争集 ===")
    labels = dbscan(pts, EPS_KM, MIN_SAMPLES)
    for r, l in zip(rows, labels):
        r["geo_cluster"] = l

    n_imp = impute_price_by_star(rows)
    print(f"价格代理: {n_imp} 家缺价用同星级中位价填充\n")

    # --- 每个地理簇内切价格档 ---
    clusters = defaultdict(list)
    for r in rows:
        clusters[r["geo_cluster"]].append(r)

    compset_rows = []
    compset_members = defaultdict(list)
    for cid, members in sorted(clusters.items()):
        if cid == -1:
            # 噪声点：地理孤立，无地理竞争集
            for r in members:
                r["compset_id"] = "isolated"
                r["price_tier"] = None
            continue
        n_tiers = 2 if len(members) < 6 else 3
        tmap = price_tiers([m["price_imputed"] for m in members], n_tiers)
        for r in members:
            tier = tmap[r["price_imputed"]]
            cs_id = f"geo{cid}_{tier}"
            r["compset_id"] = cs_id
            r["price_tier"] = tier
            compset_members[cs_id].append(r)

    # --- 标记有效/无效竞争集 ---
    print("=== 竞争集明细 ===")
    valid_count = 0
    for cs_id in sorted(compset_members):
        members = compset_members[cs_id]
        valid = len(members) >= MIN_COMPSET
        if valid:
            valid_count += 1
        flag = "✓有效" if valid else "✗太小"
        for r in members:
            r["compset_valid"] = int(valid)
        # 簇质心
        clat = sum(m["lat"] for m in members)/len(members)
        clon = sum(m["lon"] for m in members)/len(members)
        prices = sorted(m["price_imputed"] for m in members)
        print(f"  {cs_id:<14} {len(members)} 家 {flag} | "
              f"价 €{prices[0]}–€{prices[-1]} | 质心({clat:.3f},{clon:.3f})")
        for m in members:
            proxy = "~" if m["price_is_proxy"] else " "
            print(f"      - {m['hotel_name'][:38]:<38} {m['star']}★ €{proxy}{m['price_imputed']}")

    # isolated
    iso = [r for r in rows if r.get("compset_id") == "isolated"]
    if iso:
        print(f"\n  [地理孤立 {len(iso)} 家，无竞争集]")
        for r in iso:
            print(f"      - {r['hotel_name'][:38]:<38} {r['star']}★ €{r['price_imputed']}")
        for r in iso:
            r["compset_valid"] = 0

    # --- 落盘 ---
    out_fields = ["hotel_url", "hotel_name", "lat", "lon", "star",
                  "price", "price_imputed", "price_is_proxy",
                  "geo_cluster", "price_tier", "compset_id", "compset_valid"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in out_fields})

    print(f"\n{'='*56}")
    print(f"有效竞争集（≥{MIN_COMPSET}家）: {valid_count} 个")
    print(f"覆盖酒店: {sum(len(compset_members[c]) for c in compset_members if len(compset_members[c])>=MIN_COMPSET)} 家")
    print(f"输出: {OUT_CSV}")


if __name__ == "__main__":
    main()
