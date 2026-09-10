# AUTORUN SPEC · 全自动执行规范（10 天连续运行 → 数据 + 代码 + 论文）

> **本文件是给 AI Agent 的可执行规范，不是给人读的计划书。**
> 目标：Agent 连续运行约 10 天，自动产出 ①清洗后的数据库 ②全部代码 ③一篇完整论文。
> 每个 STEP 都写清四件事：**【怎么做】【为什么】【创新点】【预期结果】**。
> 撰写日期：2026-09-04 ｜ 配套：`PAPER_STRATEGY.md`（命题）、`SPRINT_44D.md`（截稿日历）

---

## Part 0 · 自主性设计：人类触点如何归零

原计划里有四个人类触点，逐一消除：

| 原触点 | 消除方式 | 是否真的更差？ |
|---|---|---|
| Kaggle 账号下载数据 | 改用 **HuggingFace 公开镜像** `Dricz/515k-Hotel-Reviews-In-Europe`，无需任何凭证 | 否，完全等价 |
| 500 句人工标注 | 改用**三重自动验证**（结构真值 / 跨检测器一致性 / 外部锚定 HotelRec 用户自评子评分） | **反而更强**——HotelRec 的 aspect 子评分是数万名真实用户自己打的标签，是独立于我们的人类真值，规模比 500 句大三个数量级 |
| Gate 人工判断 | 改为**预注册的数值阈值 + 自动分支**（Part 2 的决策表） | 否，反而消除了"报喜不报忧"偏差 |
| 论文写作 | 改为**事实库驱动生成 + 三轮对抗自审**（STEP 36–38） | 见下方唯一保留项 |

### 唯一保留的人类步骤（必须说清楚）

**Bowen 必须自己通读并核实最终论文，然后才能提交。** 原因有三，都不是形式主义：

1. 会议与学校对 AI 生成文本有披露/限制规定，署名者要为内容负责；
2. WWW 有 rebuttal 期，你要在 12 月为论文里每一个数字辩护；
3. FYP 有答辩，导师会问方法细节。

所以本规范的设计目标不是"人完全不看"，而是：**把人的工作从"执行"压缩到"验收"** —— 从几百小时降到几小时。
Agent 会在 `outputs/REPORT.md` 里为每一步自动生成【怎么做/为什么/结果】的说明，验收时读这一份即可。

### 已实测的机器事实（规范按此设计，不要假设别的）

```
Apple M5 · 16 GB RAM · 可用磁盘 109 GB · torch 2.12.0 · MPS 可用
python3 = Anaconda 3.12.4，numpy 2.4.6 与 pandas/sklearn 二进制冲突 → 必须建新 venv
无 kaggle 凭证；有 huggingface-cli
```
**内存纪律**：16 GB 意味着不能把 515K 条评论的全文一次性读进 pandas 再做 embedding。
所有文本处理必须**分块（chunk=20000 行）+ 落 parquet**，embedding 用 `float16` 存。

---

## Part 1 · 总架构

```
阶段 0  引导            Day 0      STEP 00–02    环境 + 数据 + 完整性
阶段 1  测量层          Day 1      STEP 03–10    aspect 检测 + 去混杂质量面板   ★创新②
阶段 2  竞争集          Day 2      STEP 11–16    构建 + 两个证伪测试            ★创新③
阶段 3  因果            Day 3–4    STEP 17–23    DiD + event study + placebo
阶段 4  皇冠            Day 5–6    STEP 24–28    peer IV + Figure 1             ★核心命题
阶段 5  策略与推荐      Day 7      STEP 29–32    处方策略 + Tourist 排序
阶段 6  稳健性          Day 8      STEP 33–34    稳健性矩阵 + 第二面板复制
阶段 7  论文            Day 9–10   STEP 35–39    事实库 → 论文 → 对抗自审
```

### 目录（Agent 自行创建）

```
FYP1/
├── conf/            config.yaml, aspects.yaml, compset.yaml, causal.yaml
├── src/             见 CODE_PLAN.md §0.2 的模块划分
├── data/raw|interim|processed/
├── outputs/
│   ├── steps/STEP_XX/{metrics.json, log.txt, artifacts/}
│   ├── facts.json           ← 论文里每一个数字的唯一来源
│   ├── decisions.md         ← 自动决策日志
│   ├── REPORT.md            ← 自动生成的【怎么做/为什么/结果】叙述
│   └── NEXT.md              ← 断点续跑的指针
├── paper/           main.tex, sections/*.tex, figs/
└── state.json       ← 执行状态机
```

### 执行契约（每个 STEP 必须遵守）

1. **幂等**：重跑不改变结果；已完成的 STEP 直接跳过（读 `state.json`）
2. **原子**：产物先写 `.tmp` 再 `os.replace`，避免中断留下半成品
3. **自检**：每个 STEP 末尾跑自己的 assert，失败则写 `status: FAILED` 并触发降级
4. **留痕**：`metrics.json` 记录所有关键数字；**论文只能从 `facts.json` 取数**
5. **续跑**：任何时候被中断，读 `state.json` + `NEXT.md` 即可从下一个 STEP 继续

---

## Part 2 · 自动决策表（预注册，不允许事后改）

> 这张表是本规范最重要的部分。**所有分支在跑之前就定死**，Agent 不需要判断，只需要比对阈值。
> 这同时是论文可信度的来源——预注册的阈值排除了 p-hacking。

