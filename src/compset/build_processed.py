#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1 前置：清洗爬取属性 + 合并评论数 → 标准化酒店表

输入：
  data/scraped/hotel_attributes.csv   (Phase 0 爬取结果)
  data/booking_reviews copy.csv       (原始评论，用于统计本地评论数)
输出：
  data/processed/brussels_hotels.csv  (Phase 1 竞争集的干净输入)

清洗规则：
  - 剔除"假坐标"行（Booking 兜底点 50.8474280093567,4.35258558669035）——这些是抓取失败
  - 剔除无地址的行
  - 从地址解析邮编 → 标记 zone / 是否布鲁塞尔市区
  - 标记地理离群（Mons/Antwerp 等非布鲁塞尔城市）
  - join 原始 CSV 的本地评论数（local_review_count）

幂等：重跑覆盖输出，不污染。
"""
import os
import re
import csv
from urllib.parse import urlparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ATTRS_CSV = os.path.join(ROOT, "data", "scraped", "hotel_attributes.csv")
RAW_CSV   = os.path.join(ROOT, "data", "booking_reviews copy.csv")
OUT_CSV   = os.path.join(ROOT, "data", "processed", "brussels_hotels.csv")

FAKE_COORD = ("50.8474280093567", "4.35258558669035")  # Booking 兜底点 = 抓取失败信号

OUT_FIELDS = [
    "hotel_url", "hotel_name", "latitude", "longitude",
    "star_rating", "star_type", "zip", "city_label", "is_brussels_core",
    "is_outlier", "price", "price_currency",
    "review_score", "review_count_booking", "local_review_count",
]


def clean_url(u):
    p = urlparse(u.strip())
    return f"{p.scheme}://{p.netloc}{p.path}"


def parse_zip_city(address):
    """从地址解析 4 位邮编 + 城市名。"""
    if not address:
        return None, None
    zm = re.search(r"\b(\d{4})\b", address)
    zip4 = zm.group(1) if zm else None
    # 城市名：地址里 "NNNN City" 模式
    cm = re.search(r"\b\d{4}\s+([A-Za-zÀ-ÿ' \-]+?),\s*Belgium", address)
    city = cm.group(1).strip() if cm else None
    return zip4, city


def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

    # 本地评论数
    local_rc = defaultdict(int)
    with open(RAW_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            u = row.get("hotel_url", "").strip()
            if u:
                local_rc[clean_url(u)] += 1

    rows_out = []
    n_drop_fake = n_drop_noaddr = 0
    with open(ATTRS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            # 剔除假坐标
            if (r["latitude"], r["longitude"]) == FAKE_COORD or not r["latitude"]:
                n_drop_fake += 1
                continue
            # 剔除无地址
            if not r["address"]:
                n_drop_noaddr += 1
                continue

            zip4, city = parse_zip_city(r["address"])
            is_core = bool(zip4 and zip4[:2] in ("10", "11", "12"))  # 1000-1299 = 布鲁塞尔大区
            # 离群：纬度明显偏离布鲁塞尔（50.75–50.95）
            try:
                lat = float(r["latitude"])
                is_outlier = not (50.70 <= lat <= 50.95)
            except ValueError:
                is_outlier = True

            url = r["hotel_url"]
            rows_out.append({
                "hotel_url": url,
                "hotel_name": r["hotel_name"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "star_rating": r["star_rating"],
                "star_type": r["star_type"],
                "zip": zip4 or "",
                "city_label": city or "",
                "is_brussels_core": int(is_core),
                "is_outlier": int(is_outlier),
                "price": r["price"],
                "price_currency": r["price_currency"],
                "review_score": r["review_score"],
                "review_count_booking": r["review_count"],
                "local_review_count": local_rc.get(clean_url(url), 0),
            })

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(rows_out)

    # 汇总
    n = len(rows_out)
    n_outlier = sum(r["is_outlier"] for r in rows_out)
    n_core = sum(r["is_brussels_core"] for r in rows_out)
    n_price = sum(1 for r in rows_out if r["price"])
    n_star = sum(1 for r in rows_out if r["star_rating"])
    print(f"清洗: 剔除假坐标 {n_drop_fake} 家, 无地址 {n_drop_noaddr} 家")
    print(f"输出: {n} 家 → {OUT_CSV}")
    print(f"  布鲁塞尔大区: {n_core} 家 | 地理离群: {n_outlier} 家 | "
          f"有效布鲁塞尔(core 且非离群): {sum(1 for r in rows_out if r['is_brussels_core'] and not r['is_outlier'])} 家")
    print(f"  有价格: {n_price} 家 | 有星级: {n_star} 家")
    print(f"\n离群酒店(将不进布鲁塞尔竞争集):")
    for r in rows_out:
        if r["is_outlier"]:
            print(f"    - {r['hotel_name'][:40]:<40} {r['city_label']} ({r['zip']})")


if __name__ == "__main__":
    main()
