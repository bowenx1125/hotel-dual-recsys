# 44 天冲刺计划 · 从零到一篇可投 A* 的论文

> 配套 `PAPER_STRATEGY.md`（命题与论证）、`CODE_PLAN.md`（长期工程）。
> 本文件只回答一件事：**接下来 44 天，每天做什么，才能在 2026-10-18 交出一篇完整论文。**
> 撰写日期：2026-09-04

---

## Part 0 · 你的「一个月」正好撞上一个 A* 截稿

查了一圈，你要的时间窗里只有一个真正的顶会截稿，而且卡得刚刚好：

| | 日期 | 距今 |
|---|---|---|
| **WWW 2027（The Web Conference, Dublin, CCF A / CORE A\*）摘要注册** | **2026-10-11** | **37 天** |
| **WWW 2027 全文提交** | **2026-10-18** | **44 天** |
| 通知 | 2026-12-10 | — |
| Rebuttal | 2026-12-12 ~ 12-19 | — |

后备（不用改主线，同一篇文章顺延即可）：
- SIGIR 2027：2027-01-23
- KDD 2027 第二轮：约 2027-02
- RecSys 2027：2027-04-25

### 关于「一个月解决 paper」的诚实定义

**1 个月能达成的目标不是「被接收」，是「有一篇完整的、够格投 A* 的论文存在」。**
WWW 的接收率约 18%，一篇 7 周做出来的本科 FYP 论文大概率被拒。但是：

- 被拒的成本几乎为零，而**换回三份 A* 审稿意见**，这是花钱买不到的东西；
- 12 月 10 日出结果，正好留出时间按审稿意见改，投 SIGIR(1月) 或 RecSys(4月)；
- **最重要的是：截稿日会强迫工作真的发生。** 没有硬截稿的研究计划，八个月后通常还停在 Phase 1。

所以本计划的定位是：**用 44 天把论文的骨头全部长出来，然后用审稿意见长肉。**

---

## Part 1 · 「多篇顶会合体」到底是什么意思

先破一个误解：**顶会论文不是把几篇论文的方法拼在一起。** 拼接式论文审稿人一眼就能看出来，
典型评语是 "the contributions feel like a collection of existing techniques applied to a new dataset"。

真正的做法是：**从不同社区借「承重构件」，每个构件撑住一个具体的主张，抽掉它主张就塌。**
新颖性来自 (a) 这个组合此前无人搭过，(b) 组合中至少有 1–2 个是你自己的构件。

### 1.1 我们这篇的承重结构图

```
主张 L3：处方式推荐是 performative 的（回报随同集竞争者同向改进而衰减）
  │
  ├─ 承重① 因果效应的识别设计
  │     ← Proserpio & Zervas, Marketing Science 2017
  │       （评论平台上的 DiD：用同店在另一平台的走势做对照）
  │       我们的改造：对照组换成「同竞争集内未改进的同行」
  │
  ├─ 承重② 同伴效应的可识别性（否则撞 Manski reflection problem）
  │     ← Bramoullé, Djebbari & Fortin, Econometrica 2009
  │       （网络的非传递性提供排除限制 → 二阶邻居可做工具变量）
  │       我们的改造：竞争集天然重叠且非传递，这个条件白送
  │
  ├─ 承重③ 竞争者集合怎么定义
  │     ← Hoberg & Phillips, Journal of Political Economy 2016（TNIC）
  │       （不用行业代码，用产品文本相似度定义竞争者）
  │       我们的改造：地理 + 客群构成 + 评论文本画像 + 价格档
  │
  ├─ 承重④ 可观测的「内容向量」 ★ 我们自己的巧思①
  │     Booking 评论天然分列 Positive_Review / Negative_Review
  │     → 极性免费，ABSA 退化为 aspect 检测
  │     → 这是"为什么此前没人做"的技术答案（详见 Part 2）
  │
  ├─ 承重⑤ 质量 ≠ 情感 ★ 我们自己的巧思②
  │     客群构成去混杂：s = q + γ'x_reviewer + δ_time + ε
  │
  └─ 理论假说的来源（我们要检验的对象）
        ← Perdomo et al., ICML 2020（performative prediction）
        ← Jagadeesan, Garg & Steinhardt, NeurIPS 2023（supply-side equilibria）
        ← Ben-Porat & Tennenholtz, NeurIPS 2018
        这三篇全是理论/仿真。我们是第一次拿真实市场数据检验它们。

主张 L4：忽略 L3 的处方策略被系统性误配
  ├─ 承重⑥ 离线策略评测 ← IPS / SNIPS / DR（Gilotte et al., WSDM 2018）
  └─ 承重⑦ 描述性基线的形式化 ★ 我们自己的巧思③
        把业界工具（STR / TrustYou 式 comp-set benchmarking）写成
        "fix-worst / fix-largest-gap / most-mentioned" 三条可评测的策略

防御工事（对应审稿人的必问）
  ├─ 抽取噪声 → 分半样本 IV ★ 我们自己的巧思④（把经典 ME 校正用到 NLP 抽取量上）
  ├─ 未观测混杂 → Oster (2019) δ 边界
  ├─ 交错处理下 TWFE 有偏 → Callaway & Sant'Anna (2021)
  ├─ 均值回归 → Ashenfelter dip 检验 + 条件于基线水平的匹配
  └─ "评论其实没用" → Sachdeva & McAuley, SIGIR 2020 的 mask-review 消融
```

