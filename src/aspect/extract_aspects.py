#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2：Aspect-Based Sentiment 提取（创新点 ③）

固定 7 个 aspect：location / cleanliness / breakfast / service / noise / room / value
两步法（避免预训练 ABSA 模型"假设 aspect 一定存在"的问题）：
  1. 门控（gating）：关键词词典判断评论是否提及该 aspect；未提及 → not_mentioned。
  2. 情感分类：提及的 (review, aspect) 喂 deberta-v3-absa 模型 → Positive/Negative/Neutral。

输出：
  data/processed/review_aspects.jsonl   每条评论 × 每个 aspect 的情感（明细，供竞争集层面差评聚合）
  data/processed/aspect_features.csv     每家酒店的 aspect 质量向量 + 差评热点分布

差评定义：rating < 7（Booking 10 分制）。差评 aspect 热点在竞争集层面聚合更稳健
（单店差评稀疏）。

运行（用专用 venv，避开 anaconda 的 numpy 冲突）：
  .venv-absa/bin/python src/aspect/extract_aspects.py

耗时长任务（~3600 评论 × 命中的 aspect），由你自己 python 运行，不消耗订阅额度。
断点续跑：已处理的 review index 写入 jsonl，重跑自动跳过。
"""
import os
# 强制离线：用本地已下好的模型，绝不联网（HF 在线下载器会卡死，见 models/absa/）
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import re
import csv
import json
import sys
from urllib.parse import urlparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
COMPSET_CSV = os.path.join(ROOT, "data", "processed", "compsets.csv")
RAW_CSV     = os.path.join(ROOT, "data", "booking_reviews copy.csv")
OUT_JSONL   = os.path.join(ROOT, "data", "processed", "review_aspects.jsonl")
OUT_CSV     = os.path.join(ROOT, "data", "processed", "aspect_features.csv")

# 本地模型目录（用 curl 预先下好，避开会卡死的 HF 在线下载器）
MODEL = os.path.join(ROOT, "models", "absa")
NEG_RATING_THRESHOLD = 7.0   # rating < 7 视为差评

ASPECTS = ["location", "cleanliness", "breakfast", "service", "noise", "room", "value"]

# 门控词典：评论文本（小写）命中任一词 = 提及该 aspect
ASPECT_KEYWORDS = {
    "location": ["location", "located", "locate", "metro", "subway", "station",
                 "walk", "walking", "centre", "center", "central", "downtown",
                 "distance", "nearby", "close to", "far from", "transport",
                 "tram", "bus", "airport", "neighbourhood", "neighborhood",
                 "area", "grand place", "city center", "city centre"],
    "cleanliness": ["clean", "dirty", "dust", "dusty", "hygien", "spotless",
                    "stain", "smell", "smelly", "tidy", "mold", "mould",
                    "filthy", "unclean", "immaculate", "grubby"],
    "breakfast": ["breakfast", "buffet", "morning meal", "croissant",
                  "continental breakfast", "brekkie"],
    "service": ["staff", "service", "reception", "receptionist", "helpful",
                "friendly", "rude", "welcome", "welcoming", "host", "hostess",
                "manager", "employee", "concierge", "attentive", "polite",
                "unhelpful", "courteous"],
    "noise": ["noise", "noisy", "quiet", "loud", "soundproof", "sound proof",
              "silent", "silence", "hear", "heard", "traffic noise",
              "thin wall", "peaceful"],
    "room": ["room", "bed", "bedroom", "bathroom", "shower", "toilet",
             "spacious", "comfortable", "comfy", "mattress", "pillow",
             "air conditioning", "air con", "a/c", "heating", "cramped",
             "size", "tiny room", "small room", "clean room"],
    "value": ["value", "price", "expensive", "cheap", "worth", "money",
              "overpriced", "affordable", "cost", "pricey", "bargain",
              "value for money", "good deal", "reasonable price"],
}
# 预编译为单个正则（词边界，cleanliness 等用前缀匹配命中 clean/cleaner/cleanliness）
ASPECT_RE = {}
for asp, kws in ASPECT_KEYWORDS.items():
    parts = []
    for kw in kws:
        if " " in kw:
            parts.append(re.escape(kw))
        else:
            parts.append(r"\b" + re.escape(kw))   # 前缀边界，clean→cleaner/cleanliness
    ASPECT_RE[asp] = re.compile("|".join(parts), re.IGNORECASE)


def clean_url(u):
    p = urlparse(u.strip())
    return f"{p.scheme}://{p.netloc}{p.path}"


def gate(text):
    """返回该评论提及的 aspect 列表。"""
    return [a for a in ASPECTS if ASPECT_RE[a].search(text)]


def load_target_hotels():
    """compset_valid=1 的酒店 url → (name, compset_id)。"""
    targets = {}
    with open(COMPSET_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["compset_valid"] == "1":
                targets[r["hotel_url"]] = (r["hotel_name"], r["compset_id"])
    return targets


def load_reviews(targets):
    """返回 [(review_id, hotel_url, text, rating), ...] 仅目标酒店、非空文本。"""
    out = []
    with open(RAW_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            u = row.get("hotel_url", "").strip()
            if not u:
                continue
            cu = clean_url(u)
            if cu not in targets:
                continue
            text = (row.get("review_text") or "").strip()
            if not text or len(text) < 5:
                continue
            try:
                rating = float(row.get("rating")) if row.get("rating") else None
            except ValueError:
                rating = None
            out.append((row.get("index", ""), cu, text, rating))
    return out


def load_done_ids():
    done = set()
    if os.path.exists(OUT_JSONL):
        with open(OUT_JSONL, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["review_id"])
                except Exception:
                    pass
    return done


def main():
    targets = load_target_hotels()
    reviews = load_reviews(targets)
    done = load_done_ids()
    todo = [r for r in reviews if r[0] not in done]
    print(f"目标酒店: {len(targets)} 家 | 评论: {len(reviews)} 条 | "
          f"已处理: {len(done)} | 待处理: {len(todo)}")
    if not todo:
        print("全部已处理，直接聚合。")
    else:
        # 延迟加载模型（gating 阶段不需要）
        print("加载 ABSA 模型...")
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        tok = AutoTokenizer.from_pretrained(MODEL)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL)
        model.eval()
        id2label = {i: l.lower() for i, l in model.config.id2label.items()}

        @torch.no_grad()
        def absa(text, aspect):
            inp = tok(text, aspect, return_tensors="pt", truncation=True, max_length=256)
            probs = torch.softmax(model(**inp).logits, dim=1)[0]
            idx = int(probs.argmax())
            return id2label[idx], round(float(probs[idx]), 3)

        n = len(todo)
        with open(OUT_JSONL, "a", encoding="utf-8") as fout:
            for i, (rid, url, text, rating) in enumerate(todo, 1):
                mentioned = gate(text)
                asp_sent = {}
                for asp in mentioned:
                    lab, conf = absa(text, asp)
                    asp_sent[asp] = {"sentiment": lab, "conf": conf}
                rec = {
                    "review_id": rid, "hotel_url": url,
                    "rating": rating, "is_negative": (rating is not None and rating < NEG_RATING_THRESHOLD),
                    "aspects": asp_sent,
                }
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if i % 100 == 0 or i == n:
                    print(f"  [{i}/{n}] 处理中...")
        print("情感提取完成，开始聚合。")

    aggregate(targets)


def aggregate(targets):
    """从 jsonl 聚合每家酒店的 aspect 质量向量 + 差评热点分布。"""
    # 每家酒店：aspect → [pos, neg, neu] 计数；差评里 aspect → neg 计数
    hotel_asp = defaultdict(lambda: defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0}))
    hotel_neg_asp = defaultdict(lambda: defaultdict(int))  # 差评中各 aspect 的负面提及
    hotel_total = defaultdict(int)
    hotel_neg_total = defaultdict(int)

    with open(OUT_JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            url = rec["hotel_url"]
            hotel_total[url] += 1
            is_neg = rec.get("is_negative")
            if is_neg:
                hotel_neg_total[url] += 1
            for asp, d in rec["aspects"].items():
                s = d["sentiment"]
                if s in ("positive", "negative", "neutral"):
                    hotel_asp[url][asp][s] += 1
                    if is_neg and s == "negative":
                        hotel_neg_asp[url][asp] += 1

    # 写 CSV：每家酒店一行，每个 aspect 一个净情感分 + 提及率；差评热点单独列
    fields = ["hotel_url", "hotel_name", "compset_id", "n_reviews", "n_negative"]
    for a in ASPECTS:
        fields += [f"{a}_net", f"{a}_mention_rate"]
    for a in ASPECTS:
        fields += [f"neg_{a}_share"]

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for url, (name, cs_id) in targets.items():
            total = hotel_total.get(url, 0)
            row = {"hotel_url": url, "hotel_name": name, "compset_id": cs_id,
                   "n_reviews": total, "n_negative": hotel_neg_total.get(url, 0)}
            for a in ASPECTS:
                c = hotel_asp[url][a]
                m = c["positive"] + c["negative"] + c["neutral"]
                # 净情感分 = (pos - neg) / mentioned，范围 [-1,1]；未提及为空
                row[f"{a}_net"] = round((c["positive"] - c["negative"]) / m, 3) if m else ""
                row[f"{a}_mention_rate"] = round(m / total, 3) if total else ""
            # 差评热点：该酒店差评里各 aspect 负面提及占总差评负面提及的比例
            neg_total_mentions = sum(hotel_neg_asp[url].values())
            for a in ASPECTS:
                row[f"neg_{a}_share"] = (round(hotel_neg_asp[url][a] / neg_total_mentions, 3)
                                          if neg_total_mentions else "")
            w.writerow(row)

    print(f"\n聚合输出: {OUT_CSV}（{len(targets)} 家）")
    print(f"明细: {OUT_JSONL}")


if __name__ == "__main__":
    main()
