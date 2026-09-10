# CODE PLAN · 工程实现计划

> 配套 `RESEARCH_MASTER_PLAN.md`（研究蓝图）与 `CLAUDE.md`（Agent 守则）。
> **执行者**：Claude Code Agent。**规则**：一个 Stage 一个 Stage 做，**每个 Stage 有验收门禁（Gate），不过 Gate 不许进下一个 Stage**。

---

## 0 · 环境与仓库重建（S0-a，最先做，约 1 小时）

### 0.1 环境（当前是坏的，必须先修）

实测状态：`python3` = Anaconda Python 3.12.4，**numpy 2.4.6 与 pandas / sklearn / pyarrow 二进制不兼容，import 直接崩**；`lightgbm` 未安装。
现有的 `data/` 脚本靠纯标准库 `csv` 绕过这个问题——**新代码不要再绕，直接修环境**。

```bash
# 建独立环境，不要再污染 anaconda base
python3 -m venv .venv-fyp
source .venv-fyp/bin/activate
pip install -U pip
pip install "numpy>=2.1,<3" pandas pyarrow scikit-learn lightgbm scipy statsmodels \
            linearmodels econml matplotlib seaborn tqdm pyyaml python-dotenv
pip install torch transformers datasets peft accelerate sentence-transformers
pip install geopy shapely osmnx  # 位置便利性（POI 距离）
python -c "import numpy,pandas,sklearn,lightgbm,statsmodels; print('env OK')"
```

**Gate 0.1**：上面最后一行打印 `env OK`。

> 说明：`linearmodels` 用于面板 DiD（PanelOLS + 双向固定效应），`econml` 用于双重稳健 / DR-learner。若 `econml` 装不上（它对 sklearn 版本挑剔），可以只用 `statsmodels` + 手写 AIPW，不是阻塞项。

### 0.2 新仓库结构

```
FYP1/
├── CLAUDE.md                    # Agent 守则（入口，最先读）
├── RESEARCH_MASTER_PLAN.md      # 研究蓝图
├── CODE_PLAN.md                 # 本文件
├── BG.md, RESEARCH_PLAN.md      # 旧文档，保留为历史，不再作为权威
├── conf/
│   ├── config.yaml              # 全局配置（路径、随机种子、时间切分点）
│   ├── compset.yaml             # M1 超参（半径网格、m、权重网格）
│   ├── aspects.yaml             # 8 个 aspect 的定义、同义词、种子词
│   └── causal.yaml              # M4 的窗口、δ 阈值、协变量
├── src/
│   ├── common/
│   │   ├── io.py                # 统一读写（parquet 优先）、schema 校验
│   │   ├── schema.py            # 所有中间产物的列定义（单一真相来源）
│   │   ├── geo.py               # haversine、KNN 半径、POI 距离
│   │   └── stats.py             # 贝叶斯收缩、bootstrap CI、Wilcoxon
│   ├── data/
│   │   ├── load_d1_europe.py    # 515K Europe → 统一 schema
│   │   ├── load_d2_hotelrec.py  # HotelRec 抽样 → 统一 schema
│   │   ├── load_d3_belgium.py   # 本项目自采数据 → 统一 schema
│   │   └── build_panel.py       # (hotel, period) 面板构造
│   ├── price/
│   │   └── price_proxy.py       # D4：价格档位代理模型（在 D3 上训练）
│   ├── compset/
│   │   ├── features.py          # demand_mix / text_profile 向量
│   │   ├── build.py             # M1：可替代性图 + 竞争集
│   │   └── validate.py          # T1 留出互预测力 / T2 需求溢出
│   ├── absa/
│   │   ├── sample_for_annotation.py  # 抽 800 条待标注
│   │   ├── llm_annotate.py           # LLM 生成四元组（API，非订阅）
│   │   ├── gold_set.py               # 人工复核合并 + κ/F1 计算
│   │   ├── train_lora.py             # LoRA 微调小模型
│   │   ├── infer.py                  # 批量推理 → review_aspects.parquet
│   │   └── validate_external.py      # 与 HotelRec 子评分相关性
│   ├── repr/
│   │   └── build_crr.py         # M3：竞争集相对表征 + 收缩
│   ├── tourist/
│   │   ├── labels.py            # M5：需求份额增量标签（无泄漏）
│   │   ├── train_ranker.py      # LambdaMART + 加权基线
│   │   └── baselines.py         # 评分/流行度/ItemKNN/BPR/LLM
│   ├── manager/
│   │   ├── treatment.py         # M4：aspect 跃迁事件识别
│   │   ├── estimate_did.py      # CompSet-matched DiD + event study
│   │   ├── estimate_dr.py       # 双重稳健 / AIPW
│   │   ├── policy.py            # 处方策略（预算约束下的 argmax）
│   │   └── narrate.py           # LLM 只做文本化（数字来自结构化输出）
│   ├── eval/
│   │   ├── tourist_eval.py      # NDCG/MAP/Recall + 显著性
│   │   ├── policy_eval.py       # IPS / SNIPS / DR 策略价值
│   │   ├── coupling_eval.py     # H1 双视角耦合检验
│   │   ├── human_eval.py        # 人工评估打分表生成 + Krippendorff α
│   │   └── llm_judge.py         # 多模型集成 judge + 与人工校准
│   └── figures/
│       └── make_all.py          # 论文全部图表，一键重生成
├── data/
│   ├── raw/{d1,d2,d3}/
│   ├── interim/
│   ├── processed/
│   └── annotations/             # gold set（人工标注，进 git）
├── outputs/
│   ├── tables/                  # 论文表格 CSV/TeX
│   ├── figures/
│   └── runs/<run_id>/           # 每次实验的完整快照（config + metrics + log）
├── tests/                       # pytest：schema、几何、统计、泄漏检查
└── paper/                       # LaTeX
```