| 决策点 | 统计量 | 阈值 | 通过 | 不通过 |
|---|---|---|---|---|
| **D1** 数据可用性 | D1 行数 / 酒店数 / 坐标覆盖率 | ≥50万 / ≥1400 / ≥95% | 继续 | 换 HF 备用镜像 → 再不行用 D3 单数据集模式 |
| **D2** 抽样截断 | corr(本地评论数, `Total_Number_of_Reviews`) 与截断检验 | 无硬性上限截断 | 需求代理用**份额** | 仍用份额（份额对恒定抽样率免疫），但在 Limitations 明写 |
| **D3** aspect 检测质量 | 三检测器 Krippendorff α | α ≥ 0.60 | 继续 | 缩到 5 个最清晰 aspect 重跑 |
| **D4** 外部锚定 | 与 HotelRec 子评分的 Spearman ρ（逐 aspect） | ≥4 个 aspect 的 ρ ≥ 0.35 | 继续 | 只保留达标的 aspect |
| **D5** 竞争集有效性 | 有效竞争集数（规模 5–10、同城） | ≥ 50 | 继续 | 放宽半径网格上限至 3 km 重跑 |
| **D6** T2 需求溢出 | 同集需求系数 β（含 city×month FE） | \|β\| 显著 p<0.05 且随机对照不显著 | 竞争集作为核心贡献 | 竞争集降级为方法组件，论文重心移到因果 |
| **D7** 主因果效应 | `Δq_own` 系数 | 显著 p<0.05 | 继续 | → **Plan C**（测量论文） |
| **D8** 无预趋势 | event study τ∈[-6,-1] 的联合检验 | 联合 F 检验 p > 0.10 | 因果主张成立 | 改用 Callaway–Sant'Anna；仍不过 → 降级为"预测性关联" |
| **D9 ★ performativity** | `Δq_own × peer_adopt` 交互项 | 系数 < 0 且 p<0.05 | → **Plan A** | → **Plan B**（零结果论文） |
| **D10** 弱工具 | 二阶邻居 IV 一阶段 F | F > 10 | 报 IV 结果 | 只报 OLS + 明写弱工具问题 |
| **D11** 策略价值 | V(ours) vs 最优基线，bootstrap CI | CI 不含 0 | 主卖点成立 | 报为"无显著差异"，诚实写 |

**分支即论文标题**：
- Plan A（D9 通过）：*Prescriptive Recommendation is Performative: Returns to Provider Quality Investment under Competition* → WWW
- Plan B（D7 通过、D9 不通过）：*Are Returns to Quality Competed Away? Testing Supply-Side Equilibrium Predictions in a Real Marketplace* → RecSys/CIKM
- Plan C（D7 不通过）：*Review Sentiment Is Not Quality: Guest-Mix Confounding in Hotel Review Mining* → CIKM resource / ECIR

---

## Part 3 · STEP 逐条规范

> 格式：**【怎么做】【为什么】【创新点】【预期结果】【产出】【自检】**
> 没有【创新点】的 STEP 写 "—"（是基础设施，不是卖点）。

---

### 阶段 0 · 引导

#### STEP 00 · 环境自举
**怎么做**
```bash
python3 -m venv .venv-fyp && source .venv-fyp/bin/activate && pip install -U pip
pip install "numpy>=2.1,<3" pandas pyarrow scikit-learn lightgbm scipy statsmodels linearmodels pyfixest \
            torch transformers sentence-transformers datasets huggingface_hub \
            matplotlib seaborn tqdm pyyaml networkx krippendorff
python -c "import numpy,pandas,sklearn,lightgbm,statsmodels,pyfixest,torch;print('env OK', torch.backends.mps.is_available())"
```
**为什么** 当前 anaconda base 的 numpy 2.4.6 与 pandas/sklearn 二进制冲突，`import pandas` 直接崩；旧脚本靠纯标准库 csv 绕开，新代码不能再绕。`pyfixest` 用于高维固定效应回归（1493 家 × 25 月的 FE 用 statsmodels 会爆内存）。
**创新点** —
**预期结果** 打印 `env OK True`
**产出** `.venv-fyp/`
**自检** 上述 import 全部成功；`torch.backends.mps.is_available()` 为 True

#### STEP 01 · 数据获取（零凭证级联）
**怎么做**
```python
SOURCES = [
  ("hf", "Dricz/515k-Hotel-Reviews-In-Europe", "Hotel_Reviews.csv"),
  ("hf", "enelpol/booking_com_reviews", None),
  ("kaggle", "jiashenliu/515k-hotel-reviews-data-in-europe", None),  # 仅当 ~/.kaggle/kaggle.json 存在
]
# 逐个尝试，第一个成功即停；记录实际来源到 facts.json["data_source"]
```
D2（HotelRec）：`git clone https://github.com/Diego999/HotelRec` 取其下载脚本，**只抽 6 个欧洲城市 + 3 个北美城市**，目标 20–50 万条，超过即停。
D3：直接读本地 `data/booking_reviews copy.csv` 与 `data/processed/hotels_all.csv`。
**为什么** HF 镜像是公开的、无需任何账号，这是把"人类触点"归零的关键。级联设计保证单点失效不阻塞。
**创新点** —
**预期结果** D1 约 515,738 行 × 17 列；D2 20–50 万行；D3 26,675 行
**产出** `data/raw/{d1,d2,d3}/`
**自检** 决策点 **D1**

#### STEP 02 · 完整性校验与数据卡
**怎么做** 检查列名、行数、缺失率、日期范围、城市分布；生成 `outputs/steps/STEP_02/datacard.md`。
**关键检验（决策点 D2，必须在 Day 0 做掉）**：
```
每家酒店在数据集中的评论数 n_h  vs  该酒店的 Total_Number_of_Reviews N_h
① 画 n_h 的分布 → 是否存在硬性上限（如都卡在某个整数）→ 判断是否截断抓取
② 算 ratio_h = n_h / N_h 的分布 → 若近似常数，说明抽样率恒定
③ 按月画 n_h 的时间分布 → 是否平滑（截断通常表现为只保留最近 K 条）
```
**为什么** 如果这个数据集是"每家只抓最近 K 条"，那么"评论到达数"就是被删失的，需求代理直接报废——**这是整个因果设计的地基，必须最先验证**，不能等到 Day 6 才发现。
**创新点** 这个检验本身值得写进论文的数据章节：**几乎所有用这个数据集的论文都没检查过抽样机制。**
**预期结果** ratio 分布近似恒定 → 用**竞争集内份额**做需求代理（份额对恒定抽样率免疫，这是关键的设计保险）
**产出** `datacard.md`, `fig_sampling_check.png`
**自检** 决策点 D2；无论结果如何都记进 `decisions.md`

---

### 阶段 1 · 测量层（★ 创新②所在）

