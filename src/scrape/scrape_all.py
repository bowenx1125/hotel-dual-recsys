#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 0（全量）：爬取全部 821 家酒店属性

相对布鲁塞尔 MVP 版（scrape_brussels.py）的改进：
  1. 覆盖原始 CSV 中全部去重 hotel_url（不再按名字筛城市）——城市改由坐标反推（见 clean_all.py）。
  2. price 换日期重试：第一个日期无价 → 依次试第 2、3 个可比工作日，取首个有价的。
  3. 存原始 HTML（gzip）：scrape once, parse many——以后改解析逻辑直接重解析本地，不用重爬。
  4. 识别"假坐标"（Booking 兜底点）→ 标记为需后续 geocoding，不存垃圾坐标。

合规：每页随机延迟、UA 正常、不绕验证码、不破解 bot 检测。
鲁棒：断点续爬、重试退避、失败记录、进度打印。

运行（由用户自己跑，耗时约 3–5 小时，可整夜无人值守）：
  python3 src/scrape/scrape_all.py
  # 用主环境（playwright 装在这里）。本脚本只用标准库+playwright，
  # 不碰 pandas/numpy/sklearn，所以不受 numpy 2.x 冲突影响。

幂等：重跑跳过已成功/部分成功的 URL，只补未完成的。
"""
import os
import re
import csv
import json
import gzip
import time
import random
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# ----------------------------------------------------------------------------
# 路径
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW_CSV    = os.path.join(ROOT, "data", "booking_reviews copy.csv")
OUT_DIR    = os.path.join(ROOT, "data", "scraped")
HTML_DIR   = os.path.join(OUT_DIR, "html")                       # 原始 HTML 落盘目录
OUT_CSV    = os.path.join(OUT_DIR, "hotel_attributes_all.csv")
FAILED_CSV = os.path.join(OUT_DIR, "failed_urls_all.csv")

# ----------------------------------------------------------------------------
# 抓取参数
# ----------------------------------------------------------------------------
# 3 个可比工作日（均为周三，住 1 晚，避开周末/节假日）
PRICE_DATES = [
    ("2026-07-15", "2026-07-16"),
    ("2026-07-22", "2026-07-23"),
    ("2026-07-29", "2026-07-30"),
]
CURRENCY = "EUR"

def query_for(checkin, checkout):
    return (f"?checkin={checkin}&checkout={checkout}"
            f"&group_adults=2&no_rooms=1&group_children=0&selected_currency={CURRENCY}")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

DELAY_MIN, DELAY_MAX = 3.0, 7.0
MAX_RETRY    = 3          # WAF/网络失败重试次数
PAGE_TIMEOUT = 45000
PRICE_WAIT   = 9000       # 等价格控件出现（ms）；有空房时几秒内就渲染

FAKE_COORD = ("50.8474280093567", "4.35258558669035")  # Booking 兜底点 = 抓取失败/无精确坐标

FIELDS = [
    "hotel_url", "hotel_name", "latitude", "longitude", "coord_is_fake",
    "star_rating", "star_type", "address", "city_raw", "property_type",
    "price", "price_date", "price_currency", "review_score", "review_count",
    "html_file", "scraped_at", "status",
]


# ----------------------------------------------------------------------------
# 第 1 步：提取全部去重 hotel_url
# ----------------------------------------------------------------------------
def clean_url(u):
    p = urlparse(u.strip())
    return f"{p.scheme}://{p.netloc}{p.path}"


def load_all_hotels():
    """返回 [(clean_url, hotel_name), ...]，按 url 去重。"""
    hotels = {}
    with open(RAW_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row.get("hotel_url", "").strip()
            if not raw:
                continue
            cu = clean_url(raw)
            if cu not in hotels:
                hotels[cu] = row.get("hotel_name", "").strip()
    return list(hotels.items())


def load_done_urls():
    done = set()
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("status") in ("success", "partial"):
                    done.add(row.get("hotel_url", ""))
    return done


def ensure_header(path, fields):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()


def append_row(path, fields, row):
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fields).writerow(row)


def slug_of(url):
    m = re.search(r"/hotel/([a-z]{2})/([^/.?]+)", url)
    return f"{m.group(1)}_{m.group(2)}" if m else re.sub(r"\W+", "_", url)[-60:]


# ----------------------------------------------------------------------------
# 解析（与 MVP 版一致，多来源兜底）
# ----------------------------------------------------------------------------
def extract_jsonld(html):
    pat = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE)
    out = []
    for m in pat.finditer(html):
        try:
            out.append(json.loads(m.group(1).strip()))
        except Exception:
            pass
    return out


def parse_jsonld_fields(jsonld_list):
    res = {"address": None, "city": None, "property_type": None,
           "review_score": None, "review_count": None}
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
                locality = addr.get("addressLocality", "")
                parts = [addr.get("streetAddress", ""), locality,
                         addr.get("postalCode", ""), addr.get("addressCountry", "")]
                res["address"] = res["address"] or ", ".join(p for p in parts if p)
                res["city"] = res["city"] or (locality or None)
            elif isinstance(addr, str):
                res["address"] = res["address"] or addr
            agg = item.get("aggregateRating", {})
            if isinstance(agg, dict):
                res["review_score"] = res["review_score"] or agg.get("ratingValue")
                res["review_count"] = res["review_count"] or agg.get("reviewCount")
    return res


def parse_coords(html):
    m = re.search(r'data-atlas-latlng=["\']([\d\.\-]+),([\d\.\-]+)["\']', html)
    if m:
        return m.group(1), m.group(2)
    lat = re.search(r'b_map_center_lat(?:itude)?["\']?\s*[:=]\s*["\']?([\d\.\-]+)', html)
    lon = re.search(r'b_map_center_lon(?:gitude)?["\']?\s*[:=]\s*["\']?([\d\.\-]+)', html)
    if lat and lon:
        return lat.group(1), lon.group(1)
    m2 = re.search(r'"latitude"\s*:\s*"?([\d\.\-]+)"?.{0,40}?"longitude"\s*:\s*"?([\d\.\-]+)"?',
                   html, re.DOTALL)
    if m2:
        return m2.group(1), m2.group(2)
    return None, None


def parse_stars(html):
    m = re.search(r'(\d)\s*out of 5\s*(stars|quality rating)', html, re.IGNORECASE)
    if m:
        return m.group(1), ("official" if "star" in m.group(2).lower() else "quality")
    return None, None


def parse_price(page):
    prices = []
    for sel in ['[data-testid="price-and-breakdown"]', ".prco-valign-middle-helper"]:
        for el in page.query_selector_all(sel):
            for num in re.findall(r'€\s?(\d{2,4})', el.inner_text()):
                v = int(num)
                if v >= 50:                     # 过滤押金/服务费小额噪声
                    prices.append(v)
        if prices:
            break
    return min(prices) if prices else None


# ----------------------------------------------------------------------------
# 单页抓取：先 date1 拿全字段，无价则换 date2/date3 只补价
# ----------------------------------------------------------------------------
def goto_and_render(page, url, price_wait=PRICE_WAIT):
    """加载页面，等价格控件或 JSON-LD 出现。返回 (html, got_price_el)。"""
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    got_price_el = False
    try:
        page.wait_for_selector('[data-testid="price-and-breakdown"]', timeout=price_wait)
        got_price_el = True
    except Exception:
        try:
            page.wait_for_selector(
                'script[type="application/ld+json"], .prco-valign-middle-helper', timeout=6000)
        except Exception:
            page.wait_for_timeout(3000)
    return page.content(), got_price_el


def scrape_one(page, url, name):
    base_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            # ---- date1：拿位置/星级/地址/评分 + 尝试价格 ----
            ci, co = PRICE_DATES[0]
            html, _ = goto_and_render(page, url + query_for(ci, co))
            if len(html) < 50000:
                raise RuntimeError(f"页面过小({len(html)}B)，疑似 WAF 未通过")

            jl = parse_jsonld_fields(extract_jsonld(html))
            lat, lon = parse_coords(html)
            star, star_type = parse_stars(html)
            price = parse_price(page)
            price_date = ci if price else ""
            html_to_save = html

            # 假坐标检测（必须在 page_is_real 之前）：Booking 兜底点 = 无精确坐标，置空留给 geocoding
            coord_fake = int((lat, lon) == FAKE_COORD)
            if coord_fake:
                lat = lon = None

            # 页面是否真实渲染出酒店（有真坐标/地址/星级任一）。死页/已下架不做日期重试，省时间。
            page_is_real = bool((lat and lon) or jl["address"] or star)

            # ---- price 换日期重试（仅对真实页面；重试用更短等待）----
            di = 1
            while price is None and page_is_real and di < len(PRICE_DATES):
                ci2, co2 = PRICE_DATES[di]
                html2, _ = goto_and_render(page, url + query_for(ci2, co2), price_wait=7000)
                p2 = parse_price(page)
                if p2 is not None:
                    price = p2
                    price_date = ci2
                    html_to_save = html2     # 存有价的那次
                di += 1
                time.sleep(random.uniform(1.0, 2.0))

            # 存 HTML（gzip）
            html_file = ""
            if len(html_to_save) >= 50000:
                fn = slug_of(url) + ".html.gz"
                with gzip.open(os.path.join(HTML_DIR, fn), "wt", encoding="utf-8") as gf:
                    gf.write(html_to_save)
                html_file = fn

            row = {
                "hotel_url": url, "hotel_name": name,
                "latitude": lat, "longitude": lon, "coord_is_fake": coord_fake,
                "star_rating": star, "star_type": star_type,
                "address": jl["address"], "city_raw": jl["city"],
                "property_type": jl["property_type"],
                "price": price, "price_date": price_date,
                "price_currency": CURRENCY if price else "",
                "review_score": jl["review_score"], "review_count": jl["review_count"],
                "html_file": html_file,
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": "",
            }
            # status：有地址或坐标或星级 = 至少 partial；都没有 = failed
            if (lat and lon) or jl["address"] or star:
                row["status"] = "success" if (lat and lon and price and jl["address"]) else "partial"
            else:
                row["status"] = "failed"

            if row["status"] != "failed":
                return row
            # 页面已完整渲染(>50KB)但无任何字段 = 真·死页/已下架，立即返回，不浪费 WAF 重试
            return row
        except Exception as e:
            base_err = f"{type(e).__name__}: {e}"

        if attempt < MAX_RETRY:
            backoff = 2 ** attempt + random.uniform(0, 2)
            print(f"      ↻ 第 {attempt} 次失败（{base_err}），{backoff:.1f}s 后重试")
            time.sleep(backoff)

    return {f: None for f in FIELDS} | {
        "hotel_url": url, "hotel_name": name, "coord_is_fake": 0,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "failed",
    }


def main():
    os.makedirs(HTML_DIR, exist_ok=True)
    hotels = load_all_hotels()
    print(f"[1/3] 提取全部去重酒店: {len(hotels)} 家")

    done = load_done_urls()
    todo = [(u, n) for u, n in hotels if u not in done]
    print(f"[2/3] 断点续爬: 已完成 {len(done)}，待爬 {len(todo)}")
    if not todo:
        print("      ✓ 全部完成。")
        return

    ensure_header(OUT_CSV, FIELDS)
    ensure_header(FAILED_CSV, ["hotel_url", "hotel_name", "scraped_at", "reason"])
    print(f"[3/3] 开始（price 试 {len(PRICE_DATES)} 个日期，存 HTML 到 {HTML_DIR}）\n")

    n_s = n_p = n_f = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB",
                                  viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        total = len(todo)
        t0 = time.time()
        for i, (url, name) in enumerate(todo, 1):
            row = scrape_one(page, url, name)
            append_row(OUT_CSV, FIELDS, row)
            if row["status"] == "success":
                n_s += 1
            elif row["status"] == "partial":
                n_p += 1
            else:
                n_f += 1
                append_row(FAILED_CSV, ["hotel_url", "hotel_name", "scraped_at", "reason"],
                           {"hotel_url": url, "hotel_name": name,
                            "scraped_at": row["scraped_at"], "reason": "重试耗尽"})
            # 进度（每家一行，含预计剩余时间）
            elapsed = time.time() - t0
            eta = elapsed / i * (total - i) / 60
            print(f"  [{i}/{total}] {row['status']:7s} | "
                  f"loc={'✓' if row['latitude'] else '✗'} "
                  f"€{row['price'] or '-'}@{row['price_date'] or '-'} "
                  f"{row['star_rating'] or '?'}★ | ✓{n_s} ◐{n_p} ✗{n_f} | "
                  f"ETA {eta:.0f}min | {name[:30]}")
            if i < total:
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        browser.close()

    print(f"\n{'='*60}\n完成。success={n_s} partial={n_p} failed={n_f}")
    print(f"属性: {OUT_CSV}\nHTML: {HTML_DIR}\n失败: {FAILED_CSV}")
    print("下一步: python src/scrape/clean_all.py（清洗+地址反查坐标+坐标定城市）")


if __name__ == "__main__":
    main()
