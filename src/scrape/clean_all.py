#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 0 后处理：清洗 + 预处理（在 scrape_all.py 跑完后运行）

输入：
  data/scraped/hotel_attributes_all.csv   (全量爬取结果)
  data/booking_reviews copy.csv           (原始评论，统计本地评论数/差评数)
输出：
  data/processed/hotels_all.csv           (干净的全量酒店表，Phase 1 输入)
  data/processed/clean_report.txt         (清洗统计报告)

清洗步骤：
  1. 去重（按 hotel_url）。
  2. 坐标修复：
     - 假坐标(coord_is_fake)或缺坐标，但有地址 → 用 Nominatim/OSM 地址反查经纬度(geocoding)。
     - Nominatim 政策：≤1 req/s、带正常 UA。结果缓存到 data/scraped/geocode_cache.json，重跑不重复请求。
  3. 城市归属：
     - 优先从 address/邮编解析(比利时邮编 4 位)。
     - 缺地址但有坐标 → 由经纬度落在哪个城市边界框判定(粗粒度)。
  4. 合并原始 CSV 的本地评论数 / 差评数(rating<7)。
  5. 标记国家(be/by)与坐标可用性，输出 Phase 1 可直接用的干净表。

幂等：geocoding 有缓存；重跑只补新增/未解析的，输出覆盖。
依赖：仅标准库(urllib/json/csv)——不碰 numpy/pandas，避开环境冲突。
"""
import os
import re
import csv
import json
import time
import math
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ATTRS_CSV = os.path.join(ROOT, "data", "scraped", "hotel_attributes_all.csv")
RAW_CSV   = os.path.join(ROOT, "data", "booking_reviews copy.csv")
OUT_CSV   = os.path.join(ROOT, "data", "processed", "hotels_all.csv")
REPORT    = os.path.join(ROOT, "data", "processed", "clean_report.txt")
GEO_CACHE = os.path.join(ROOT, "data", "scraped", "geocode_cache.json")

NOMINATIM = "https://nominatim.openstreetmap.org/search"
GEO_UA = "FYP-hotel-research/1.0 (academic; contact: bowenx1125@gmail.com)"
GEO_DELAY = 1.1   # Nominatim 政策：≤1 req/s

# 比利时主要城市的粗略边界框（lat_min, lat_max, lon_min, lon_max），用于坐标定城市的兜底
CITY_BOXES = [
    ("Brussels", 50.76, 50.93, 4.25, 4.48),
    ("Antwerp",  51.13, 51.30, 4.32, 4.50),
    ("Ghent",    51.00, 51.10, 3.66, 3.78),
    ("Bruges",   51.17, 51.28, 3.18, 3.30),
    ("Leuven",   50.85, 50.92, 4.66, 4.74),
    ("Liège",    50.58, 50.69, 5.50, 5.62),
    ("Namur",    50.42, 50.50, 4.82, 4.92),
    ("Charleroi",50.38, 50.46, 4.40, 4.50),
    ("Ostend",   51.20, 51.25, 2.88, 2.97),
    # 白俄罗斯
    ("Minsk",    53.82, 53.97, 27.40, 27.70),
]

OUT_FIELDS = [
    "hotel_url", "hotel_name", "country", "latitude", "longitude", "coord_source",
    "star_rating", "star_type", "address", "city", "zip",
    "price", "price_date", "price_currency", "property_type",
    "review_score", "review_count_booking", "local_review_count", "local_neg_count",
    "status",
]


# ---------------------------------------------------------------------------
def clean_url(u):
    p = urlparse(u.strip())
    return f"{p.scheme}://{p.netloc}{p.path}"


def country_of(url):
    m = re.search(r"/hotel/([a-z]{2})/", url)
    return m.group(1) if m else ""


def parse_zip_city(address):
    if not address:
        return None, None
    zm = re.search(r"\b(\d{4})\b", address)
    cm = re.search(r"\b\d{4}\s+([A-Za-zÀ-ÿ' \-]+?),\s*Belgium", address)
    return (zm.group(1) if zm else None), (cm.group(1).strip() if cm else None)


def city_from_coord(lat, lon):
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    for name, la0, la1, lo0, lo1 in CITY_BOXES:
        if la0 <= la <= la1 and lo0 <= lo <= lo1:
            return name
    return None


def load_geo_cache():
    if os.path.exists(GEO_CACHE):
        with open(GEO_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_geo_cache(cache):
    with open(GEO_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)


def geocode(address, cache):
    """地址 → (lat, lon)；带缓存 + 限速。失败返回 (None, None)。"""
    if not address:
        return None, None
    if address in cache:
        v = cache[address]
        return (v.get("lat"), v.get("lon")) if v else (None, None)
    try:
        url = f"{NOMINATIM}?q={quote(address)}&format=json&limit=1"
        req = Request(url, headers={"User-Agent": GEO_UA})
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        time.sleep(GEO_DELAY)
        if data:
            lat, lon = data[0]["lat"], data[0]["lon"]
            cache[address] = {"lat": lat, "lon": lon}
            return lat, lon
        cache[address] = None
    except Exception as e:
        print(f"    geocode 失败({type(e).__name__}): {address[:40]}")
        time.sleep(GEO_DELAY)
    return None, None


# ---------------------------------------------------------------------------
def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    if not os.path.exists(ATTRS_CSV):
        print(f"找不到 {ATTRS_CSV}\n请先跑 scrape_all.py")
        return

    # 本地评论数 + 差评数
    local_rc = defaultdict(int)
    local_neg = defaultdict(int)
    with open(RAW_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            u = row.get("hotel_url", "").strip()
            if not u:
                continue
            cu = clean_url(u)
            local_rc[cu] += 1
            try:
                if float(row.get("rating") or 99) < 7:
                    local_neg[cu] += 1
            except ValueError:
                pass

    cache = load_geo_cache()
    rows_in = list(csv.DictReader(open(ATTRS_CSV, encoding="utf-8")))

    out, n_geo, n_box, n_nocoord = [], 0, 0, 0
    for r in rows_in:
        url = r["hotel_url"]
        lat, lon = r.get("latitude") or None, r.get("longitude") or None
        coord_source = "scrape" if lat else ""
        addr = r.get("address") or ""

        # 坐标修复：缺坐标(含假坐标已被爬虫置空)但有地址 → geocoding
        if not lat and addr:
            glat, glon = geocode(addr, cache)
            if glat:
                lat, lon, coord_source = glat, glon, "geocode"
                n_geo += 1

        zip4, city = parse_zip_city(addr)
        if not city and lat:                 # 地址没解析出城市 → 坐标落框兜底
            city = city_from_coord(lat, lon)
            if city:
                n_box += 1
        if not lat:
            n_nocoord += 1

        cu = clean_url(url)
        out.append({
            "hotel_url": url, "hotel_name": r.get("hotel_name", ""),
            "country": country_of(url),
            "latitude": lat or "", "longitude": lon or "", "coord_source": coord_source,
            "star_rating": r.get("star_rating", ""), "star_type": r.get("star_type", ""),
            "address": addr, "city": city or "", "zip": zip4 or "",
            "price": r.get("price", ""), "price_date": r.get("price_date", ""),
            "price_currency": r.get("price_currency", ""),
            "property_type": r.get("property_type", ""),
            "review_score": r.get("review_score", ""),
            "review_count_booking": r.get("review_count", ""),
            "local_review_count": local_rc.get(cu, 0),
            "local_neg_count": local_neg.get(cu, 0),
            "status": r.get("status", ""),
        })

    save_geo_cache(cache)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(out)

    # 报告
    n = len(out)
    n_coord = sum(1 for r in out if r["latitude"])
    n_price = sum(1 for r in out if r["price"])
    n_star = sum(1 for r in out if r["star_rating"])
    by_city = defaultdict(int)
    for r in out:
        if r["latitude"]:
            by_city[r["city"] or "Unknown"] += 1
    lines = [
        f"清洗完成：{n} 家",
        f"  有坐标: {n_coord} ({n_coord/n*100:.0f}%) — 其中 geocoding 补回 {n_geo} 家",
        f"  无坐标(死页/无地址): {n_nocoord} 家",
        f"  有价格: {n_price} ({n_price/n*100:.0f}%)",
        f"  有星级: {n_star} ({n_star/n*100:.0f}%)",
        f"  坐标落框定城市补充: {n_box} 家",
        "",
        "有坐标酒店的城市分布(Top 15):",
    ]
    for city, c in sorted(by_city.items(), key=lambda x: -x[1])[:15]:
        lines.append(f"  {city:<16} {c} 家")
    report = "\n".join(lines)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(report)
    print(f"\n输出: {OUT_CSV}\n报告: {REPORT}")


if __name__ == "__main__":
    main()