#### STEP 03 · D1 解析与规范化
**怎么做** `Hotel_Address` 尾部匹配 6 个国家/城市名 → `city`, `country`；`Review_Date`（MM/DD/YYYY）→ datetime → `year_month`；`lat/lng` 缺失的（约 17 家）用 `Hotel_Address` 走一次 Nominatim 反查（复用 `data/scraped/geocode_cache.json` 的缓存模式，1 req/s）；`hotel_id = "d1:" + sha1(Hotel_Name+Hotel_Address)[:12]`。
**为什么** 三个数据集必须归一到同一 schema，否则后面每一步都要写分支。
**创新点** —
**预期结果** 1,493 家；6 城市（Amsterdam / Barcelona / London / Milan / Paris / Vienna）；坐标覆盖 100%
**产出** `data/processed/d1_hotels.parquet`, `d1_reviews.parquet`
**自检** 每城市酒店数 ≥ 100；日期范围约 2015-08 → 2017-08

#### STEP 04 · Tags 解析
**怎么做** `Tags` 是 Python list 的字符串 → `ast.literal_eval`；用正则分类到五类：
`trip_type`（Leisure/Business）、`party_type`（Solo/Couple/Family/Group）、`room_type`（自由文本，取 top-30 归并）、`nights`（"Stayed N nights"）、`device`（Submitted from a mobile device）。
**为什么** 这五类构成"需求组成向量"（竞争集的定义维度之一）和"客群构成协变量"（去混杂的自变量）。**同一份特征在论文里承担两个角色**。
**创新点** 现有用该数据集的工作几乎都把 Tags 当噪声丢掉；我们把它变成**市场结构的观测量**。
**预期结果** trip_type 覆盖 >90%；party_type 覆盖 >85%
**产出** `d1_reviews.parquet` 增列
**自检** 各字段缺失率 < 20%

#### STEP 05 · 文本清洗与句子切分
**怎么做** 过滤字面量 `"No Negative"` / `"No Positive"` / `"Nothing"`（大小写、前后空格变体全覆盖）；对 `Positive_Review` 与 `Negative_Review` 分别做句子切分（简单规则切分即可，不用 spaCy 以省内存）；产出长表 `(review_id, hotel_id, year_month, field∈{pos,neg}, sent_idx, sentence)`。**分块处理，chunk=20000。**
**为什么** `"No Negative"` 是该数据集最经典的坑——不过滤会把它当成一句真实的负面评论，污染所有 aspect 统计。
**创新点** —
**预期结果** 约 150–250 万句；pos:neg 句子比约 1.5–2.5 : 1
**产出** `d1_sentences.parquet`（float16 友好的分块）
**自检** 无任何句子等于占位符；内存峰值 < 8 GB

#### STEP 06 · Aspect 本体
**怎么做** `conf/aspects.yaml` 定义 8 个 aspect：`location, cleanliness, food_breakfast, service_staff, noise_sleep, room_facilities, value_for_money, wifi_tech`。每个给 15–25 个种子短语（不是单词，是短语，如 "close to the station"）。用 SBERT 对种子短语编码求均值 → **aspect 原型向量**。再用语料自动扩展：取与原型最相似的 200 个高频 n-gram，人工规则过滤停用词后并入种子集，重算原型（**自举一轮即可，避免语义漂移**）。
**为什么** 固定 aspect 集是全流程一致性的前提；原型向量法比关键词匹配召回高得多，且不需要训练。
**创新点** 用语料自举扩展种子集，避免"研究者拍脑袋定关键词"的常见批评。
**预期结果** 每个 aspect 最终 60–120 个短语
**产出** `conf/aspects.yaml`（自动更新）, `data/processed/aspect_prototypes.npy`

#### STEP 07 · Aspect 检测器（三路并行）★
**怎么做** 对每个句子，三个**互相独立**的检测器各输出一个 8 维 0/1 多标签：
```
A. 词表法    : 种子短语精确/模糊匹配
B. 原型法    : SBERT(all-MiniLM-L6-v2) 余弦 ≥ τ（τ 由 STEP 08 校准）
C. 零样本 NLI: MoritzLaurer/deberta-v3-base-zeroshot-v2.0，假设模板
               "This sentence is about the hotel's {aspect}."
最终标签 = 三者多数投票（≥2 票）
极性       = 该句所属字段（pos → +1, neg → −1）★ 不需要任何情感模型
```
在 MPS 上批处理，`batch_size=256`，embedding 存 `float16`。
**为什么** 极性由字段归属决定，所以任务从"ABSA（抽取+极性+配对）"退化为"aspect 多标签检测"，
不需要标注数据、不需要微调、不需要 GPU 集群。三路投票用来在**没有人工标注的情况下**获得可报告的可靠性指标。
**创新点 ★★** 这是全项目最重要的工程洞见：**数据集的字段结构本身提供了极性监督**（structural supervision）。
论文里要单独一段写它，因为它同时回答了"为什么此前无人做这件事"——别人用的是不分列的评论数据。
**预期结果** 约 150–250 万句 × 8 aspect；总耗时 MPS 上约 4–8 小时；
mention 率排序大致为 location > room > service > cleanliness > food > noise > value > wifi
**产出** `data/processed/sentence_aspects.parquet`
**自检** 三路投票的两两一致率均 > 0.55

#### STEP 08 · 三重自动验证（替代人工标注）★★
**怎么做**
```
验证一 · 结构真值（polarity）
  额外跑一个通用情感模型，与"字段归属"比对；
  报告 agreement。字段是真值，模型是被检验对象。
验证二 · 跨检测器可靠性
  三路检测器之间的 Krippendorff α（多标签，MASI 距离）→ 决策点 D3
验证三 · 外部锚定（最强）
  在 D2 (HotelRec) 上跑同一套检测器 → 得到每家酒店的 aspect 情感；
  与 TripAdvisor **用户自己打的 aspect 子评分**（service/cleanliness/value/location/sleep/rooms）
  算 Spearman ρ（酒店层面）→ 决策点 D4
```
**为什么** 这三条合起来在**不做任何人工标注**的前提下，给出了比 500 句自标注更强的证据：
- 验证一用的是数据结构给的真值；
- 验证二是标准的标注者间信度（把三个算法当三个标注者）；
- 验证三用的是**数万名真实用户自己打的 aspect 分数**——这是独立的人类真值，规模比 500 句大三个数量级。
**创新点 ★★** "无标注的 aspect 抽取验证协议"。审稿人对"你们的抽取准不准"的质疑，被三条互相独立的证据同时回答。
**预期结果** 验证一 agreement ≈ 0.80–0.90；验证二 α ≈ 0.60–0.75；验证三 ρ 在 cleanliness/service/location 上 0.40–0.60，value/noise 上较低
**产出** `outputs/steps/STEP_08/validation.json`, `fig_validation.png`
**自检** 决策点 D3、D4