### 1.2 检验「是不是真承重」的方法

对每一个借来的构件，问一句：**抽掉它，哪个主张会塌？**
答不上来的，就是装饰品，**从论文里删掉**。装饰性引用是审稿人判断作者水平的第一信号。

| 构件 | 抽掉会塌的主张 |
|---|---|
| Bramoullé et al. | L3 完全不成立（peer effect 不可识别） |
| Hoberg & Phillips | L2 和 L3 都塌（没有竞争集就没有对照组也没有网络） |
| Pos/Neg 分列 | 整个测量层塌（回到有噪声的 ABSA，效应被噪声吃掉） |
| 去混杂 | L2 的效应可能只是客群变化 |
| 分半 IV | 不塌，但审稿人会说系数被低估 → 属于防御工事 |
| Perdomo / Jagadeesan | 不塌，但论文失去"检验理论"的身份，退化为经验发现 |

### 1.3 让它读起来不像拼接的五条写作纪律

1. **只用一个宿主社区的语言**。我们的宿主是 Web/RecSys。计量经济学的东西以「工具」身份引入，
   写成 "we adopt the identification strategy of X"，而不是摆出一副"我们也懂计量"的姿态。
2. **每个借来的构件配一句「为什么显而易见的替代方案不行」**。
   例："我们不用标准 TWFE，因为处理时点是交错的，会产生负权重（Callaway & Sant'Anna, 2021）。"
   这一句话的信息量比引三篇文献大。
3. **自己的巧思必须有可命名的名词短语**。我们的："prescription externality"（处方外部性）。
   审稿人复述你论文时会用这个词——没有名字的贡献不会被记住。
4. **介绍顺序按「问题倒逼」，不按「文献综述」**。
   ✗ "先讲 DiD，再讲 peer effect，再讲 comp set"
   ✓ "要估回报 → 需要对照组 → 竞争集给了对照组 → 但同伴也在动 → 撞上 reflection problem → 竞争集的非传递性正好解决它"
   **注意最后这个转折：同一个构造先解决了问题 A，又解决了问题 B。这种"一石二鸟"是论文优雅感的来源。**
5. **Related Work 不是列表，是「为什么这五条线索各自到不了我们的结论」**。每条一句话说清它停在哪。

---

## Part 2 · 让 44 天变得可行的关键突破

> 原计划里 ABSA（标注 + LoRA 微调 + 全量推理）要 3–4 周。44 天里放不下。
> 下面这个观察把它压缩到 3 天，而且**结果更可靠**。

### 2.1 Positive/Negative 分列 = 免费极性标签

515K Europe 数据集的每条评论有两个独立字段：`Positive_Review`（客人夸的）和 `Negative_Review`（客人骂的）。

```
"bathroom was quite dirty"  出现在 Negative_Review  →  aspect=cleanliness, polarity=NEG
"staff were incredibly kind" 出现在 Positive_Review  →  aspect=service,    polarity=POS
```

**极性由字段归属决定，不需要模型。** 于是：
- ABSA（难：aspect 抽取 + 极性分类 + 配对）→ **aspect 单标签检测**（易）
- 不需要 LoRA 微调、不需要 GPU、515K 条几小时跑完
- gold set 只需验证 aspect 检测，标注者一致率会很高，500 句足够
- **测量噪声大幅下降** → 这直接决定 L3 的效应能不能被检测出来（噪声会把系数打向 0）

**这就是「为什么此前没人做」的技术答案**，值得在论文的 Method 里明写一段。
它把一个"需要昂贵标注的测量问题"变成了"数据结构本身提供的自然标注"。