**Gate 0.2**：目录建好，`src/common/schema.py` 写好，`pytest tests/ -q` 通过（哪怕只有 3 个测试）。

### 0.3 统一 Schema（`src/common/schema.py` 的内容规范）

三个数据集必须归一到同一个 schema，**这是整个工程的地基**：

```python
# reviews.parquet —— 评论级
REVIEW = {
  "review_id": str, "hotel_id": str, "dataset": str,       # d1/d2/d3
  "date": "datetime64[ns]", "rating": float,               # 统一到 0-10
  "text_pos": str, "text_neg": str, "text_all": str,       # d1 天然分列；d2/d3 用 text_all
  "reviewer_nationality": str, "tags_raw": str,
  "trip_type": str, "party_type": str, "room_type": str, "nights": "Int32",
}

# hotels.parquet —— 酒店级
HOTEL = {
  "hotel_id": str, "dataset": str, "name": str, "city": str, "country": str,
  "lat": float, "lng": float,
  "star_rating": "Int8", "star_source": str,               # scraped/imputed/none
  "price": float, "price_currency": str, "price_date": str,
  "price_tier": str, "price_tier_source": str,             # observed/proxy_model/none
  "avg_score": float, "n_reviews_total": "Int32",
}

# panel.parquet —— (hotel, period) 面板
PANEL = {
  "hotel_id": str, "period": str,                          # '2016Q1'
  "n_reviews": "Int32", "d_n_reviews": "Int32",            # 新增评论数 = 需求代理
  "mean_rating": float,
  **{f"asp_{a}_net": float for a in ASPECTS},
  **{f"asp_{a}_mention": float for a in ASPECTS},
  **{f"asp_{a}_negshare": float for a in ASPECTS},
}
```

**硬规则**：
- 任何脚本写盘前调用 `schema.validate(df, SCHEMA_NAME)`，列名/类型不符直接报错退出。
- **禁止**用 CSV 传递中间产物（浮点精度 + 类型丢失），一律 parquet。
- `hotel_id` 全局唯一：`f"{dataset}:{原始主键的 sha1[:12]}"`。

---

## 1 · Stage S0-b：三数据集接入（2–3 天）