#### STEP 09 · 月度面板构建
**怎么做** 聚合到 `(hotel_id, year_month, aspect)`：
```
mention_count_pos, mention_count_neg, n_reviews, n_sentences
raw_net[h,k,t] = (pos − neg) / (pos + neg)              # 未去混杂
mention_rate[h,k,t] = (pos + neg) / n_sentences
n_arrivals[h,t] = 该月评论数                            # 需求代理的原料
```
**用月度不用季度**：D1 只覆盖约 25 个月，按季度只有 8 期，扣掉基线窗和事件后窗几乎无剩余。
**为什么** 面板是后面全部因果分析的输入；时间粒度直接决定统计功效。
**创新点** —
**预期结果** 约 1,493 × 25 × 8 ≈ 30 万行（含空月）；有效（n_reviews ≥ 3）的 hotel-month 约 2 万
**产出** `data/processed/panel_monthly_raw.parquet`
**自检** 每城市每月至少 30 家酒店有有效观测

#### STEP 10 · 客群构成去混杂 ★（创新②）
**怎么做** 两步法（避免高维 FE 爆内存）：
```
第一步（提及层）：
  sent_polarity[i] = β' x_r[i] + FE(city × year_month × aspect) + ε[i]
  x_r = [国籍 one-hot(top30)+其他, trip_type, party_type, nights 桶, device, 该评论者历史评论数 log]
  用 pyfixest 吸收 FE；取残差 e[i]
第二步（酒店层）：
  q̃[h,k,t] = mean(e[i] | hotel=h, aspect=k, month=t)
  经验贝叶斯收缩：q[h,k,t] = (n·q̃ + κ·μ_{city,k,t}) / (n + κ)，κ = σ²_within / σ²_between
```
**为什么** 观测到的评论情感混杂了两件事：**这家店有多好** 与 **谁在住**。
一家酒店若客群从"家庭度假"转向"商务出差"，其"噪音"投诉会自然下降——这不是质量改善。
不去混杂，后面所有"质量提升"的因果效应都可能只是客群变化。
**创新点 ★★** 现有酒店评论挖掘文献**全部**直接平均情感。本步给出一个"去混杂质量指数"，
并且可以量化地报告：**去混杂后有多少比例的"改进事件"消失、竞争集排名的 Kendall τ 掉到多少**。
这本身就是对整个应用领域的方法学警告，可以独立成一节。
**预期结果** 客群协变量解释 5–15% 的情感方差；去混杂前后酒店-aspect 排名 Kendall τ ≈ 0.75–0.90；
约 10–25% 的表观"改进事件"在去混杂后消失
**产出** `data/processed/panel_monthly.parquet`（含 `q` 与 `raw_net` 两列，便于消融）
**自检** `q` 无 NaN；收缩后方差小于收缩前

---

### 阶段 2 · 竞争集（★ 创新③）

#### STEP 11 · 需求组成与文本画像
**怎么做** 每家酒店（**只用训练期 t ≤ T1 的评论**，避免时序泄漏）：
```
demand_mix[h] ∈ R^41 : trip(2) + party(4) + room top-10(10) + nights 桶(4) + 国籍 top-20(20) + 国籍熵(1)，L1 归一
text_profile[h] ∈ R^384 : 该店评论句 SBERT 向量均值
```
**为什么** 竞争者不是"地理上近的"，而是"抢同一批客人的"。客群构成是"同一批客人"最直接的观测量。
**创新点** 把 Hoberg & Phillips (JPE 2016) 的文本化市场划分思想迁移到服务业，并加入**客群构成**这一酒店业特有的信号。
**预期结果** 同城酒店的 demand_mix 余弦相似度分布应有明显方差（若几乎全为 1，说明特征无区分度，需回到 STEP 04 检查）
**产出** `data/processed/hotel_features.parquet`

#### STEP 12 · 价格档位代理
**怎么做** 用 **D3（比利时，321 家有真实价格）** 训练一个三分类器（低/中/高），特征 = 星级、property_type、到市中心距离、评论中价格感知词频、评论量、平均分；
在 D3 上做 5 折 CV 报 accuracy 与 Spearman ρ；迁移到 D1（D1 无价格）。
同时用 D3 已抓的 **三个日期快照**（2026-07-15/22/29）计算价格 **rank 的跨日 Spearman**，作为"价格位次比价格水平稳定"的实证支持。
**为什么** 竞争集需要价格档位，但 D1 没有价格。与其不用，不如用一个**可报告精度**的代理，并做敏感性分析。
**创新点** 用自采数据（D3）为公开数据（D1）补全缺失维度，并**量化这个补全的误差**——比"用星级凑合"诚实得多。
**预期结果** 三分类 accuracy 0.55–0.70；Spearman ρ 0.45–0.65；跨日 rank 稳定性 ρ > 0.9
**产出** `data/processed/price_tier_d1.parquet`, `outputs/steps/STEP_12/price_proxy.json`
**自检** 若 ρ < 0.5 → 自动把 `conf/compset.yaml` 的 `w_price = 0` 并记入 `decisions.md`（预注册的 R1 止损）