⚠️ **已知数据坑**：该数据集用字面量 `"No Negative"` / `"No Positive"` 表示空字段，必须先过滤，
否则会被当成真实文本。这是使用该数据集的经典错误，务必在 Day 2 处理掉。

### 2.2 用月度面板，不用季度

D1 覆盖约 2015-08 至 2017-08 ≈ **25 个月**。按季度只有 8 期，扣掉基线窗和事件后窗几乎没剩。
**改成月度面板：25 期。** 平均每家每月约 14 条评论，够算 aspect 指标。

### 2.3 主分析用连续处理（dose-response），不用二元处理

二元"跃迁"事件数量有限（估计 200–500 个）。改成连续处理：
每个 (hotel, aspect, month) 都有一个质量变化幅度，样本量瞬间放大两个数量级。
- **主结果**：连续处理 + 交互项（`Δq_own × Δq_peers`）
- **Figure 1**：按 peer 改进数量分箱呈现（更好看、更好懂）
- **稳健性**：二元处理 + event study（用来展示无预趋势）

---

## Part 3 · 六条并行工作流（Day 1 就全部启动）

**token 充裕、时间紧张时，最大的浪费是串行。** 下面六条流之间没有依赖，Day 1 全开：

| 流 | 内容 | 谁做 | 何时交付 |
|---|---|---|---|
| **W1 数据与面板** | D1 解析 → 月度面板 | Agent | Day 4 |
| **W2 测量** | aspect 检测 + gold set + 去混杂 | Agent + 人(标注) | Day 12 |
| **W3 竞争集** | 构建 + T1/T2 验证 | Agent | Day 10 |
| **W4 因果与 Figure 1** | DiD / event study / peer IV | Agent | Day 26 |
| **W5 基线与策略评测** | 复现基线 + Policy Value + Tourist 排序 | Agent | Day 30 |
| **W6 写作** | LaTeX 骨架 + Related Work + 图表模板 | Agent + 人 | **Day 1 就开始** |

> **W6 从 Day 1 开始是本计划最反直觉、也最重要的一条。**
> 常规做法是最后两周写作，结果 Related Work 潦草、图表粗糙——而这恰恰是审稿人判断"这是不是一篇 A 类论文"的第一印象来源。
> Related Work 和基线复现完全不依赖我们的实验结果，**它们没有理由排在最后**。

---

## Part 4 · 逐日计划

### 阶段 A · Day 1–7：贯穿性尖刺（Spike），产出粗糙版 Figure 1

> **核心原则：先把整条链路用最粗糙的方式跑通，再回头精修每个零件。**
> 绝不能是"先做完美的 ABSA → 再做完美的竞争集 → 最后才发现因果做不出来"。

| Day | 日期 | 动作 | 产出 |
|---|---|---|---|
| 1 | 09-05 | 修环境；下载 D1；**同时启动 W6**（LaTeX 骨架 + 开始读文献）；启动 W5（基线代码框架） | `env OK`；`paper/main.tex` 骨架 |
| 2 | 09-06 | D1 解析：地址→城市、Tags→出行类型/房型/停留、**过滤 "No Negative"/"No Positive"**、日期→月 | `reviews.parquet`, `hotels.parquet` |
| 3 | 09-07 | **仅用种子词**做 aspect 检测（8 个 aspect，不用模型）；构建月度面板 | `panel_monthly.parquet` |
| 4 | 09-08 | 竞争集 v0：只用地理 KNN（k=7，同城，≤1.5km） | `compset_v0.parquet` |
| 5 | 09-09 | 连续处理 DiD v0：`Δdemand_share ~ Δq_own + city×month FE` | 主效应初值 |
| 6 | 09-10 | **peer 交互项**：`Δq_own × Δq_peers`；画粗糙版 Figure 1 | `fig1_v0.png` |
| 7 | 09-11 | **★ GO / NO-GO 决策日**（见 Part 5） | 决定走 Plan A / B / C |

**Day 7 的判据**：`Δq_own × Δq_peers` 的交互项系数
- 显著为负 → **Plan A**（performativity 论文），全速推进
- 不显著但主效应显著 → **Plan B**（零结果论文，见 Part 5）
- 主效应也不显著 → **Plan C**（测量论文，见 Part 5）

### 阶段 B · Day 8–21：把每个零件做真