### 任务
1. `load_d1_europe.py`：下载 515K Europe → 解析 `Hotel_Address` 得 city/country（6 个城市，字符串匹配即可）→ 解析 `Tags`（是个 Python list 字符串，需 `ast.literal_eval`）→ 拆出 trip_type / party_type / room_type / nights → `Review_Date` 转 datetime → 写 `reviews`/`hotels` parquet。
   - ⚠️ 已知坑：该数据集有 **17 家酒店的 lat/lng 为 NaN**，用 `Hotel_Address` 做一次 Nominatim 反查补全（复用 `data/scraped/geocode_cache.json` 的缓存模式）。
2. `load_d2_hotelrec.py`：从 GitHub 拿 HotelRec，**按城市抽样**（D1 的 6 城市 + 3 个北美城市对照），保留 aspect 子评分列。目标规模 20 万–50 万条评论即可，不要全量 50M。
3. `load_d3_belgium.py`：把现有 `data/booking_reviews copy.csv` + `data/processed/hotels_all.csv` 归一到新 schema。评论文本从 `review_text` 取（`raw_review_text` 是 HTML，丢弃）。
4. `build_panel.py`：按季度聚合成面板。

### Gate S0-b（**硬性**）
- [ ] 三个 `reviews.parquet` 通过 schema 校验，行数打印在报告里
- [ ] D1 酒店坐标覆盖率 ≥ 99%
- [ ] `outputs/tables/dataset_summary.csv`：每数据集的 酒店数/评论数/时间跨度/城市数/中位数评论量
- [ ] **D1 中，每城市 hotel 数 ≥ 100**（若不满足说明解析错了）

---

## 2 · Stage S0-c：价格代理模型（1–2 天）

`src/price/price_proxy.py`：
1. 训练集 = D3 里 **321 家有真实价格**的酒店。
2. 特征：星级、property_type、地址关键词、到市中心距离、评论中的价格感知词频（"expensive", "good value", "overpriced" 等）、评论量、平均分。
3. 目标：**价格三分位（低/中/高）**，分类；同时训练一个回归版本用于算 Spearman。
4. 报告：3 折 CV 的 accuracy、macro-F1、**Spearman ρ(预测价格, 真实价格)**。
5. 用 D3 的 3 个日期快照（2026-07-15/22/29）**实证价格 rank 的稳定性**：算三天之间的 Spearman ρ。这个数字直接写进论文回应 P2。
6. 迁移到 D1/D2 打 `price_tier_source='proxy_model'`。

### Gate S0-c
- [ ] 报告出 Spearman ρ 与三日 rank 稳定性
- [ ] **若 ρ < 0.5 → 触发 R1 止损**：立即在 `conf/compset.yaml` 里把 price 权重设为 0，写进 `outputs/decisions.md`，继续往下走（不要卡住）

---

## 3 · Stage S1：竞争集构建与证伪（1 周）

### 3.1 `src/compset/features.py`
- `demand_mix(hotel)` → 向量：trip_type 比例(2) + party_type 比例(4) + room_type top-10 比例 + nights 分布(4 桶) + 国籍 top-20 比例 + 国籍熵 = 约 41 维，L1 归一化
- `text_profile(hotel)` → SBERT 句向量对该店评论的均值（用 `all-MiniLM-L6-v2`，快）
- **注意**：只用 **train 期（t ≤ T1）** 的评论构造这些特征，避免时序泄漏

### 3.2 `src/compset/build.py`
```
s(i,j) = w_geo·exp(-d_ij/τ) + w_dem·cos(dem_i,dem_j) + w_txt·cos(txt_i,txt_j) + w_pri·1[tier_i=tier_j]
C(h)   = {j : s(h,j) 在 top-m}，m ∈ {5,7,10}
约束   : 同城；d_ij ≤ r_max（r_max 自适应 = h 的第 k 近邻距离，k=15，上限 3km）
```
超参网格：`τ ∈ {300,600,1000}m`，`m ∈ {5,7,10}`，`w ∈ 单纯形上的 20 个网格点`。
**选参依据不是拍脑袋，是 T1 的留出预测力。**

### 3.3 `src/compset/validate.py` —— 两个证伪测试