#### STEP 13 · 竞争集构建
**怎么做**
```
s(i,j) = w_geo·exp(−d_ij/τ) + w_dem·cos(dem_i,dem_j) + w_txt·cos(txt_i,txt_j) + w_pri·1[tier_i=tier_j]
约束   : 同城 ∧ d_ij ≤ r_max(h)，r_max(h) = min(3km, h 的第 15 近邻距离)
C(h)   = top-m 邻居
网格   : τ∈{300,600,1000}m × m∈{5,7,10} × w∈单纯形 20 个网格点 = 180 组
```
**为什么** 硬规则（"1km 内 + 同价位"）在数据上会碎成一堆无效小组（旧版就是这样，只剩 1 个有效簇）。
连续相似度 + top-m 保证**每家酒店都有竞争集**，且规模可控在业界惯例的 5–10 家。
**创新点** 竞争集从"研究者定义的启发式"变成"从数据学出来、且用 STEP 14/15 可证伪的构造"。
**预期结果** 1,493 家全部有竞争集；有效竞争集（去重后的独立集合）数百个 → 决策点 D5
**产出** `data/processed/compset_edges.parquet`, `compset_membership.parquet`（每组网格一份）

#### STEP 14 · T1 留出互预测力
**怎么做** 对每个留出属性 y ∈ {avg_score, 需求增长, price_tier}：
`ŷ_compset = mean(y | C(h))` vs `ŷ_random`（随机同城 m 家）vs `ŷ_geo`（最近 m 家）；报 R² 与 ΔR²。
**为什么** 这是"竞争集是不是一个有信息量的构造"的最基本检验，也是**选超参的依据**（选 ΔR² 最大的一组，而不是拍脑袋）。
**创新点** 用无监督的留出预测力做模型选择，避免"超参调到结果好看"的指控。
**预期结果** ΔR²(compset vs random) 在 0.05–0.20；compset 应优于纯地理
**产出** `outputs/tables/t1_holdout.csv`

#### STEP 15 · T2 需求溢出（核心证伪）★
**怎么做**
```
双向固定效应面板回归：
  Δshare[h,t] = β · mean(Δshare[j∈C(h)\h, t]) + α_h + γ_{city×t} + ε
对照：把 C(h) 换成随机同城集合，β 应不显著
若 β 显著为正 → 加更细的区域×时间 FE 吸收共同冲击后重估
```
**为什么** 真正的竞争者之间应有**替代关系**：同集某店需求异常上升时，同集其他店的份额应下降。
这是"我们的竞争集抓到了真实替代关系"的**硬证据**，远强于任何定性论证。
**创新点 ★★** 把"竞争集"这个通常只靠直觉论证的构造，做成一个**可以失败的统计检验**。
**预期结果** β 显著为负；随机对照不显著 → 决策点 D6
**产出** `outputs/tables/t2_spillover.csv`, `fig_compset_validation.png`

#### STEP 16 · 选参与冻结
**怎么做** 按 T1 的 ΔR² 选最优网格点；**冻结**竞争集，后续所有 STEP 只读不改；全网格结果留作稳健性。
**为什么** 冻结是防止"因果结果不好看就回去调竞争集"的纪律保证。
**创新点** —
**预期结果** `conf/compset.yaml` 写入最终超参并加锁标记
**产出** `data/processed/compset_FINAL.parquet`

---

### 阶段 3 · 因果

#### STEP 17 · 需求代理构建与验证
**怎么做**
```
share[h,t] = n_arrivals[h,t] / Σ_{j∈C(h)∪{h}} n_arrivals[j,t]
验证：① 与 Total_Number_of_Reviews 的截面相关
      ② 季节性是否合理（夏季高峰）
      ③ 用三个 outcome 交叉验证：share / n_arrivals / mean_rating
```
**为什么** 份额对"恒定抽样率"免疫（分子分母同比例缩放会抵消），这是应对 STEP 02 抽样风险的设计保险。
**创新点** —
**预期结果** share 的截面方差合理；季节性明显
**产出** `data/processed/panel_outcome.parquet`

#### STEP 18 · 处理定义（连续为主，二元为辅）
**怎么做**
```
连续处理（主）：Δq[h,k,t] = q[h,k,t] − mean(q[h,k,t−6:t−1])
二元处理（辅）：跃迁 = Δq > δ·σ_C[k] 且 t+1,t+2 保持；δ ∈ {0.5,0.75,1.0}
```
**为什么** 二元跃迁事件预计只有几百个，功效不足；连续处理把每个 hotel-aspect-month 都变成观测，样本量放大两个数量级。
二元版本保留用于 event study（图更好看、更好懂）。
**创新点** —
**预期结果** 连续处理样本 ~2 万 hotel-month × 8 aspect；二元事件 200–600 个
**产出** `data/processed/treatment.parquet`

#### STEP 19 · 主因果估计
**怎么做**
```
Δshare[h,t+1..t+3] = θ·Δq[h,k,t] + Controls + α_h + γ_{city×t} + ε   （聚类到 hotel）
同时对三个 outcome 各跑一次；对 8 个 aspect 分别跑一次（异质性）
```
**为什么** 这是 L2 的主结果：**改进 aspect 是否真的带来需求/评分提升**。
**创新点** 对照组是"同竞争集内未改进的同行"，而不是全样本——竞争集在这里第一次承担**统计角色**。
**预期结果** θ > 0 且显著；cleanliness / service 的效应强于 wifi / value → 决策点 D7
**产出** `outputs/tables/main_did.csv`

#### STEP 20 · Event study
**怎么做** 二元处理，估 τ ∈ [−6, +6] 的动态系数，画图；对 τ ∈ [−6,−1] 做联合 F 检验。
**为什么** **无预趋势是因果主张的准入证**。这张图审稿人一定会看。
**创新点** —
**预期结果** τ<0 系数围绕 0 且联合检验不显著；τ≥0 逐步上升后平台 → 决策点 D8
**产出** `fig_event_study.png`

#### STEP 21 · Placebo 套件
**怎么做** ① placebo-in-time（处理时点前移 4 期）② placebo-aspect（随机 aspect）③ placebo-unit（随机指派处理组）；各 500 次重抽样，画效应分布并标注真实效应位置。
**为什么** 三种 placebo 覆盖三种不同的伪相关来源。
**创新点** —
**预期结果** 真实效应落在 placebo 分布的极端尾部（经验 p < 0.05）
**产出** `fig_placebo.png`, `placebo.json`

