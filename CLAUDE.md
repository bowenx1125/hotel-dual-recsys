# CLAUDE.md · 项目 Agent 守则

> **本文件是 Claude Code 每次启动的入口。先读完这份，再读别的。**
> 项目：双视角酒店推荐系统（Tourist + Manager），目标 RecSys 2027 / CIKM 2027。
> 作者：徐伯闻 Bowen XU（BNBU，AI 专业，学号 2330034059）。导师：Dr. Sunny Jeong。

---

## 1 · 权威文档（按需读，不要一次全读）

| 文件 | 什么时候读 |
|---|---|
| **`RESEARCH_MASTER_PLAN.md`** | 开始任何 Stage 前，读对应章节。这是**唯一权威研究蓝图** |
| **`CODE_PLAN.md`** | 写代码前，读对应 Stage 的任务与 Gate |
| **`AUTORUN_SPEC.md`** | **执行主文件**。40 个 STEP 的全自动规范（每步含 怎么做/为什么/创新/预期结果）+ 预注册决策表 + 自动降级表。Agent 干活时读这一份 |
| **`SPRINT_44D.md`** | **当前主线**。44 天冲刺 WWW 2027（摘要 2026-10-11 / 全文 2026-10-18），逐日计划 + Plan A/B/C |
| **`PAPER_STRATEGY.md`** | 想清楚论文命题时读。顶会强度版本的核心论证（performativity）与写作蓝图 |
| `BG.md` / `RESEARCH_PLAN.md` / `SCRAPING_SPEC.md` | **历史文档，已被上面几份取代**。只在追溯"当初为什么这么做"时读 |

---

## 2 · 一句话讲清这个项目在做什么

用一套**共享的、竞争集相对的酒店表征**，同时服务两个视角：
- **Tourist**：在预算档位内选最优酒店（排序任务）
- **Manager**：给出经**因果验证**的改进处方（"把清洁度提到竞争集第 30 百分位，预计评分 +0.18 [0.07, 0.29]"）

**核心创新不是"做了个系统"，而是**：把「本地竞争集」同时用作产品意义上的可比市场**和**统计意义上的匹配对照组，从而让经理侧的建议第一次变得**可验证**。

**当前所处位置**：进入 **44 天冲刺**（`SPRINT_44D.md`），目标 WWW 2027 全文截稿 2026-10-18。
最关键的单一里程碑是 **Day 7（2026-09-11）画出粗糙版 Figure 1** —— 那是 Plan A/B/C 的分叉点。
长期工程计划（`CODE_PLAN.md` 的 S0–S6）在冲刺结束后恢复。

---

## 3 · 环境（当前是坏的，先修）

`python3`（Anaconda 3.12.4）里 **numpy 2.4.6 与 pandas/sklearn/pyarrow 二进制不兼容，import 直接崩**。旧脚本靠纯标准库 `csv` 绕开——**新代码不要再绕**。

```bash
source .venv-fyp/bin/activate     # 若不存在，按 CODE_PLAN.md §0.1 建
python -c "import numpy,pandas,sklearn,lightgbm,statsmodels; print('env OK')"
```

- `.venv-absa/`：旧的 ABSA 环境（只有 transformers 系），S2 之前保留
- `models/absa/`：本地 `yangheng/deberta-v3-base-absa` 权重。**HF 在线下载器在本机会卡死**，脚本必须设 `HF_HUB_OFFLINE=1` 并走本地路径

---

## 4 · 工作模式（重要：省订阅额度）

- **长时间任务由用户自己用 `python` 跑**：爬虫、LoRA 微调、全量推理、大规模 DiD。
  Agent 的职责是**写好脚本 + 打印清晰进度 + 支持断点续跑**，然后告诉用户怎么跑。
- **Agent 的额度只花在**：写代码、改代码、调 bug、分析结果、写论文。
- 脚本必须支持中断后重跑不污染结果（幂等），且要打印 `已完成/总数/失败数`。
- **不要**用 `claude -p` 程序化调用自己去跑批量任务。批量 LLM 标注用 **API key**，不用订阅额度。

---

## 5 · 每次开工的固定动作

1. 读 `CODE_PLAN.md` 里当前 Stage 的任务和 **Gate**
2. 读 `outputs/decisions.md`（历史上偏离计划的决定，避免重复踩坑）
3. 干活
4. **跑该 Stage 的 Gate 检查**，把结果写进 `outputs/decisions.md`
5. Gate 不过 → 执行 `RESEARCH_MASTER_PLAN.md` Part 8 里对应的止损方案，**不要硬推**