**T1 · 留出互预测力**
```
对每个 hotel h、每个留出属性 y ∈ {avg_score, d_n_reviews, price}:
    ŷ_compset = mean(y over C(h))
    ŷ_random  = mean(y over 随机同城 m 家)
    ŷ_geo     = mean(y over 最近 m 家)         # 只用地理的消融
报告 R²(y, ŷ_*) 与 ΔR² = R²_compset - R²_random
```

**T2 · 需求溢出（核心证据）**
```
面板回归（双向固定效应）:
    d_n_reviews[h,t] = β·mean(d_n_reviews[j∈C(h), t]) + α_h + γ_t + ε
    对照: 把 C(h) 换成随机同城集合，β 应不显著
预期: 真竞争集的 β 显著为负（替代效应）；随机集不显著
```
> 若 β 为正也有解释（同区域需求共动），那就**加入区域-时间固定效应 `α_region×t`** 吸收共同冲击后再估——这是标准做法，写进方法里。

### Gate S1（**硬性，这是全论文最重要的一道门**）
- [ ] **有效竞争集数量 ≥ 50**（D1 上）；平均规模 5–10
- [ ] T1：`ΔR² > 0` 且对至少 2 个留出属性显著
- [ ] T2：在加入区域-时间固定效应后，β 显著（p < 0.05），随机对照不显著
- [ ] `outputs/tables/compset_validation.csv` + `outputs/figures/fig_compset_validation.png`
- [ ] **不过 Gate → 触发 R2 止损**：把 C1 从核心贡献降级，在 `outputs/decisions.md` 记录，论文重心压到 C3

---

## 4 · Stage S2：ABSA 管线（3–4 周，可与 S3 并行）

### 4.1 aspect 定义（`conf/aspects.yaml`）
8 个：`location, cleanliness, food_breakfast, service_staff, noise_sleep, room_facilities, value_for_money, wifi_tech`
每个给：英文名、中文名、10–20 个种子词、2 个正例句、2 个负例句（用于 few-shot prompt）

### 4.2 标注（`sample_for_annotation.py` → `llm_annotate.py` → `gold_set.py`）
1. 分层抽样 800 条评论（按 rating 分层 × 按数据集分层），拆句
2. LLM 标注：输出 `[(aspect, polarity, evidence_span)]`，**用 API key 调用，不用订阅额度**
3. **人工复核 300 条**（作者自己做，约 4–6 小时）→ `data/annotations/gold_300.jsonl`
4. 计算 LLM-vs-human 的 Cohen's κ（aspect 检出）与 macro-F1（极性）

### 4.3 模型（`train_lora.py` → `infer.py`）
- 弱监督扩充：D1 的 `Positive_Review` / `Negative_Review` 天然带极性 → 几十万条自动标注
- LoRA 微调 DeBERTa-v3-base（现成的 `models/absa/` 可作初始化）或 Qwen2.5-0.5B
- 在 gold_300 上评估；对比 4 个基线：现有关键词门控、zero-shot LLM、InstructABSA、未微调 DeBERTa-ABSA
- 批量推理全量评论 → `data/processed/review_aspects.parquet`

### 4.4 外部验证（`validate_external.py`）
在 D2 (HotelRec) 上跑抽取器，与 TripAdvisor 用户自评的 aspect 子评分算 Pearson/Spearman。
**这是独立于自己标注的外部效度证据，论文里必须有。**

### Gate S2
- [ ] gold_300 上 macro-F1 ≥ 0.75（aspect 检出 + 极性联合）
- [ ] 至少在 2 个基线上显著更优
- [ ] HotelRec 外部相关 r ≥ 0.4（至少 4 个 aspect 达标）
- [ ] **不过 → 触发 R5**：aspect 集合缩到 5 个（location/cleanliness/service/room/value），重跑

---

## 5 · Stage S3：共享表征 + Tourist 侧（2 周）

### 5.1 `src/repr/build_crr.py`
- 贝叶斯收缩：`ã = (n·a + κ·μ_C)/(n+κ)`，`κ = σ²_within / σ²_between`（用竞争集内方差分解估计）
- 竞争集内 z-score 与 percentile
- 位置便利性：OSM POI（地铁站、火车站、主要景点）距离，用 `osmnx` 一次性下载 6 城市的 POI