#### STEP 22 · 交错处理估计器
**怎么做** Callaway & Sant'Anna (2021) 的 group-time ATT；与 TWFE 结果对比。
**为什么** 处理时点是交错的，TWFE 会产生负权重导致偏误——这是近年计量领域的标准批评，审稿人会问。
**创新点** —
**预期结果** CS 估计与 TWFE 同号，量级可能不同；若符号相反必须在论文里讨论
**产出** `outputs/tables/callaway_santanna.csv`

#### STEP 23 · 均值回归检验
**怎么做** Ashenfelter dip 检验：看处理前是否有异常下跌；再做条件于基线水平的匹配（把"从低位反弹"和"真实改进"分开）。
**为什么** 处理定义是"高于自身基线 δ 个标准差"，天然有均值回归风险。**这是最危险的一条审稿意见，必须提前打掉。**
**创新点** —
**预期结果** 无明显 dip；条件匹配后效应量下降但仍显著
**产出** `outputs/tables/mean_reversion.csv`

---

### 阶段 4 · 皇冠（★ 核心命题）

#### STEP 24 · Peer adoption 构建
**怎么做** `peer_adopt[h,k,t] = mean(Δq[j,k,t])`（连续版）与 `#{j∈C(h): j 在 t 期跃迁}`（计数版，用于画图）。
**为什么** 这是 performativity 的自变量。
**创新点** —
**预期结果** 计数版取值 0–m；分布右偏
**产出** `data/processed/peer.parquet`

#### STEP 25 · 二阶邻居 IV ★★（技术皇冠）
**怎么做**
```
先验证网络非传递性：计算竞争集图的聚类系数，报告 "存在大量 A–B–C 但 A–C 不相邻的三元组"
一阶段：peer_adopt[h,k,t] ~ Z[h,k,t−1] + α_h + γ_{city×t}
        Z = C(C(h)) \ (C(h) ∪ {h}) 的**滞后 aspect 赤字**均值
        （二阶邻居的历史赤字预测他们会改进，进而影响 h 的一阶竞争者，但不直接影响 h 的需求）
二阶段：Δshare[h,t+1..3] ~ θ·Δq_own + λ·(Δq_own × peer_adopt_hat) + ...
```
**为什么** 直接估同伴效应会撞上 Manski 的 reflection problem（我和同伴互相决定，线性均值模型不可识别）。
Bramoullé, Djebbari & Fortin (Econometrica 2009) 证明：**网络非传递时，二阶邻居的特征提供排除限制**。
**创新点 ★★★ 全篇最优雅的地方**：竞争集是**重叠且非传递**的（A 的竞争集含 B，B 的含 C，A 的不含 C），
这个条件不是我们凑出来的，是竞争集这个构造**天然满足**的。
于是同一个构造在论文里承担了三个角色：①可比市场定义 ②因果对照组 ③同伴效应的识别网络。
**一石三鸟——这是审稿人会记住的东西。**
**预期结果** 一阶段 F > 10（决策点 D10）；λ < 0 且显著（决策点 D9）
**产出** `outputs/tables/peer_iv.csv`

#### STEP 26 · ★ Figure 1
**怎么做**
```
主图 : x = 同集同期改进同一 aspect 的竞争者数量 (0,1,2,…,m)
       y = 该 aspect 改进对自身需求份额的估计效应 τ̂，带 95% CI（bootstrap 1000 次，按 hotel 聚类）
副图 : 随机"假竞争集"的同一条曲线 → 应为平线
标注 : 曲线穿过 y=0 的位置 = "回报被完全竞争掉的临界采纳数"
```
**为什么** 一张图定生死。读者读完 abstract 后 10 秒内要能相信核心命题。
**创新点 ★★★** 这张图是论文的核心证据，也是**首个在真实市场上测出的供给侧 performativity 曲线**。
**预期结果** 单调下降；在 peer≈3–5 处穿过 0
**产出** `paper/figs/fig1_performativity.pdf`

#### STEP 27 · 分半样本 IV（测量误差）
**怎么做** 把每个 (hotel, month) 的评论随机分两半，分别算 aspect 情感 → 同一潜在质量的两个独立测量 → 一半做另一半的工具变量；报告 naive 与校正后系数。
**为什么** 审稿人必问"你的处理变量是 NLP 抽出来的，有噪声，经典测量误差会把系数拉向 0"。
**创新点 ★★** 把经典测量误差校正用到**NLP 抽取量**上。这在 NLP-for-社科的论文里很少见，成本却几乎为零（只需重跑一次聚合）。
**预期结果** 校正后系数绝对值增大 10–40%
**产出** `outputs/tables/split_sample_iv.csv`

#### STEP 28 · Oster δ 边界
**怎么做** Oster (2019)：用加入协变量前后的系数变化与 R² 变化，计算"要使效应归零所需的未观测混杂强度 δ"。
**为什么** 回答"存在未观测混杂怎么办"最专业的方式不是辩解，而是**量化需要多强的混杂才能推翻结论**。
**创新点** —
**预期结果** δ > 1（即未观测混杂需比全部已观测协变量加起来还强，才能推翻结论）
**产出** `outputs/tables/oster_bounds.csv`

---

### 阶段 5 · 策略与推荐

#### STEP 29 · 处方策略与基线形式化
**怎么做**
```
ours(equilibrium-aware): argmax_{S⊆A, Σc(k)≤B}  Σ_{k∈S} [ θ̂_k + λ̂·E(peer_adopt_k) ]
基线①fix-worst        : 选 q 最低的 aspect
基线②fix-largest-gap  : 选与竞争集均值差距最大的 aspect
基线③most-mentioned   : 选差评提及最多的 aspect
基线④random / ⑤LLM 直接建议
成本 c(k) 用三组场景假设，全部报告
```
**为什么** 基线①②③正是业界 comp-set benchmarking 工具的实际做法——把它们**形式化成可评测的策略**，
才能证明"忽略 performativity 会导致误配"。
**创新点 ★★** 把商业实践写成可评测的算法基线，这是"我们的发现有实际后果"的落脚点。
**预期结果** ours 与基线的推荐重合率 40–70%（不重合的部分正是 performativity 造成的差异）
**产出** `outputs/tables/policy_overlap.csv`