---

## 6 · 编码约定

- 中文注释 OK，变量名/函数名用英文
- **中间产物一律 parquet**，不用 CSV（浮点精度 + 类型丢失）
- 写盘前必须 `schema.validate(df, NAME)`，列名/类型不符直接报错退出
- `hotel_id` 全局格式：`f"{dataset}:{sha1(原始主键)[:12]}"`
- 每个脚本 `python -m src.xxx.yyy --config conf/config.yaml` 独立可运行
- 随机种子统一从 `conf/config.yaml` 读（`seed: 42`）
- 正式实验**不在 notebook 里做**；notebook 只探索，结论回落到脚本

---

## 7 · 研究纪律（比代码规范更重要）

1. **时序切分，永远不要随机切分。** 这是评论数据，随机切分 = 用未来预测过去。
2. **结果好的第一嫌疑是泄漏。** 任何"哇效果很好"的时刻，先跑泄漏自检 pytest。
   - 特别注意：D1 的 `Average_Score` 是**全期**平均分，含未来信息，**不能直接当特征**，必须用特征窗重算。
3. **LLM 只做文本化，不做数值。** Manager 侧的所有数字来自结构化估计，LLM 只负责翻译成人话；输出后要正则校验每个数字都能在输入 dict 里找到。
4. **负结果也要如实报。** 比如 mask-reviews 消融如果没下降，就写进论文——这本身回应了 SIGIR'20 对评论推荐的批评，是有价值的。
5. **每个"我们的方法更好"的主张，都要配一个可证伪的检验。** 竞争集有 T1/T2，因果有 event study + placebo，处方有 Policy Value，双视角有 H1。
6. 引用文献前**必须核对原文**，不要照抄 `RESEARCH_MASTER_PLAN.md` Part 9 的措辞（那是起始清单，不是已核实的引用）。

---

## 8 · 数据与合规红线

- 爬虫：3–8s 随机延迟、遵守 robots.txt、原始 HTML 落盘可复现、**绝不绕过验证码或任何 bot 检测**。遇到验证码就记为失败走降级方案。
- 只抓研究必需的酒店级属性，不抓个人数据。
- **任何凭证/API key 绝不写进代码或提交**，走 `.env` + `python-dotenv`，`.env` 进 `.gitignore`。
- **不提交**：`data/raw/`、`.venv*`、模型权重、`.env`
- **要提交**：`data/annotations/`（人工标注 gold set，这是论文资产）、`conf/`、`src/`、`outputs/tables/`

---

## 9 · 当前目录里的历史资产（别重复造）

| 路径 | 是什么 | 还能用吗 |
|---|---|---|
| `data/booking_reviews copy.csv` | 26,675 条比利时评论（2018–2021） | ✅ 归一化成 D3 |
| `data/processed/hotels_all.csv` | 822 家爬取结果（745 坐标 / 321 价格 / 529 星级） | ✅ D3 + 价格代理模型的训练集 |
| `data/scraped/html/*.gz` | 每家的原始 HTML 存档 | ✅ 可重解析补字段，不用重爬 |
| `data/processed/compsets.csv` | 旧竞争集 MVP（**只有 34 家、1 个有效地理簇**） | ❌ 已知失效，S1 重建 |
| `data/processed/aspect_features.csv` | 旧 ABSA MVP（24 家酒店） | ❌ S2 重建 |
| `src/scrape/*.py` | 爬虫（Playwright，可用） | ✅ 需要补爬时复用 |
| `src/compset/build_compsets.py` | 纯 Python 手写 DBSCAN+haversine（因环境坏才手写） | ⚠️ 环境修好后改用 sklearn |
| `figures/*.png`, `build_thesis.js` | Partial Thesis 的图与生成脚本 | ✅ 写作阶段复用 |
| `FYP1_Partial_Thesis.docx` | 已交的 partial thesis（5,589 词） | ✅ 论文 Introduction/动机素材 |

**本机已知环境坑**：macOS 26.4 beta → brew 装不了 LibreOffice；Word 的 AppleScript 桥不稳。docx 渲染 QA 路径：`pandoc docx→html` + Chrome `--headless=new --screenshot`。

---

## 10 · 沟通约定

- 用户用中文，回复用中文，技术术语保留英文
- 报告实验结果时**给数字，不给形容词**（"NDCG@10 = 0.412 vs 基线 0.387，Wilcoxon p=0.03"，不是"效果不错"）
- Gate 没过就直说没过，并给出触发了哪条止损方案