### 5.2 `src/tourist/labels.py` —— **无泄漏标签（P4 的解法）**
```
时间切分: T1 = 数据 60% 分位, T2 = 80% 分位
特征窗:   t ≤ T1 的所有评论
标签窗:   T1 < t ≤ T2 (valid), t > T2 (test)
标签:     share_h = Δn_reviews[h, 标签窗] / Σ_{j∈C(h)} Δn_reviews[j, 标签窗]
          → 转成竞争集内的 graded relevance（分 5 档）用于 NDCG
```
**泄漏自检（写成 pytest）**：断言特征表里不含任何标签窗的数据；断言 `avg_score` 若入特征，则只用特征窗重算而非用数据集自带的全期 `Average_Score`（后者含未来信息！这是个真实的坑）。

### 5.3 `src/tourist/train_ranker.py` + `baselines.py`
- 主模型：LightGBM LambdaMART，group = 竞争集
- 可解释基线：线性加权打分
- 对比基线：全局评分排序 / 评分+价格过滤 / 流行度 / ItemKNN / BPR-MF / LLM 排序 / 无竞争集相对化的本方法
- 消融：**mask reviews**（把所有 aspect 特征置零）← 回应 SIGIR'20 的批评，必做

### Gate S3
- [ ] 在 test 期，NDCG@10 显著优于最强基线（Wilcoxon p < 0.05，跨竞争集配对）
- [ ] 泄漏自检 pytest 全绿
- [ ] mask-reviews 消融有明显下降（若无下降，**如实写进论文**，这本身是有价值的负结果）

---

## 6 · Stage S4：因果处方模块（6–8 周，最重的一块）★

### 6.1 `src/manager/treatment.py`
```
对每个 (h, k=aspect):
  baseline = mean(ã[h,k,t-W:t-1])       # W=4 期
  跃迁 if  ã[h,k,t] - baseline > δ·σ_C[k]  且  在 t+1, t+2 保持 > baseline
  δ 网格: {0.5, 0.75, 1.0}
  记录 treat_time[h,k]
```
**样本量检查**：若治疗组 < 100 个 (h,k) 事件 → 触发 R4（放宽 δ / 改半年窗口 / 改连续处理）

### 6.2 `src/manager/estimate_did.py`
```
对照组: j ∈ C(h)，在 [t-W, t+H] 内 aspect k 未跃迁
模型:   y[i,s] = Σ_τ β_τ·1[s = treat_time + τ] + α_i + γ_{city×s} + X'δ + ε
        y ∈ {mean_rating, d_n_reviews, compset_rank}
        τ ∈ [-4, +4]  ← event study
标准误: 按 hotel 聚类
输出:   event study 图（必须显示 τ<0 时 β 不显著 = 无预趋势）
```
**必做的稳健性**：
- Placebo-in-time：把 treat_time 前移 4 期，效应应消失
- Placebo-aspect：对随机 aspect 做同样估计
- 不同 δ 阈值的敏感性
- Callaway-Sant'Anna 交错处理估计器（若处理时点交错，TWFE 有偏，这是审稿人会问的）

### 6.3 `src/manager/estimate_dr.py`
AIPW / DR-learner 估计条件平均处理效应 `τ̂(h,k | z_h)` —— 这是处方模块真正需要的（异质性效应）。

### 6.4 `src/manager/policy.py`
```
处方(h, 预算 B) = argmax_{S⊆aspects, Σ_{k∈S} c(k) ≤ B}  Σ_{k∈S} τ̂(h,k | z_h)
成本 c(k): 场景化（3 组假设：等成本 / 软性改进便宜 / 硬件改进贵），全部报告
基线策略: worst-net / most-mentioned-neg / largest-compset-gap / random / LLM-direct
```

### 6.5 `src/manager/narrate.py`
输入 = 结构化 dict（含 τ̂、CI、percentile、gap）→ LLM 输出 3 段话。
**强制约束**：prompt 里明确"只能使用给定数值，不得计算或推断新数字"；输出后用正则抽出所有数字，**逐一校验是否在输入 dict 中**，不匹配则重试。这个校验率写进论文（应为 100%）。