#### STEP 30 · Off-policy 评测
**怎么做** 时序留出期回放；对每个实际发生改进的 (h,k)，用 IPS / SNIPS / Doubly-Robust 估计各策略的价值；bootstrap 95% CI。
**为什么** 我们不能真的让酒店去改进，只能用历史上实际发生的改进做离线评估——这是 RecSys 社区的标准工具。
**创新点** 把 off-policy evaluation 从"评估推荐给用户的物品"迁移到"评估推荐给供给方的干预"。
**预期结果** V(ours) 高于最优基线 10–30% → 决策点 D11
**产出** `outputs/tables/policy_value.csv`, `fig_policy_value.png`

#### STEP 31 · Tourist 侧排序实验
**怎么做**
```
标签（无泄漏）: 竞争集内的需求份额增量，转 5 档 graded relevance
切分          : 严格时序，T1=60% 分位，T2=80% 分位
模型          : LightGBM LambdaMART（group=竞争集）+ 线性加权基线
基线          : 全局评分排序 / 评分+价格 / 流行度 / ItemKNN / BPR-MF
消融          : ★ mask-reviews（aspect 特征全置零）
指标          : NDCG@{5,10}, MAP；按竞争集配对 Wilcoxon
```
**为什么** 两个作用：①让"双视角"成立 ②回应审稿人"这更像计量经济学论文，推荐系统的成分在哪"。
**创新点** 标签用**需求份额增量**而非评分，彻底避开"高评分=好酒店"的循环论证与标签泄漏。
**预期结果** NDCG@10 优于最强基线 3–8%；mask-reviews 消融下降明显
**产出** `outputs/tables/tourist_ranking.csv`
**自检** 泄漏自检：断言特征表不含标签窗数据；断言未使用数据集自带的全期 `Average_Score`

#### STEP 32 · 双视角耦合（H1）
**怎么做** 对留出期实际改进过 aspect 的酒店，比较其 Tourist 排序位次变化：ours 推荐组 vs 启发式推荐组；Mann-Whitney U。
**为什么** 这是论文里"双视角"这个词**唯一的硬证据**——把两个视角用一个可证伪的命题绑在一起。
**创新点 ★★** 多数"多视角"论文的两个视角只是并列展示；我们让它们互相**预测**。
**预期结果** ours 组位次提升显著更大
**产出** `outputs/tables/coupling_h1.csv`

---

### 阶段 6 · 稳健性

#### STEP 33 · 稳健性矩阵
**怎么做** 对 5 个维度做全网格并汇总成一张"稳健性曲面"：竞争集半径 × m × 权重 × δ 阈值 × 结果窗长度。
主结果的符号与显著性在多少比例的设定下保持不变 → 报一个"稳健性比例"。
**为什么** 报单点估计会被问"换个参数还成立吗"；报曲面直接堵死。
**创新点** 用"稳健性比例"这一个数字概括数百个设定，比堆附录表更有说服力。
**预期结果** ≥ 80% 的设定下主结论不变
**产出** `fig_robustness_surface.png`

#### STEP 34 · 第二面板复制（D3 比利时）
**怎么做** 在 D3（2018–2021，45 个月，822 家）上重跑 STEP 09→26 的核心链路；显式建模 COVID 断点（2020Q1）与时间固定效应。
**为什么** 跨市场复制是泛化性的唯一证据；同时 D3 跨 COVID，可作为"aspect 显著度冲击"的额外分析。
**创新点** D1 天然避开 COVID（2015–2017），D3 跨 COVID —— 两者对照本身构成一个自然实验：
**当外生冲击让所有人同时关注清洁度时，清洁度的个体回报是否下降？** 这是 performativity 命题的独立佐证。
**预期结果** 主效应同号；COVID 期间 cleanliness 的回报显著低于非 COVID 期
**产出** `outputs/tables/d3_replication.csv`

---

### 阶段 7 · 论文

#### STEP 35 · 图表定稿
**怎么做** 全部图输出 PDF 矢量、双栏宽（3.3 in）或通栏（7 in）、字号 ≥ 7pt、色盲安全配色、灰度可读；表格输出 booktabs LaTeX。
**为什么** 图表质量是审稿人对论文"档次"的第一印象来源，且几乎不花时间。
**创新点** —
**预期结果** 6 张图 + 6 张表
**产出** `paper/figs/*.pdf`, `paper/tables/*.tex`

#### STEP 36 · 事实库 ★★（防幻觉的关键设计）
**怎么做** 把所有 STEP 的 `metrics.json` 汇总成 `outputs/facts.json`，每个数字一个 key：
```json
{"n_reviews_d1": 515738, "n_hotels_d1": 1493, "krippendorff_alpha": 0.68,
 "did_theta": 0.041, "did_theta_se": 0.012, "peer_lambda": -0.017, ...}
```
论文正文只允许写 `\fact{did_theta}`，编译时由脚本替换为真实值；**任何未在 facts.json 中的数字直接编译失败**。
**为什么** 这是让"AI 写论文"变得安全的唯一办法——**结构上杜绝编造数字**。
**创新点 ★★** 这个机制本身值得在复现包 README 里说明，它是"AI 辅助研究"的一个可复用工程实践。
**预期结果** facts.json 约 150–300 个 key
**产出** `outputs/facts.json`, `paper/tools/substitute_facts.py`
**自检** 编译时扫描全文数字，凡不来自 facts.json 的报错

#### STEP 37 · 论文生成
**怎么做** 按 `PAPER_STRATEGY.md` Part 9 的五段式 Intro + `RESEARCH_MASTER_PLAN.md` 附录 B 的章节结构生成；
写作顺序强制为：**Figure 1 → Abstract（写 10 版择一）→ Introduction → Method → Experiments → Related Work → Conclusion**；
根据决策表的分支自动选择 Plan A/B/C 的标题与叙事。
**为什么** Abstract 先行能强制先想清楚命题；Related Work 后置能保证它服务于已确定的定位而不是泛泛综述。
**创新点** —
**预期结果** 正文符合 WWW 页数限制，引用 60–90 条
**产出** `paper/main.tex` + `paper/sections/*.tex`

