#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 0 爬虫：补全布鲁塞尔酒店的缺失属性（MVP 范围）

用途：对原始 CSV 中筛出的布鲁塞尔酒店，逐个访问 Booking.com 页面，
      用 Playwright 真实浏览器通过 AWS WAF 的 JS 挑战，解析：
        - latitude / longitude   (data-atlas-latlng，Phase 1 地理聚类核心)
        - star_rating / star_type (aria-label "N out of 5 stars/quality rating")
        - address / city          (JSON-LD)
        - price                   (统一查询条件下的最低可用房价，best-effort)
        - review_score / review_count (JSON-LD，用于交叉验证 URL 有效性)

合规（见 SCRAPING_SPEC §5）：
  - 仅用于学术研究，规模小（~47 页）
  - 每页间随机延迟 3–8s
  - 不绕验证码、不破解 bot 检测；WAF 的 JS 挑战由真实浏览器正常通过
  - 不硬编码任何凭证

鲁棒性（见 SCRAPING_SPEC §6）：
  - 断点续爬：逐行追加落盘，重跑跳过已成功的 URL
  - 重试：等不到关键元素时重试，带退避
  - 失败记录：写 failed_urls.csv，单家失败不中断
  - 进度打印：已完成 / 总数 / 失败数

运行：
  python src/scrape/scrape_brussels.py
  （耗时约 8–12 分钟，由你自己 python 运行，不消耗 Claude 订阅额度）