| Day | 动作 |
|---|---|
| 8–9 | **W2**：aspect 检测升级为 种子词 + SBERT 语义匹配 + LLM 复核；抽 500 句待标注 |
| 10–11 | **人工标注 500 句**（Bowen 自己做，约 4–5 小时/天 × 2）→ 报 F1 与 κ |
| 12–13 | **W2**：客群构成去混杂（`s = q + γ'x_r + δ_{k,t} + ε`，双向 FE）；报「去混杂后被推翻的改进事件比例」与 Kendall τ |
| 14–15 | **W3**：竞争集正式版（地理 + 客群构成 + 文本画像 + 价格档）；超参网格 |
| 16–17 | **W3**：T1 留出互预测力 + T2 需求溢出（含随机竞争集对照）；出验证表 |
| 18–19 | **W4**：正式 DiD + event study（±6 个月）+ placebo-in-time + placebo-aspect |
| 20–21 | **W4**：Callaway–Sant'Anna 交错处理估计；Ashenfelter dip 检验 |

**Day 21 Gate**：event study 的处理前系数不显著（无预趋势）；aspect 检测 F1 ≥ 0.75；有效竞争集 ≥ 50。

### 阶段 C · Day 22–32：识别皇冠 + 策略评测

| Day | 动作 |
|---|---|
| 22–24 | **W4**：二阶邻居 IV 估 peer effect（一阶段 F 统计量要报）；**Figure 1 正式版** |
| 25–26 | **W4**：分半样本 IV 处理测量误差；Oster δ 边界 |
| 27–28 | **W5**：处方策略 + 4 条描述性基线；IPS/SNIPS/DR 的 Policy Value |
| 29–30 | **W5**：Tourist 侧排序实验（LightGBM + 基线 + mask-review 消融）；双视角耦合检验 H1 |
| 31–32 | 稳健性矩阵全跑：竞争集半径 × m × 权重 × 窗口长度；D3（比利时）作第二面板复制 |

**Day 32 Gate**：所有主结果冻结，**此后只允许改文字和图，不许再改数字**。

### 阶段 D · Day 33–40：写作与对抗自审

| Day | 动作 |
|---|---|
| 33 | Figure 1–6 全部定稿（矢量图、双栏宽度、字号 ≥ 7pt）；所有表格生成 LaTeX |
| 34 | **Abstract 写 10 版**，选 1 版；Introduction 五段式初稿 |
| 35–36 | Method + Experiments 全文初稿 |
| 37 | **★ WWW 摘要注册截止（10-11）——今天必须提交标题与摘要** |
| 38 | **对抗自审第 1 轮**：agent 扮演 IR / 计量 / RecSys 三位审稿人各写一份 review → 逐条列 response |
| 39 | 按 review 改稿；补实验（只补能在 1 天内跑完的） |
| 40 | **对抗自审第 2 轮** → 改稿 |

### 阶段 E · Day 41–44：收尾

| Day | 动作 |
|---|---|
| 41 | **对抗自审第 3 轮**；Limitations 章节（不是道歉，是先发制人） |
| 42 | 外部读者（导师 + 1 位同学）通读；复现包整理；补充材料 |
| 43 | 格式检查（ACM 模板、页数、匿名化、引用格式）；全文朗读一遍抓语病 |
| 44 | **10-18 提交** |

---

## Part 5 · Plan A / B / C（Day 7 就决定，不要拖）

一个 44 天的冲刺**必须预先想好失败分支**，否则在 Day 25 发现主结果不成立时会全盘崩溃。

### Plan A —— peer 交互项显著为负
**标题**：*Prescriptive Recommendation is Performative: Returns to Provider Quality Investment under Competition*
**目标**：WWW 2027 → SIGIR 2027
按 Part 4 全速推进。

### Plan B —— 主效应显著、peer 效应不显著
**标题**：*Are Returns to Quality Competed Away? Testing Supply-Side Equilibrium Predictions in a Real Marketplace*
**卖点转移**：论文变成「**对一个纯理论文献的首次实证检验**」，而结论是**理论预测在本地服务市场不成立**，
并给出为什么的机制讨论（容量约束 / 改进的持久性 / 需求的地理黏性 / 消费者注意力有限）。
**零结果是可发的，前提是检验本身做得足够干净**——所以 Part 5 的防御工事一个都不能省。
**目标**：RecSys 2027 / CIKM 2027（A 类，比 WWW 更接受这类实证检验）