#### STEP 38 · 对抗自审 ×3 轮
**怎么做** 每轮生成三份独立 review（角色分别为：IR/RecSys 审稿人、计量经济学审稿人、怀疑一切的审稿人），
按 WWW 评分表打分并写具体意见 → 逐条写 response → 改稿 → 下一轮。**三轮全部存档**。
每个角色的攻击清单预置于 `PAPER_STRATEGY.md` Part 10。
**为什么** 这是 token 最划算的用法：它模拟了真实审稿，且存档的 response 在 12 月 rebuttal 时可直接复用。
**创新点** —
**预期结果** 第三轮的三份 review 平均分应高于第一轮；未解决的意见全部转入 Limitations
**产出** `outputs/self_review/round{1,2,3}/`

#### STEP 39 · 复现包与终检
**怎么做** 整理匿名仓库（代码 + 派生数据 + aspect 本体 + 决策日志）；跑格式检查（页数、匿名化、引用格式、图字号）；
生成 `outputs/REPORT.md` 最终版（全流程的【怎么做/为什么/结果】叙述）。
**为什么** 复现包本身是接收理由之一；REPORT.md 是给人验收用的。
**创新点** —
**预期结果** 从零复现的完整命令序列可跑通
**产出** `paper/main.pdf`, 匿名仓库, `outputs/REPORT.md`

---

## Part 4 · 编排：如何真的连续跑 10 天

**怎么做**
```python
# run.py —— 状态机驱动
STEPS = [("STEP_00", step00_env), ("STEP_01", step01_fetch), ...]
state = json.load("state.json") if exists else {"done": [], "plan": None}
for name, fn in STEPS:
    if name in state["done"]: continue
    try:
        metrics = fn(cfg)                       # 每个 STEP 是一个纯函数
        write(f"outputs/steps/{name}/metrics.json", metrics)
        apply_decision_rules(name, metrics, state)   # Part 2 的决策表
        append_report(name, metrics)                 # 自动写 REPORT.md
        state["done"].append(name); save(state)
    except Exception as e:
        log_failure(name, e); apply_fallback(name, state); save(state)
        continue   # 不中断整个流程
write("outputs/NEXT.md", next_action(state))
```
**运行方式**：长任务（STEP 07 的 embedding、STEP 33 的网格）用普通 `python run.py --from STEP_XX` 在后台跑，
Agent 只负责写代码、读 `metrics.json`、决定下一步。**这样既连续又不消耗订阅额度。**

**断点续跑**：任何时候中断，重跑 `python run.py` 会从 `state.json` 的下一个 STEP 继续。
Agent 换会话时先读 `outputs/NEXT.md`。

---

## Part 5 · 自动降级表（预注册，Agent 不需要判断）

| 失败情形 | 自动动作 |
|---|---|
| HF 镜像不可用 | 依次试第二镜像 → Kaggle（若有凭证）→ 仅用 D3（缩小 scope，论文改投 CIKM short） |
| 抽样被截断（D2 不过） | 需求代理只用**份额**，并在 Limitations 明写；不改其他 |
| aspect 一致性 α < 0.6 | 缩到 5 个 aspect（location/cleanliness/service/room/value）重跑 STEP 07–10 |
| 有效竞争集 < 50 | 半径网格上限放宽到 3 km，m 放宽到 12，重跑 STEP 13 |
| T2 不显著 | 竞争集降级为方法组件；论文重心移到因果；标题不变 |
| 预趋势显著 | 改用 Callaway–Sant'Anna；仍不过 → 主张降级为"预测性关联"，全文措辞自动替换 |
| 一阶段 F < 10 | 只报 OLS 交互项 + 明写弱工具限制；Figure 1 改为 OLS 版本 |
| peer 交互项不显著 | **切 Plan B**：标题/摘要/Intro 自动改写为"检验理论 → 零结果"叙事 |
| 主效应也不显著 | **切 Plan C**：标题/摘要/Intro 自动改写为"测量论文 + benchmark" |
| 任一 STEP 崩溃 | 记录后跳过，继续下一个；终检时在 REPORT.md 顶部列出所有跳过项 |

---

## Part 6 · 十天日程

| Day | STEP | 主要产出 |
|---|---|---|
| 0 | 00–02 | 环境、三份数据、数据卡、抽样检验 |
| 1 | 03–10 | 句子表、aspect 检测、三重验证、**去混杂质量面板** |
| 2 | 11–16 | 竞争集 + T1/T2 证伪 + 冻结 |
| 3 | 17–21 | 需求代理、处理定义、主 DiD、event study、placebo |
| 4 | 22–23 | Callaway–Sant'Anna、均值回归检验 |
| 5 | 24–26 | peer adoption、**二阶邻居 IV**、**Figure 1** |
| 6 | 27–28 | 分半 IV、Oster 边界 |
| 7 | 29–32 | 处方策略、off-policy 评测、Tourist 排序、耦合检验 |
| 8 | 33–34 | 稳健性曲面、D3 复制 |
| 9 | 35–37 | 图表定稿、事实库、论文全文 |
| 10 | 38–39 | 三轮对抗自审、复现包、终检 |

> 与 `SPRINT_44D.md` 的关系：本规范是那个 44 天日历里 **Day 1–10 的加速版**。
> 10 天跑完后剩下的 34 天全部用于：补实验、加深 Related Work、外部读者反馈、以及（若时间允许）加 Yelp 第二 vertical。

---

## Part 7 · 最终交付物

- [ ] `data/processed/*.parquet` —— 完整的派生数据库（句子级 aspect、月度去混杂质量面板、竞争集图、处理与结果面板）
- [ ] `src/**` —— 全部代码，`python run.py` 一键从零复现
- [ ] `outputs/facts.json` —— 论文中每个数字的唯一来源
- [ ] `outputs/REPORT.md` —— 全流程【怎么做/为什么/结果】自动叙述（**验收时读这一份**）
- [ ] `outputs/decisions.md` —— 所有自动决策与降级记录（直接转成论文 Limitations）
- [ ] `paper/main.pdf` —— 完整论文，Plan A/B/C 三选一
- [ ] `outputs/self_review/` —— 三轮对抗审稿与 response（rebuttal 直接复用）