### Gate S4（**论文核心结果的门**）
- [ ] event study 图：τ < 0 时系数不显著（无预趋势）
- [ ] 至少一个 outcome 上处理效应显著且方向合理
- [ ] Placebo 两项均不显著
- [ ] 数字幻觉校验率 = 100%
- [ ] **不过 → 触发 R3**：改 RDD 或 synthetic control；或把主张降级为"预测性关联"（论文仍成立，但卖点变弱，必须诚实写）

---

## 7 · Stage S5：评测与人工评估（3 周）

### 7.1 `src/eval/policy_eval.py` —— 策略价值（**主卖点指标**）
```
测试期回放:
  对每个在 test 期实际发生 aspect 跃迁的 (h,k)：
     观测到的结果提升 Δy
     各策略是否会推荐 k → 用 IPS / SNIPS / DR 估计策略价值
  V(π) = Σ  w_i · Δy_i · 1[π 推荐了实际改进的 aspect] / P(k | h)
报告: V(本方法) vs V(各基线)，bootstrap 95% CI
```

### 7.2 `src/eval/coupling_eval.py` —— H1 检验
对 test 期改进过 aspect 的酒店，比较 Tourist 排序位次变化：本方法推荐组 vs 启发式组，Mann-Whitney U 检验。

### 7.3 `src/eval/human_eval.py` + `llm_judge.py`
- 生成 60 份建议 × 4 个维度的打分表（CSV，发给 3 位评估者）
- 计算 Krippendorff's α
- LLM judge：≥2 个模型家族、顺序随机化、显式 rubric；报告与人工评分的 Spearman

### Gate S5
- [ ] Policy Value 优于全部 4 个基线（至少 2 个显著）
- [ ] H1 检验有结果（支持或不支持都要如实报）
- [ ] Krippendorff α ≥ 0.6；LLM judge 与人工 Spearman 报告出来

---

## 8 · Stage S6：论文与复现包（6 周）

- `src/figures/make_all.py`：一条命令重生成全部图表
- `outputs/runs/<run_id>/`：每次实验存 config + git hash + metrics + 环境快照
- README：从零复现的完整步骤
- 论文按 `RESEARCH_MASTER_PLAN.md` 附录 B 的结构写

---

## 9 · 工程硬规则（Agent 必须遵守）

1. **一个 Stage 一个分支/一次提交**，commit message 写清 Gate 通过情况。
2. **每个脚本独立可运行**，`python -m src.xxx.yyy --config conf/config.yaml`，中间产物落盘，下一个 Stage 从盘读。
3. **禁止在 notebook 里做正式实验**；notebook 只用于探索，结论必须回落到脚本。
4. **随机种子固定**（`conf/config.yaml` 的 `seed: 42`），且在 run 记录里存种子。
5. **任何"看起来结果很好"的时刻，先跑泄漏自检**。时序数据里，好结果的第一嫌疑是泄漏。
6. **决策日志**：任何偏离本计划的决定写进 `outputs/decisions.md`（时间、原因、替代方案）。论文的 Limitations 直接从这里长出来。
7. **长任务（爬取、LoRA 微调、全量推理）由人工用 `python` 跑**，Agent 只写/调代码——见 `CLAUDE.md`。
8. **不提交**：`data/raw/`（大）、`.venv*`、模型权重、任何凭证。`data/annotations/`（人工标注）**要**提交，它是论文资产。

---

## 10 · 优先级（时间不够时的砍法）

```
绝对不能砍: S0（数据底盘） · S1（竞争集+证伪） · S4（因果） · S5.1（策略价值）
可以砍薄:   S3 的神经 ranker（只留 LambdaMART + 线性基线）
            S5.3 的人工评估规模（3人×60 → 3人×30）
            S2 的 aspect 数（8 → 5）
            D2 (HotelRec) 的规模（只做外部验证，不做第二市场实验）
最后才砍:   D3 比利时数据的泛化实验（但这样会失去"跨市场"卖点）
```

> 记住：**这篇论文的价值 100% 在于「诊断→处方→因果验证」这个闭环**。Tourist 侧只是让"双视角"这个故事成立的必要配件，不是卖点。砍东西时按这个原则判断。