### Plan C —— 因果设计整体不成立（事件太少 / 预趋势严重）
**标题**：*Review Sentiment Is Not Quality: Guest-Mix Confounding in Hotel Review Mining*
**卖点转移**：变成**测量论文 + 资源论文**。核心发现是「现有酒店评论挖掘全部直接平均情感，
去混杂后 X% 的结论翻转」，配上竞争集 benchmark 释放。
**目标**：CIKM resource track / ECIR / SIGIR short

> 三个 Plan 共用 Day 1–13 的全部工作。**分叉只发生在 Day 14 之后**，所以前两周不存在浪费。

---

## Part 6 · 人和 Agent 的分工

**Bowen 本人必须亲自做的（不可外包）**：

| 事项 | 时间 | 为什么不能外包 |
|---|---|---|
| 500 句人工标注 | Day 10–11，约 9 小时 | 论文里"human annotation"这句话必须是真的 |
| Day 7 / 21 / 32 三个 Gate 的判断 | 各 1 小时 | 决定项目方向，agent 会倾向于报喜 |
| Abstract 与 Introduction 的最终定稿 | Day 34、41 | 这两节决定论文命运，必须是你自己的判断 |
| 通读全文并回答"我能为每句话辩护吗" | Day 43 | 你要在 rebuttal 里守这篇论文 |
| 和导师沟通 | 每周一次 | — |

**Agent 承担的（token 尽管烧）**：
数据处理、全部建模与统计、基线复现与调参、文献精读、Related Work 初稿、图表生成、
稳健性矩阵、对抗自审、格式与引用检查。

**并行策略**：六条工作流各开一个独立 agent 会话，各自有明确的输入输出契约（`src/common/schema.py`）。
每天固定一次同步：把六条流的进度汇总进 `outputs/daily_log.md`。

---

## Part 7 · 砍东西的顺序（一定会砍，提前决定）

进度落后时按此顺序砍，**从下往上砍**：

```
绝不能砍 ─────────────────────────────────
  1. D1 数据 + 月度面板
  2. aspect 检测 + 500 句 gold set
  3. 竞争集 + T2 需求溢出验证
  4. 连续处理 DiD + event study + placebo
  5. Figure 1（peer 交互项）
  6. Policy Value 评测
─────────────────────────────────────────
  7. 二阶邻居 IV              ← 落后 3 天砍这个（降级为"我们讨论了 reflection problem"）
  8. Tourist 侧排序实验        ← 落后 5 天砍（但会招来"推荐系统成分在哪"的批评）
  9. D3 比利时第二面板复制     ← 落后 7 天砍
 10. 分半 IV / Oster 边界      ← 落后 9 天砍（放进 rebuttal 备用）
 11. Yelp 第二 vertical        ← 本次冲刺**本来就不做**，留给 SIGIR 版本
 12. 均衡仿真                  ← 本次冲刺**本来就不做**
 13. 人工评估建议质量(3 评估者) ← 本次冲刺**本来就不做**
```

> 注意 11–13 是**一开始就排除**的，不是砍出来的。44 天里塞进 Yelp 会导致所有环节都做不深。
> 它们是 SIGIR/RecSys 版本的加强内容。

---

## Part 8 · Day 44 的交付物清单

- [ ] `paper/main.pdf` —— WWW 格式，正文页数符合 CFP，已匿名化
- [ ] Figure 1（performativity 曲线）+ 5 张辅助图，全部矢量
- [ ] 主表：因果效应 / 策略价值 / 竞争集验证 / 消融
- [ ] 补充材料：稳健性矩阵、超参网格、gold set 标注规范
- [ ] 匿名复现仓库链接（代码 + 派生数据 + 标注）
- [ ] `outputs/decisions.md` —— 全部偏离计划的决定（写 Limitations 时直接用）
- [ ] 三轮对抗自审的 review 与 response（**存档，rebuttal 时直接复用**）

---

## Part 9 · 明天（Day 1）就做的五件事

1. 修环境（`CODE_PLAN.md` §0.1）
2. `kaggle datasets download -d jiashenliu/515k-hotel-reviews-data-in-europe -p data/raw/d1`
3. 开一个 agent 专做 **W6**：建 LaTeX 骨架，开始精读 Part 1.1 里列的 12 篇承重文献，写 Related Work 初稿
4. 开一个 agent 专做 **W5**：搭基线复现框架（BPR / ItemKNN / DeepCoNN / NARRE）
5. 主线 agent 开始 W1：D1 解析

> **不要在 Day 1 纠结方法细节。** 这 44 天的成败取决于 Day 7 能不能画出 Figure 1 v0，
> 而不是取决于 aspect 检测器有多精致。**先让整条链路跑通，再让每个零件变好。**