幂等：重跑只补未成功的 URL，已成功的不会重复爬、不会污染结果。
"""

import os
import re
import csv
import json
import time
import random
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

# ----------------------------------------------------------------------------
# 路径配置（相对项目根，脚本可从任意目录运行）
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW_CSV     = os.path.join(ROOT, "data", "booking_reviews copy.csv")
OUT_DIR     = os.path.join(ROOT, "data", "scraped")
OUT_CSV     = os.path.join(OUT_DIR, "hotel_attributes.csv")
FAILED_CSV  = os.path.join(OUT_DIR, "failed_urls.csv")

# ----------------------------------------------------------------------------
# 抓取参数（统一查询条件，见 SCRAPING_SPEC §3，必须固定以保证跨酒店可比）
# ----------------------------------------------------------------------------
CHECKIN  = "2026-07-15"   # 未来约 30 天的普通周三，避开周末/节假日/旺季
CHECKOUT = "2026-07-16"   # 住 1 晚
QUERY = (
    f"?checkin={CHECKIN}&checkout={CHECKOUT}"
    f"&group_adults=2&no_rooms=1&group_children=0&selected_currency=EUR"
)
CURRENCY = "EUR"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

DELAY_MIN, DELAY_MAX = 3.0, 8.0   # 每页间随机延迟（秒）
MAX_RETRY = 3                      # 单页最多尝试次数
PAGE_TIMEOUT = 45000               # 页面加载超时（ms）
PRICE_WAIT   = 15000               # 等价格元素出现的超时（ms）

# 输出列顺序
FIELDS = [
    "hotel_url", "hotel_name", "latitude", "longitude",
    "star_rating", "star_type", "address", "city", "property_type",
    "price", "price_currency", "review_score", "review_count",
    "scraped_at", "status",
]

# 布鲁塞尔识别关键词（与 EDA 阶段一致；用词边界避免误匹配 forest 等）
BRU_KW = re.compile(
    r"\bbrussels\b|\bbrussel\b|\bbruxelles\b|"
    r"\bixelles\b|\belsene\b|\betterbeek\b|\bmolenbeek\b|"
    r"\bschaerbeek\b|\banderlecht\b|\blaeken\b|\bheysel\b|\batomium\b|"
    r"\bsaint-gilles\b|\bsint-gillis\b|\bsaint-josse\b|\bkoekelberg\b|"
    r"\bgrand-place\b|\bplace-jourdan\b|\bmontgomery\b|\bsablon\b|"
    r"\bwoluwe\b|\bauderghem\b|\bwatermael\b|\buccle\b|\bukkel\b|\bjette\b",
    re.IGNORECASE,
)


# ----------------------------------------------------------------------------
# 第 1 步：从原始 CSV 提取去重的布鲁塞尔 hotel_url
# ----------------------------------------------------------------------------
def load_brussels_hotels():
    """返回 [(clean_url, hotel_name), ...]，按 url 去重。"""
    from urllib.parse import urlparse
    hotels = {}
    with open(RAW_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("hotel_url", "").strip()
            if not raw:
                continue
            parsed = urlparse(raw)
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"  # 去掉 query
            name = row.get("hotel_name", "").strip()
            if clean not in hotels and (BRU_KW.search(name) or BRU_KW.search(parsed.path)):
                hotels[clean] = name
    return list(hotels.items())


# ----------------------------------------------------------------------------
# 断点续爬：读已完成的 URL
# ----------------------------------------------------------------------------
def load_done_urls():
    done = set()
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                # 只把 success / partial 视为已完成；failed 留待重跑
                if row.get("status") in ("success", "partial"):
                    done.add(row.get("hotel_url", ""))
    return done


def ensure_csv_header(path, fields):
    """文件不存在时写表头。"""
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()


def append_row(path, fields, row):
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fields).writerow(row)


# ----------------------------------------------------------------------------
# 字段解析
# ----------------------------------------------------------------------------
def extract_jsonld(html):
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    out = []
    for m in pattern.finditer(html):
        try:
            out.append(json.loads(m.group(1).strip()))
        except Exception:
            pass
    return out


def parse_jsonld_fields(jsonld_list):
    """从 JSON-LD 提取 address / city / review_score / review_count / property_type。"""
    res = {
        "address": None, "city": None, "property_type": None,
        "review_score": None, "review_count": None,
    }
    for obj in jsonld_list:
        items = obj if isinstance(obj, list) else [obj]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = str(item.get("@type", ""))
            if not any(k in t for k in
                       ["Hotel", "Lodging", "BedAndBreakfast", "Hostel", "Apartment", "Resort"]):
                continue
            res["property_type"] = res["property_type"] or t

            addr = item.get("address", {})
            if isinstance(addr, dict):
                street = addr.get("streetAddress", "")
                locality = addr.get("addressLocality", "")
                postal = addr.get("postalCode", "")
                country = addr.get("addressCountry", "")
                parts = [p for p in (street, locality, postal, country) if p]
                res["address"] = res["address"] or ", ".join(parts)
                # city 优先用 addressLocality；它常含 "1040 Brussels" 之类
                res["city"] = res["city"] or (locality or None)
            elif isinstance(addr, str):
                res["address"] = res["address"] or addr

            agg = item.get("aggregateRating", {})
            if isinstance(agg, dict):
                res["review_score"] = res["review_score"] or agg.get("ratingValue")
                res["review_count"] = res["review_count"] or agg.get("reviewCount")
    return res


def parse_coords(html):
    """从 data-atlas-latlng / b_map_center / JSON 提取经纬度（多源一致，取第一个）。"""
    m = re.search(r'data-atlas-latlng=["\']([\d\.\-]+),([\d\.\-]+)["\']', html)
    if m:
        return m.group(1), m.group(2)
    lat = re.search(r'b_map_center_lat(?:itude)?["\']?\s*[:=]\s*["\']?([\d\.\-]+)', html)
    lon = re.search(r'b_map_center_lon(?:gitude)?["\']?\s*[:=]\s*["\']?([\d\.\-]+)', html)
    if lat and lon:
        return lat.group(1), lon.group(1)
    return None, None


def parse_stars(html):
    """从 aria-label 'N out of 5 stars/quality rating' 提取星级及类型。
    返回 (star_rating, star_type)：
      star_type = 'official'（官方星级）/ 'quality'（Booking 自评）/ None
    """
    m = re.search(r'(\d)\s*out of 5\s*(stars|quality rating)', html, re.IGNORECASE)
    if m:
        val = m.group(1)
        kind = "official" if "star" in m.group(2).lower() else "quality"
        return val, kind
    return None, None


def parse_price(page):
    """从房型表的价格单元格取最低可用价（EUR）。
    过滤掉 <50 的小额（早餐/服务费噪声）。
    """
    prices = []
    for sel in ['[data-testid="price-and-breakdown"]', ".prco-valign-middle-helper"]:
        for el in page.query_selector_all(sel):
            txt = el.inner_text()
            for num in re.findall(r'€\s?(\d{2,4})', txt):
                v = int(num)
                if v >= 50:           # 过滤押金/早餐/服务费等小额噪声
                    prices.append(v)
        if prices:
            break
    return min(prices) if prices else None


# ----------------------------------------------------------------------------
# 单页抓取（含重试）
# ----------------------------------------------------------------------------
def scrape_one(page, url, name):
    """返回一行 dict。status: success / partial / failed。"""
    full_url = url + QUERY
    last_err = None

    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = page.goto(full_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            # 价格动态加载：尽量等价格元素出现；等不到也继续（走降级）
            got_price_el = False
            try:
                page.wait_for_selector('[data-testid="price-and-breakdown"]',
                                       timeout=PRICE_WAIT)
                got_price_el = True
            except Exception:
                # 退而求其次等 JSON-LD / 旧版价格类，再多给页面一点渲染时间
                try:
                    page.wait_for_selector(
                        'script[type="application/ld+json"], .prco-valign-middle-helper',
                        timeout=8000)
                except Exception:
                    page.wait_for_timeout(5000)

            html = page.content()

            # 若页面仍是 WAF 挑战页（极小），重试
            if len(html) < 50000:
                raise RuntimeError(f"页面过小({len(html)}B)，疑似 WAF 未通过")

            jl = parse_jsonld_fields(extract_jsonld(html))
            lat, lon = parse_coords(html)
            star, star_type = parse_stars(html)
            price = parse_price(page)

            row = {
                "hotel_url": url,
                "hotel_name": name,
                "latitude": lat,
                "longitude": lon,
                "star_rating": star,
                "star_type": star_type,
                "address": jl["address"],
                "city": jl["city"],
                "property_type": jl["property_type"],
                "price": price,
                "price_currency": CURRENCY if price else "",
                "review_score": jl["review_score"],
                "review_count": jl["review_count"],
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": "",
            }

            # 判定 status：核心字段（坐标）齐 = 至少 partial；坐标+价格齐 = success
            has_core = lat and lon
            if has_core and price:
                row["status"] = "success"
            elif has_core:
                row["status"] = "partial"   # 有坐标但无价（价格降级用星级代理）
            else:
                # 连坐标都没有，但拿到了 JSON-LD 字段，也算 partial；全空才 failed
                row["status"] = "partial" if (jl["address"] or star) else "failed"

            if row["status"] != "failed":
                return row
            last_err = "核心字段全空"

        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"

        # 重试退避
        if attempt < MAX_RETRY:
            backoff = 2 ** attempt + random.uniform(0, 2)
            print(f"      ↻ 第 {attempt} 次失败（{last_err}），{backoff:.1f}s 后重试")
            time.sleep(backoff)

    # 全部重试失败
    return {
        "hotel_url": url, "hotel_name": name,
        "latitude": None, "longitude": None, "star_rating": None, "star_type": None,
        "address": None, "city": None, "property_type": None,
        "price": None, "price_currency": "", "review_score": None, "review_count": None,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "failed",
    }


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    hotels = load_brussels_hotels()
    print(f"[1/3] 从原始 CSV 提取布鲁塞尔酒店：{len(hotels)} 家（去重）")

    done = load_done_urls()
    todo = [(u, n) for u, n in hotels if u not in done]
    print(f"[2/3] 断点续爬：已完成 {len(done)} 家，待爬 {len(todo)} 家")

    if not todo:
        print("      ✓ 全部已完成，无需再爬。")
        return

    ensure_csv_header(OUT_CSV, FIELDS)
    ensure_csv_header(FAILED_CSV, ["hotel_url", "hotel_name", "scraped_at", "reason"])

    print(f"[3/3] 开始爬取（统一查询：{CHECKIN}→{CHECKOUT}, 2成人1房, {CURRENCY}）\n")

    n_success = n_partial = n_failed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=UA, locale="en-GB",
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()

        total = len(todo)
        for i, (url, name) in enumerate(todo, 1):
            print(f"  [{i}/{total}] {name[:50]}")
            row = scrape_one(page, url, name)

            append_row(OUT_CSV, FIELDS, row)
            if row["status"] == "success":
                n_success += 1
            elif row["status"] == "partial":
                n_partial += 1
            else:
                n_failed += 1
                append_row(FAILED_CSV,
                           ["hotel_url", "hotel_name", "scraped_at", "reason"],
                           {"hotel_url": url, "hotel_name": name,
                            "scraped_at": row["scraped_at"], "reason": "重试耗尽"})

            print(f"        → {row['status']:8s} | "
                  f"({row['latitude']},{row['longitude']}) | "
                  f"{row['star_rating']}★{row['star_type'] or ''} | "
                  f"€{row['price']} | score {row['review_score']}")
            print(f"        进度: ✓{n_success} ◐{n_partial} ✗{n_failed}")

            if i < total:
                d = random.uniform(DELAY_MIN, DELAY_MAX)
                time.sleep(d)

        browser.close()

    print(f"\n{'='*60}")
    print(f"完成。success={n_success}  partial={n_partial}  failed={n_failed}")
    print(f"输出: {OUT_CSV}")
    if n_failed:
        print(f"失败清单: {FAILED_CSV}（可直接重跑本脚本补爬）")


if __name__ == "__main__":
    main()
