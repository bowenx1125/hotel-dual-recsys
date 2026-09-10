# 双视角酒店推荐系统 · 顶会级研究总规划

> **文件定位**：这是本项目的**唯一权威研究蓝图**，取代旧的 `RESEARCH_PLAN.md`（旧版保留为历史参考）。
> **读者**：(1) 项目作者 徐伯闻；(2) 接手执行的 Claude Code Agent。
> **配套文件**：`CODE_PLAN.md`（工程实现计划）、`CLAUDE.md`（Agent 工作守则）。
> **撰写日期**：2026-09-04

---

## Part 0 · TL;DR（先读这 20 行）

**现在的项目是什么**：一个基于 Booking.com 比利时酒店评论的双视角推荐系统原型。数据层已跑通（822 家爬取 / 745 家有坐标 / 321 家有价格），竞争集与 ABSA 有 MVP，但只覆盖 34 家酒店、1 个有效地理簇。这是一个**合格的 FYP**，但**不是一篇可投顶会的论文**。

**为什么现在投不了顶会**（详见 Part 1.4）：
1. 竞争集实际只形成了 1 个地理簇 → 核心创新点②在数据上立不住；
2. 价格覆盖率 39%，且是 2026 年快照对 2018–2021 年评论 → 审稿人一击必杀；
3. 单一国家、单一数据集 → 无泛化性证据；
4. Tourist 侧用「高评分=好酒店」当 label → 标签泄漏 + 循环论证；
5. Manager 侧只有 LLM-as-judge → 2025 年的文献已明确说这不能单独作为评测；
6. ABSA 无标注 gold set → 整条 aspect 链路没有精度证据。

**怎么改才能投顶会**（详见 Part 3）：把论文从「我做了一个系统」重构成「我提出并**验证**了一个可证伪的科学主张」。核心动作三条：

- **A. 换数据底盘**：主战场从「比利时 821 家」换成「515K Europe（6 大城市 1,493 家，自带经纬度）+ HotelRec（TripAdvisor 50M 评论，自带 aspect 子评分）」，比利时数据降级为**跨市场泛化的第三方 holdout**。这一步同时解决问题 1、3、6。
- **B. 换核心命题**：从「描述性诊断」（你在竞争集里排第 4）升级成「**处方性因果主张**」（把清洁度提升 X，你在竞争集里的排名/需求预计提升 Y ± Z）。这一步让论文从工程 demo 变成研究贡献。
- **C. 换评测范式**：竞争集不只是产品功能，它同时是**因果识别策略**——竞争集 = 匹配对照组。用 comp-set-matched DiD + 时序 holdout 回放来验证 Manager 侧建议，Tourist 侧改用无泄漏的行为代理标签。这一步解决问题 2、4、5。

**现实的投稿目标**（详见 Part 7）：
- 主目标 **RecSys 2027**（截稿 2027-04-25，CORE A，多利益相关者推荐的主场，与 FYP 结题时间完美对齐）；
- 备选 **CIKM 2027**（2027-05-22）；
- 早期低风险练兵 **ENTER 2027 working paper**（2026-10-11）；
- 期刊路线（往往比会议更适合这个题目）：*Tourism Management* / *IJHM* / *Information Processing & Management* / *Decision Support Systems*。

---

## Part 1 · 这个 FYP 到底是什么（现状实测盘点）

### 1.1 一句话定位

> 基于在线评论，构建一套**共享底层表征**，同时向**游客**（在预算档位内选最优酒店）和**酒店经理**（在本地竞争集内的相对位置 + aspect 诊断 + 改进/定价建议）输出决策支持。

### 1.2 数据资产清单（本次实测，非文档声称值）

| 资产 | 实测数字 | 位置 |
|---|---|---|
| 原始评论 | **26,675 条 / 820 家酒店 / 2018–2021 年** | `data/booking_reviews copy.csv`（93,790 行含多行文本） |
| 评论年份分布 | 2018: 4,851 / 2019: 13,799 / 2020: 5,428 / 2021: 2,308 | — |
| 单店评论量 | 中位数 **17**，均值 32.5，最大 846；≥50 条的 109 家，≥100 条的 50 家，≥200 条的 20 家 | — |
| 评分分布 | 强左偏：9–10 分占 53.7%（7,433 + 6,897） | — |
| 爬取结果 | 822 家：success 321 / partial 424 / failed 77 | `data/processed/hotels_all.csv` |
| 坐标覆盖 | **745 (91%)** | 同上 |
| 星级覆盖 | 529 (64%) | 同上 |
| **价格覆盖** | **321 (39%)** ← 瓶颈 | 同上 |
| 城市分布（有坐标） | Brussels 80 / Bruges 62 / Antwerp 38 / Ghent 29 / Ostend 25 / Liège 20 / Namur 18 / Minsk 18 / …；**Unknown 96** | 同上 |
| 竞争集 | **仅 34 家酒店入表**；有效簇实际只有 `geo0`（布鲁塞尔市中心）的 low/mid/high 三档；`geo1`（机场）标记为无效；9 家 isolated | `data/processed/compsets.csv` |
| ABSA 特征 | **24 家酒店**，7 个 aspect 的 net sentiment + mention rate + 差评占比 | `data/processed/aspect_features.csv` |
| 原始 HTML 存档 | 每家 gzip 存档，可重解析 | `data/scraped/html/` |
| 论文与图 | Partial Thesis 已交（5,589 词，11 条引用）；5 张图 | `FYP1_Partial_Thesis.docx`, `figures/` |

### 1.3 已完成 vs 未完成

**已完成**：Phase 0 爬虫（含 WAF 规避以外的合规做法：真实浏览器、3–8s 延迟、原始 HTML 落盘、不破验证码）、Phase 1 竞争集 MVP、Phase 2 ABSA MVP（本地 `yangheng/deberta-v3-base-absa` + 关键词门控）、Partial Thesis、Data Foundation PPT。

**未完成**：Phase 3 共享表征、Phase 4 Tourist ranker、Phase 5 Manager 诊断、Phase 6 评测/消融、Phase 7 完整论文。

### 1.4 现状的六个致命问题（必须直面）

> 这一节是整份文档最重要的部分。不解决这六条，后面做多少工程量都没用。

**P1 — 竞争集在数据上立不住（创新点②失效）**
`compsets.csv` 里真正有效的地理簇只有 `geo0` 一个（布鲁塞尔市中心），机场簇 `geo1` 因规模不足被判无效。一个「本地竞争集」方法论，实证只跑出**一个 local**，等于没有 local。审稿人第一个问题就是这个。
根因：DBSCAN 输入只有「有价格的布鲁塞尔酒店」，样本量被 39% 价格覆盖率二次砍掉。

**P2 — 价格的时间错配（一击必杀级别）**
评论来自 2018–2021，价格是 2026 年 7 月的快照，**中间隔了 5–8 年，还跨了 COVID**。当前文档里写「只用于相对档位所以可接受」——这个辩护在 B 类会议勉强能过，在 A 类会议一定被打。而且 39% 覆盖率意味着 61% 的价格是插补的（`price_is_proxy=1`），插补值直接决定了分档，也就直接决定了竞争集，**误差会从价格一路传导到全部结论**。

**P3 — 单一市场，无泛化证据**
96% 比利时，最大城市 80 家酒店。任何「我们的方法对酒店市场普遍有效」的主张都没有支撑。顶会要求至少 2–3 个市场/数据集。

**P4 — Tourist 侧的标签是循环的**
现计划用「高 `avg_rating` / 高评论数」当 relevance label，而 `avg_rating` 同时也在特征里（或与特征强相关）。这是教科书级的 label leakage，同时是循环论证：「好酒店的定义是评分高，我们的模型能找出评分高的酒店」——没有信息量。

**P5 — Manager 侧没有可验证的评测**
现计划是 LLM-as-judge + case study。2025 年的评测文献（见 Part 2.5）已经系统性证明：LLM judge 存在 position/verbosity/self-enhancement bias，与人类标注在相关性标准上系统性分歧，**未经人工校准不能单独作为主评测**。而 Manager 侧恰恰是本项目的最大卖点——卖点没有评测 = 没有论文。

**P6 — ABSA 链路没有精度证据**
现方案 = 关键词门控 + DeBERTa-ABSA，无标注 gold set，无 F1/κ。所有下游 aspect 结论都建立在一个未经验证的抽取器上。

---

## Part 2 · 文献定位：别人做过什么，缺口在哪

> 以下每条都给了可直接引用的代表文献。Agent 在写 Related Work 时**必须逐篇核对原文**再引用，不得直接抄本节措辞。

### 2.1 多利益相关者推荐（本项目的理论母体）

推荐系统长期只优化 consumer 侧效用；Abdollahpouri 等人的综述系统化了 consumer / provider / platform 三方框架，并指出 **provider 侧的目标建模严重不足**。旅游领域已有两侧公平性工作（TFROM, SIGIR'21；ACM RecSys'23 的旅游多方公平与可持续性论文）。

**关键观察**：现有 provider 侧工作几乎都在做**曝光公平（exposure fairness）**——「怎么把流量更公平地分给供给方」。**没有人做「给供给方一份可执行的、经过因果验证的改进处方」**。这正是本项目的位置。

代表文献：
- Abdollahpouri, Adomavicius, Burke, Guy, Jannach, Kamishima, Krasnodebski, Pizzato. *Multistakeholder recommendation: Survey and research directions.* UMUAI 30(1):127–158, 2020.
- Wu et al. *TFROM: A Two-sided Fairness-Aware Recommendation Model for Both Customers and Providers.* SIGIR 2021.
- *Fairness and Sustainability in Multistakeholder Tourism Recommender Systems.* ACM UMAP/RecSys workshop line, 2023.
- Burke et al. *Multistakeholder Recommender Systems.* In *Recommender Systems Handbook* (3rd ed.), 2022.

### 2.2 基于评论的推荐（本项目的方法母体 + 一个必须知道的警告）

DeepCoNN / NARRE / ANR 一脉把评论文本喂进推荐模型。但 **Sachdeva & McAuley (SIGIR 2020)** 做了一次严厉的复现研究，结论是：多数评论增强模型**打不过简单基线**，把评论遮蔽掉性能几乎不变，且论文之间存在结果互抄。

**这对本项目意味着两件事**：
1. 不要把「我们用了评论所以更好」当卖点——这条路已经被证伪过一次；
2. 论文里**必须**有一个「mask reviews」的消融，主动证明你的增益真的来自评论内容，而不是来自评分统计量。这是把 P4 变成加分项的方法。

代表文献：
- Sachdeva & McAuley. *How Useful are Reviews for Recommendation? A Critical Review and Potential Improvements.* SIGIR 2020.
- Zheng, Noroozi, Yu. *Joint Deep Modeling of Users and Items Using Reviews for Recommendation (DeepCoNN).* WSDM 2017.
- Chen, Zhang, Liu, Ma. *Neural Attentional Rating Regression with Review-level Explanations (NARRE).* WWW 2018.

### 2.3 ABSA（本项目的特征工程母体）

从规则 → SVM → LSTM/CNN → Transformer；当前 SOTA 分两支：(a) 微调式（InstructABSA 等指令微调）、(b) LLM zero/few-shot。近期结论：**微调 GPT-3.5 在 SemEval-2014 联合抽取+极性任务上 F1 ≈ 83.8**，优于 InstructABSA 约 5.7；zero-shot LLM 在英文上可用但仍不及任务专用微调模型；LoRA 微调的小模型在低资源领域可逼近或超过闭源大模型。

**这对本项目意味着**：现在的「关键词门控 + DeBERTa」是 2021 年的做法。顶会版本应该是：**LLM 蒸馏 + 小模型 LoRA 微调 + 人工 gold set 验证**（见 Part 5.M2）。

代表文献：
- Scaria et al. *InstructABSA: Instruction Learning for Aspect Based Sentiment Analysis.* NAACL 2024.
- *Large language models for aspect-based sentiment analysis.* arXiv:2310.18025.
- *Do we still need Human Annotators? Prompting LLMs for Aspect Sentiment Quad Prediction.* arXiv:2502.13044.
- Yang et al. `yangheng/deberta-v3-base-absa`（当前项目在用的模型）。

### 2.4 评论的因果经济学（本项目升级的关键钥匙）★

这一支文献才是把本项目从「系统」变成「研究」的杠杆：

- **Luca (2016)** / **Lewis & Zervas**：用 DiD 估计评分变化对需求的因果效应——「1 星提升 ↔ 需求提升约 26%」。
- **Proserpio & Zervas (Marketing Science 2017)**：用 DiD（TripAdvisor 变化 vs 同店 Expedia 基线做对照）估计「管理层回复评论」的因果效应。**这篇是本项目 Manager 侧最好的方法论模板。**
- **Deng et al., WSDM 2022** — *Estimating Causal Effects of Multi-Aspect Online Reviews with Multi-Modal Proxies*：用多模态代理处理未观测混杂，回答「如果 Service 这个 aspect 的质量提升 10%，商家人气会怎么变？」

> ⚠️ **WSDM'22 这篇是本项目最近的先行工作，必须正面处理**。差异化点见 Part 3.3。

- **Pokryshevskaya & Antipov**：用 TripAdvisor 气泡评分的四舍五入规则做断点回归（RDD）估计评分对酒店人气的影响——这是本项目可以复用的第二个识别策略。

### 2.5 LLM-as-a-judge 的可靠性（决定 Manager 侧评测怎么写）

2025 年多篇系统性评估指出：LLM judge 存在 position / verbosity / self-enhancement bias；「高相关性 ≠ 高效度」，judge 可能只是学会了模仿人类的偏见；表层文本操纵可以骗过 judge。最佳实践：显式 rubric、顺序随机化、跨模型家族集成投票、事后与人工评分做校准。

**结论**：LLM-as-judge 在本项目里只能是**次要指标**，且必须配一个人工标注子集报告相关性/一致性（见 Part 6.3）。

### 2.6 竞争集 / 市场划分（创新点②的学术出身）

酒店业实务里 comp set 是 STR 报告的核心概念，选择标准是「规模、类型、设施、地理、以及**客人可替代性（guest substitutability）**」，通常 5–10 家。学术侧最强的可迁移方法论是产业组织的 **文本化产品市场分类（Hoberg & Phillips, TNIC）**：不用行业代码，而用产品描述的文本相似度定义竞争者。

**本项目的机会**：把「comp set」从一个**拍脑袋的启发式**，升级为一个**从数据学出来、并且可被证伪验证的构造**（见 Part 3.2 C1）。

代表文献：
- Hoberg & Phillips. *Text-Based Network Industries and Endogenous Product Differentiation.* Journal of Political Economy, 2016.
- Cornell Hospitality 关于 comp set identification 的 agency-perspective 研究。

### 2.7 缺口总结（论文 Introduction 的核心段落）

| 已有工作 | 做了什么 | 没做什么 |
|---|---|---|
| 多方推荐 | provider 侧的**曝光公平** | provider 侧的**可执行改进处方** |
| 评论推荐 | 用评论提升 consumer 侧排序精度 | 把评论转成 provider 侧的**竞争情报** |
| ABSA / 酒店评论挖掘 | 抽 aspect、算情感、描述性洞见 | 洞见的**因果有效性验证**（改了真的有用吗？） |
| 评论因果经济学 | 单店层面「评分↑→需求↑」 | **竞争集条件下的相对效应** + 转化为**推荐策略** |
| 酒店 comp set | 实务启发式（地理+规模+类型） | 从数据学习 + **可证伪的验证** |

> **一句话缺口**：现有工作要么给游客排序（不管供给方），要么给供给方公平曝光（不管怎么变好），要么给出描述性诊断（不管建议是否真的有效）。**没有人建过一个「诊断 → 处方 → 因果验证」闭环的供给侧推荐系统。**

---

## Part 3 · 重构后的论文（顶会版本）

### 3.1 论文的一句话 pitch

> **CompSetRec**：我们把「本地竞争集」同时用作 (a) 产品意义上的可比市场定义，和 (b) 统计意义上的**匹配对照组**；在此之上构建一个游客/经理共享的 aspect 级表征，使得经理侧的改进建议不再是描述性的，而是可以用 comp-set-matched 因果估计**验证其预期收益**，并在时序 holdout 上被证实优于「修最差项」等启发式策略。

### 3.2 四个 Contribution（论文的骨架）

**C1 · 可学习、可证伪的本地竞争集（Learned Local Competition Set）**
不再用「地理 ∩ 价格档 ∩ 星级」硬规则，而是把竞争集定义成一个**需求可替代性图**：
`sim(h_i, h_j) = f(地理邻近度, 需求组成相似度, 价格档相似度, 产品文本相似度)`
其中「需求组成」来自评论的 `tags` / 国籍 / 出行类型 / 停留时长向量（沿用 Hoberg-Phillips 的 TNIC 思路）。
**关键：这个构造是可验证的。** 验证协议见 Part 6.1（用「留出 aspect 的相互预测力」和「需求冲击的溢出效应」两个证伪测试）。

**C2 · 竞争集相对的、稀疏感知的共享表征（CompSet-Relative Representation, CRR）**
每家酒店表示为在**其竞争集内部标准化**后的向量，而非绝对值：
`z_h = [ (x_h - μ_C(h)) / σ_C(h) ]`，x 包含 aspect 情感、提及率、差评热点、价格位次、位置便利性、评论量。
稀疏性用**经验贝叶斯收缩**处理：评论少的店，其 aspect 分数向竞争集均值收缩，收缩强度由评论量决定。
Tourist 与 Manager 读同一个 `z_h`，只是读取方向不同（Tourist：档位内 argmax；Manager：自身 percentile + gap 分解）。

**C3 · 因果验证的处方模块（Prescriptive Module with Causal Validation）★ 核心创新**
经理侧输出不是「你排第 4」，而是「**把 cleanliness 从竞争集第 70 百分位提到第 30 百分位，预计后续 6 个月综合评分 +0.18（95% CI [0.07, 0.29]），竞争集排名 +1.7 位**」。
估计方法：以竞争集为匹配对照的**面板 DiD / 双重稳健估计**，处理定义为「某店某 aspect 情感发生持续性跃迁」，结果为「后续窗口的评分 / 评论量 / 竞争集排名」。
推荐策略 = 在预算约束下选择**期望提升最大**的 aspect 干预组合，而非「修最差项」。

**C4 · 供给侧推荐的可复现评测协议与基准（Benchmark & Protocol）**
公开：竞争集构建代码、aspect gold set（人工标注）、时序切分协议、四个基线（随机 / 修最差项 / 修最常被提及项 / 纯 LLM 建议），以及策略价值的离线估计器。这一条本身就是被会议接收的理由（RecSys 有 reproducibility track）。

### 3.3 与最近先行工作（WSDM'22 多 aspect 因果）的差异化

| 维度 | Deng et al. WSDM'22 | 本项目 |
|---|---|---|
| 单位 | 单个商家，全局比较 | **竞争集内相对**（对照组是同市场竞争者） |
| 混杂处理 | 多模态代理变量 | **竞争集匹配 + 时序 DiD**（更接近经济学标准做法） |
| 输出 | 因果效应估计值 | 效应 → **可执行处方 → 排序策略**，闭环到推荐 |
| 评测 | 效应估计精度 | **策略价值**（时序 holdout 回放） + 人工校准的建议质量 |
| 双视角 | 无 | 同一表征驱动 Tourist 与 Manager，并测两者的**耦合性** |

> 论文里必须有一段明写这个对比表。审稿人一定会问「和 WSDM'22 有什么不同」。

### 3.4 一个可证伪的核心假设（论文的科学性来源）

> **H1（耦合假设）**：如果 Manager 侧的处方是有效的，那么在竞争集内实施该处方的酒店，其在 **Tourist 侧排序**中的位次提升，应显著大于实施「修最差项」启发式的酒店。

这条假设把两个视角绑在一起，使「双视角」不再只是一个产品口号，而是一个**可以被数据推翻的科学主张**。Part 6.4 给出检验方法。

---

## Part 4 · 数据战略（三层数据底盘）

> 这是解决 P1/P2/P3/P6 的总开关。**必须先做这一步，再写任何模型代码。**

### D1（主数据集）· 515K Hotel Reviews in Europe

- Kaggle: `jiashenliu/515k-hotel-reviews-data-in-europe`
- **515,738 条评论 / 1,493 家酒店 / 6 个欧洲大城市**（Amsterdam, Barcelona, London, Milan, Paris, Vienna）/ 约 2015-08 – 2017-08
- **自带 `lat` / `lng`** → 竞争集不再依赖爬虫，**P1 直接解决**
- **`Positive_Review` 与 `Negative_Review` 分列** → 天然的弱监督极性标签，**P6 的训练数据来源**
- 其他关键列：`Hotel_Name`, `Hotel_Address`, `Average_Score`, `Reviewer_Score`, `Review_Date`, `Reviewer_Nationality`, `Tags`, `Total_Number_of_Reviews`, `Additional_Number_of_Scoring`, `Total_Number_of_Reviews_Reviewer_Has_Given`, `Review_Total_Positive_Word_Counts`, `Review_Total_Negative_Word_Counts`, `days_since_review`
- **为什么它救命**：6 个城市 × 数百家酒店 = **几十到上百个有效竞争集**（现在只有 1 个）；2 年时间跨度 = 可做面板 DiD；`Tags` 提供出行类型/房型/停留时长 = C1 的需求组成向量。

### D2（验证数据集）· HotelRec

- Antognini & Faltings, LREC 2020，TripAdvisor **约 5,000 万条**评论
- **关键价值：自带 aspect 子评分**（service / cleanliness / value / location / sleep quality / rooms）
- **用途**：(a) ABSA 抽取器的**外部 ground truth**——直接解决 P6，可以报告「我们抽出的 aspect 情感与 TripAdvisor 用户自己打的 aspect 子评分相关性 = r」；(b) 大规模预训练/微调语料；(c) 第二个市场做泛化验证
- 注意：全量 50M 太大，按城市/酒店抽样即可（建议抽 D1 的 6 个城市 + 若干北美城市）

### D3（原创数据集）· 本项目自采的比利时数据

- 822 家 / 26,675 条评论 / 745 家坐标 / **321 家真实价格**
- **降级为**：(a) 跨市场泛化的第三方 holdout（证明方法迁移到小城市/非首都市场仍成立）；(b) **价格研究的唯一真值来源**——它是三个数据集里**唯一有真实价格**的，用来训练与验证价格代理模型
- **这仍然是论文的原创贡献**（自采数据 + 合规爬取协议 + 原始 HTML 存档可复现），只是不再当主战场

### D4 · 价格问题的正确解法（P2 的解决方案）

不要再假装 2026 的价格能代表 2018 的价格。改成三步：

1. **把价格降级为「档位」而非「数值」**，并且论证**价格位次（rank）在时间上远比价格水平（level）稳定**——这一点可以用 D3 里 3 个日期的价格快照做实证支持（本项目已经抓了 2026-07-15/22/29 三天）。
2. **训练价格档位代理模型**：在 D3 的 321 家有真实价格的酒店上，用「星级 + 品牌 + 房型 tags + 地址/位置 + 评论中的价格感知词」预测价格三分位，报告 accuracy / Spearman ρ。然后把这个模型迁移到 D1/D2。
3. **全流程做价格敏感性分析**：主结果 + 「随机扰动价格档位 10%/20% 后结论是否稳定」。审稿人问「你的价格不可靠」时，你有一张图直接回答。

> 如果代理模型 Spearman ρ < 0.5，**放弃把价格作为竞争集的定义维度**，改用「星级 + 房型 + 需求组成」定义竞争集，价格只作为评判维度。这是干净的止损方案，不是失败。

---

## Part 5 · 方法（模块级设计）

### M1 · 竞争集构建（对应 C1）

```
输入: 酒店集合 H（含 lat/lng, star, price_tier_hat, demand_mix, text_profile）
1. 地理候选: 对每个 h，取半径 r 内的酒店（r ∈ {0.5, 1.0, 1.5, 2.0} km，做敏感性分析）
   —— 城市中心用小 r，郊区用大 r（自适应：r_h = k-th nearest neighbor distance）
2. 需求组成向量 d_h: 由 tags 聚合而成
   [leisure/business 比例, couple/family/solo/group 比例, 房型分布, 停留时长分布, 国籍分布(top-K + 熵)]
3. 文本产品画像 t_h: 评论正文的 TF-IDF / SBERT 向量（描述"这家店是什么样的店"）
4. 可替代性得分: s(i,j) = w1·geo(i,j) + w2·cos(d_i,d_j) + w3·cos(t_i,t_j) + w4·price_tier_match(i,j)
5. 竞争集 C(h) = top-m 邻居（m ∈ [5,10]，对齐业界惯例），或对 s 做阈值+社区发现
输出: compset_edges.parquet (i, j, s), compset_membership.parquet (hotel_id, compset_id, rank)
```

**权重 w 怎么定？** 不要拍脑袋。用 Part 6.1 的证伪测试做**无监督模型选择**：选让「留出预测力」最高的一组 w。

### M2 · ABSA 管线（对应 C2 的输入，解决 P6）

**三段式，越往后越贵，越往前越快：**

1. **标注层（一次性）**：从 D1 抽 **800 条**评论句 → LLM（Claude/GPT）生成 aspect-polarity 四元组 → **人工复核 300 条**作为 gold set → 报告 LLM-vs-human 的 Cohen's κ 与 F1。这 300 条人工标注是论文可信度的地基，**不可省**。
2. **模型层**：用 LLM 标注的 800 条 + `Positive_Review`/`Negative_Review` 的弱监督信号，**LoRA 微调一个小模型**（DeBERTa-v3 / Qwen-0.5B 级别）→ 在 gold set 上报告 F1。基线对比：当前的关键词门控+DeBERTa、zero-shot LLM、InstructABSA。
3. **验证层（外部效度）**：在 D2 (HotelRec) 上跑抽取器，与 TripAdvisor **用户自评的 aspect 子评分**算相关系数。这是**独立于自己标注**的外部验证，非常有说服力。

**Aspect 集合**（固定，全程一致）：`location, cleanliness, breakfast/food, service/staff, noise/sleep, room/facilities, value_for_money, wifi/tech`（8 个，比现在多 wifi，因为 PPT 的 future work 提到了）

### M3 · 共享表征 CRR（对应 C2）

```
对每家酒店 h，在其竞争集 C(h) 内计算：
  raw:      a_h ∈ R^8 (aspect net sentiment), m_h ∈ R^8 (mention rate),
            n_h (评论数), p_h (价格档), g_h (位置便利性: 到地铁/景区/机场距离),
            v_h (差评热点分布 ∈ Δ^7), s_h (星级)
  收缩:      ã_h = (n_h·a_h + κ·μ_C) / (n_h + κ)     # 经验贝叶斯，κ 由竞争集内方差估计
  相对化:    z_h[k] = (ã_h[k] - μ_C[k]) / σ_C[k]      # 竞争集内 z-score
  位次:      q_h[k] = percentile of ã_h[k] within C(h)
输出: hotel_representation.parquet
Tourist 读取: score(h | budget_tier) = f_θ(z_h) ，在同档位内排序
Manager 读取: gap_h[k] = q_target - q_h[k]，按 C3 的预期收益排序
```

### M4 · 因果处方模块（对应 C3）★

**面板构造**：把每家酒店的评论按季度（或 6 个月窗口）聚合 → `(hotel, period)` 面板，每期有 aspect 情感、评分、评论量。

**处理（treatment）定义**：酒店 h 在 aspect k 上发生**持续性跃迁**——即 `ã_{h,k,t}` 相对前 W 期基线上升超过 δ，且在其后至少 2 期保持。

**识别策略（三条，从弱到强，论文里全做，作为稳健性）**：
1. **CompSet-matched DiD**：对照组 = 同竞争集内、同期未发生跃迁的酒店。这是本项目的核心识别策略——**竞争集天然满足平行趋势的可信度**，因为它们面对同一地理/季节/需求冲击。
2. **Event study**：画处理前后 ±4 期的效应曲线，**检验处理前无预趋势**（这是审稿人验真的标准动作，必须有图）。
3. **双重稳健估计（AIPW / Doubly Robust）**：倾向得分（哪些酒店更可能改进）+ 结果模型，两者任一正确即一致。

**COVID 处理**：D1（2015–2017）天然避开 COVID —— 这是选它当主数据集的又一个理由。D3（2018–2021）跨 COVID，必须显式建模（时间固定效应 + 明确声明 2020Q1 断点）。

**处方策略**：
```
对目标酒店 h，对每个 aspect k：
  预期收益 τ̂(h,k) = 估计的处理效应（在 h 的竞争集特征条件下）
  成本 c(k)       = 场景化假设（清洁/服务改进成本 < 房间翻新成本），做敏感性分析
  处方 = argmax_{S ⊆ aspects, Σc ≤ B}  Σ_{k∈S} τ̂(h,k)
基线策略: (a) 修 net sentiment 最低项  (b) 修差评占比最高项
         (c) 修与竞争集 gap 最大项    (d) 直接问 LLM
```

**LLM 的正确位置**：LLM **只做自然语言化**（把结构化的 τ̂、CI、gap 翻译成经理能读的一段话），**不参与数值生成**。论文里明写这一点——这是避免「LLM 幻觉」质疑的标准做法。

### M5 · Tourist 侧（解决 P4）

**标签必须换掉。** 三个无泄漏的替代方案，按优先级：

1. **行为代理标签（首选）**：用 `Total_Number_of_Reviews` 在**时间上的增量**作为需求代理 —— 「在时间窗 [t, t+Δ] 内，竞争集内哪家酒店获得了更多新评论」= 哪家被更多人选择。**这是真实的选择行为，不是评分。** 且天然做到时序切分（用 t 之前的特征预测 t 之后的需求份额）。
2. **竞争集内的需求份额（share-of-voice）**：`y_h = 新增评论数_h / Σ_{j∈C(h)} 新增评论数_j`，学 learning-to-rank。
3. 保留「评分」作为**另一个**目标做多任务，但主结果用 (1)。

**模型**：LightGBM LambdaMART（主）+ 一个简单加权打分（可解释基线）+ 一个神经 ranker（可选）。
**必做消融**：mask reviews（回应 Sachdeva & McAuley 的批评）、去掉竞争集相对化（用绝对值）、去掉贝叶斯收缩、去掉价格。

---

## Part 6 · 评测协议（审稿人最在意的部分）

### 6.1 竞争集的证伪测试（C1 的验证 —— 这一节是论文的亮点）

竞争集是个「构造」，不能只靠直觉。给两个可证伪的检验：

**T1 · 留出互预测力（leave-one-out predictability）**
如果 C(h) 真的是 h 的竞争者，那么用 C(h) 的属性应该比用「随机同城酒店」更能预测 h 的留出属性（评分、需求增长、价格）。
指标：`ΔR²(CompSet vs 随机同城基线)`，同时对比「只用地理」「只用价格」「只用星级」的消融。

**T2 · 需求溢出（demand spillover）**
真正的竞争者之间应存在**替代效应**：竞争集内某店需求异常上升的时期，同集其他店的需求份额应下降。
指标：面板回归里同集其他店需求的系数应显著为负；随机对照组应不显著。
**如果 T2 通过，这就是「我们的 comp set 抓到了真实替代关系」的硬证据**，远强于任何定性论证。

### 6.2 Tourist 侧

- 指标：NDCG@{5,10}、MAP、Recall@K，**按竞争集分组计算再宏平均**（避免大城市主导）
- 切分：**严格时序切分**（train: t ≤ T1，valid: T1<t≤T2，test: t > T2），绝不随机切分
- 基线：① 全局评分排序 ② 评分 + 价格过滤 ③ 流行度（评论数） ④ ItemKNN / BPR-MF ⑤ 纯 LLM 排序 ⑥ 去掉竞争集相对化的本方法
- 显著性：跨竞争集做配对检验（Wilcoxon signed-rank），报告 p 值与效应量

### 6.3 Manager 侧（三层，解决 P5）

**层 1 · 因果效应的统计有效性**
- Event study 图（处理前无预趋势）
- Placebo test（把处理时点随机前移，效应应消失）
- 安慰剂 aspect（对一个理应无关的 aspect 做同样估计，应不显著）
- 报告效应量 + CI，不只报 p 值

**层 2 · 处方策略的价值（策略层评测）★**
在时序 holdout 上做**回放（replay）**：对每家在测试期实际发生了 aspect 跃迁的酒店，检查**我们的策略是否会推荐这个 aspect**，并比较各策略下的**实现收益**。
指标：`Policy Value = E[实际观测到的结果提升 | 策略推荐的 aspect 恰好被改进]`，用 IPS / SNIPS / Doubly-Robust 做离线策略估计（这是 RecSys 社区标准的 off-policy evaluation 工具，用在这里非常契合）。
**基线**：修最差项 / 修最常提项 / 随机 / LLM 直觉。

**层 3 · 建议文本质量（辅助指标，不是主指标）**
- 人工评估：**至少 3 位评估者 × 60 条建议**，5 分制评 relevance / actionability / grounding（是否有数据支撑）/ specificity，报告 **Krippendorff's α**
- LLM-as-judge：多模型集成（≥2 个不同家族）、顺序随机化、显式 rubric，**并报告与人工评分的相关性**（Part 2.5 要求）
- 幻觉检测：自动校验建议里出现的每个数字是否能在结构化输出里找到（应为 100%，因为 LLM 不生成数字）

### 6.4 双视角耦合性检验（验证 H1）

对测试期实际改进了某 aspect 的酒店，计算其在 Tourist 排序中的位次变化；比较「本方法推荐过的 aspect」组 vs 「启发式推荐的 aspect」组。若前者位次提升显著更大，H1 得到支持。
**这是论文里"双视角"这个词唯一的硬证据**，务必做。

### 6.5 消融矩阵（一张表说明每个组件都必要）

| 移除的组件 | 预期受损的指标 |
|---|---|
| 竞争集（改全局） | T1/T2 失效；Tourist NDCG↓；Manager 效应估计偏误↑ |
| 竞争集相对化（用绝对值） | Tourist NDCG↓；跨城市泛化↓ |
| 贝叶斯收缩 | 少评论酒店的排序方差↑，尾部性能↓ |
| Aspect 特征（mask reviews） | 若不降 → 说明评论无用（回应 SIGIR'20 批评）|
| 差评热点分布 | Manager 处方准确率↓ |
| 因果估计（改用相关性） | Policy Value↓（这是 C3 的核心证明） |
| 价格维度 | 见 Part 4.D4 的敏感性分析 |

---

## Part 7 · 投稿策略与时间线

### 7.1 目标venue（诚实排序）

| Venue | 截稿 | 等级 | 匹配度 | 判断 |
|---|---|---|---|---|
| **ENTER 2027** (eTourism, Madrid) | full paper 2026-09-13 / **working paper 2026-10-11** | 领域会议 | ★★★★★ | **先投 working paper 练兵**，拿早期反馈，风险极低 |
| **RecSys 2027** (Hawaiʻi) | **2027-04-25** | CORE A | ★★★★★ | **主目标**。多利益相关者推荐的主场，与 FYP 结题完美对齐 |
| **CIKM 2027** (Sydney) | 2027-05-22 | CORE A | ★★★★ | 备选，RecSys 被拒后 4 周内改投 |
| SIGIR 2027 | 2027-01-23 | CORE A* | ★★★ | 时间紧（4.5 个月），除非 12 月前实验全做完，否则不建议 |
| WWW 2027 | 2026-10-25 | CORE A* | ★★ | **太紧，放弃** |
| WSDM 2027 | 已截稿（2026-08） | CORE A* | — | 错过 |
| *Tourism Management* / *IJHM* | 滚动 | Q1 期刊 | ★★★★★ | **强烈建议并行考虑**：这个题目在酒店管理期刊的价值远高于在 CS 会议；无截稿压力，允许更长的方法论叙述 |
| *IP&M* / *DSS* | 滚动 | Q1 期刊 | ★★★★ | CS 侧期刊，接受应用型系统研究 |

> **对「顶会」的诚实话**：以本项目的数据规模和单人工作量，投中 SIGIR/WWW/KDD 主会的概率不高——那些会议的 accept rate ~15–20%，且偏好方法论新颖度极高或工业规模数据的工作。**RecSys 是现实且体面的顶会目标**（它是推荐系统的旗舰会议，CORE A，且明确欢迎应用/多方视角的研究）。如果目标是「有一篇真正被同行认可的成果」，**RecSys full/short paper + 一篇 Q1 期刊** 是比「硬冲 A*」更高期望值的策略。

### 7.2 里程碑时间线（以 RecSys 2027-04-25 倒推）

| 阶段 | 时间 | 交付物 | 门禁（不达标不进入下一阶段） |
|---|---|---|---|
| **S0 数据底盘** | 2026-09-05 → 09-25 | D1/D2 下载清洗完毕；统一 schema；D3 价格代理模型 | **≥ 50 个有效竞争集**；价格代理 Spearman ρ 报告出来 |
| **S1 竞争集 + 证伪测试** | 09-26 → 10-20 | M1 完成；T1/T2 结果 | **T2 显著**（否则改 C1 的定义或降级该 contribution） |
| **S1.5 ENTER working paper** | 10-01 → 10-11 | 4–6 页 working paper 投 ENTER 2027 | 用 S0+S1 的结果即可 |
| **S2 ABSA + gold set** | 10-21 → 11-20 | 300 条人工标注；LoRA 模型；HotelRec 外部验证 | **gold set F1 ≥ 0.75**；与 HotelRec 子评分相关 r ≥ 0.4 |
| **S3 表征 + Tourist** | 11-21 → 12-20 | M3/M5；全部基线与消融 | **在无泄漏标签下显著优于最强基线** |
| **S4 因果 + 处方** | 12-21 → 2027-02-15 | M4；event study；placebo；Policy Value | **event study 无预趋势**；Policy Value 优于全部启发式 |
| **S5 人工评估** | 02-16 → 03-05 | 3 评估者 × 60 建议；α 系数 | Krippendorff α ≥ 0.6 |
| **S6 写作** | 03-06 → 04-15 | 完整论文 + 补充材料 + 开源仓库 | 至少 2 位外部读者读过 |
| **S7 投稿缓冲** | 04-16 → 04-25 | 提交 | — |

> **每个阶段的门禁必须真的执行**。做不到就走 Part 8 的止损方案，而不是硬推到写作阶段才发现结果不成立。

---

## Part 8 · 风险登记表与止损方案

| # | 风险 | 概率 | 影响 | 止损方案（预先决定，不要临场慌） |
|---|---|---|---|---|
| R1 | 价格代理模型太差（ρ<0.5） | 中 | 高 | 价格退出**定义维度**，竞争集改用「地理+星级+需求组成」；价格只做评判维度，并把这个决定写进 Limitations |
| R2 | T2（需求溢出）不显著 | 中 | 高 | 竞争集从「核心贡献 C1」降级为「方法组件」，论文重心全压 C3 因果处方；同时试更小的 m 和更严的地理半径 |
| R3 | DiD 出现预趋势 | 中 | 高 | 换识别策略：改用 RDD（借鉴 Pokryshevskaya & Antipov 的评分四舍五入断点）或 synthetic control；或把主张从"因果"降级为"预测性关联"并明确声明 |
| R4 | Aspect 跃迁事件太少（治疗组不足） | 中 | 中 | 放宽 δ 阈值；改用连续处理（dose-response）而非二元处理；把窗口从季度改成半年 |
| R5 | ABSA gold set F1 太低 | 低 | 中 | 缩小 aspect 集合到 5 个最清晰的；改用 LLM 直接抽取（贵但准），只对采样子集做 |
| R6 | HotelRec 下载/规模问题 | 中 | 低 | 只抽 D1 六城市对应的子集；或用 TripAdvisor 的公开小数据集替代 |
| R7 | 时间不够（FYP + 论文双压力） | **高** | 高 | **优先级顺序：S0 > S1 > S4 > S3 > S5**。若必须砍，砍 Tourist 侧的神经模型和 S5 的规模（3 人×60 → 3 人×30）。**绝不砍 S0 和因果验证**——那是论文的全部价值 |
| R8 | 与 WSDM'22 差异化不被认可 | 中 | 高 | 提前写好差异化表（Part 3.3），并在实验里**直接复现 WSDM'22 的方法作为基线**——最强的差异化证明是"我们比它好，并且好在哪" |
| R9 | 单人工作量不足以支撑 A 类 | 中 | 中 | 走 short paper（RecSys 有 short track）或期刊路线；期刊对工作量的容忍度更高、审稿轮次允许补实验 |

---

## Part 9 · 参考文献（起始清单，Agent 需逐一核对原文后引用）

**多利益相关者推荐**
1. Abdollahpouri H., Adomavicius G., Burke R., Guy I., Jannach D., Kamishima T., Krasnodebski J., Pizzato L. *Multistakeholder recommendation: Survey and research directions.* UMUAI, 30(1):127–158, 2020.
2. Abdollahpouri H., Burke R. *Multi-stakeholder Recommendation and its Connection to Multi-sided Fairness.* RMSE Workshop @ RecSys, 2019. arXiv:1907.13158.
3. Wu H., Ma C., Mitra B., Diaz F., Liu X. *TFROM: A Two-sided Fairness-Aware Recommendation Model for Both Customers and Providers.* SIGIR 2021.
4. Burke R. et al. *Multistakeholder Recommender Systems.* Recommender Systems Handbook (3rd ed.), Springer, 2022.
5. *Fairness and Sustainability in Multistakeholder Tourism Recommender Systems.* ACM, 2023. (DOI 10.1145/3565472.3595607)

**基于评论的推荐与其批判**
6. Sachdeva N., McAuley J. *How Useful are Reviews for Recommendation? A Critical Review and Potential Improvements.* SIGIR 2020. arXiv:2005.12210.
7. Zheng L., Noroozi V., Yu P.S. *Joint Deep Modeling of Users and Items Using Reviews for Recommendation.* WSDM 2017.
8. Chen C., Zhang M., Liu Y., Ma S. *Neural Attentional Rating Regression with Review-level Explanations.* WWW 2018.

**ABSA**
9. Scaria K. et al. *InstructABSA: Instruction Learning for Aspect Based Sentiment Analysis.* NAACL 2024.
10. *Large language models for aspect-based sentiment analysis.* arXiv:2310.18025, 2023.
11. *Do we still need Human Annotators? Prompting LLMs for Aspect Sentiment Quad Prediction.* arXiv:2502.13044, 2025.

**评论的因果经济学 ★**
12. Deng et al. *Estimating Causal Effects of Multi-Aspect Online Reviews with Multi-Modal Proxies.* WSDM 2022. arXiv:2112.10274.
13. Proserpio D., Zervas G. *Online Reputation Management: Estimating the Impact of Management Responses on Consumer Reviews.* Marketing Science, 36(5), 2017.
14. Lewis G., Zervas G. *The Welfare Impact of Consumer Reviews: A Case Study of the Hotel Industry.* Working paper / NBER SI 2016.
15. Luca M. *Reviews, Reputation, and Revenue: The Case of Yelp.com.* HBS Working Paper 12-016.
16. Pokryshevskaya E.B., Antipov E.A. *Robust regression / RDD analysis of TripAdvisor bubble ratings.* HSE Working Paper, 2020.

**市场划分 / 竞争集**
17. Hoberg G., Phillips G. *Text-Based Network Industries and Endogenous Product Differentiation.* Journal of Political Economy, 124(5), 2016.
18. *An Agency Perspective on Hotel Competitive Set Identification.* Cornell University thesis.

**评测方法论**
19. *Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models Across Agreement, Consistency, and Bias.* arXiv:2606.19544, 2026.
20. *LLM-as-a-Judge for Reliable and Explainable Offline Evaluation.* arXiv:2606.22961, 2026.
21. Gilotte A. et al. *Offline A/B testing for Recommender Systems.* WSDM 2018.（IPS/SNIPS 离线策略评测）

**数据集**
22. Antognini D., Faltings B. *HotelRec: a Novel Very Large-Scale Hotel Recommendation Dataset.* LREC 2020.
23. Liu J. *515K Hotel Reviews Data in Europe.* Kaggle, 2017.
24. *Booking.com Hotel Reviews.* Kaggle (thedevastator), — 本项目 D3 的原始来源。

---

## 附录 A · 从旧计划到新计划的映射

| 旧 Phase | 新归属 | 变化 |
|---|---|---|
| Phase 0 爬虫 | D3 + Part 4.D4 | 保留，但降级为价格研究与泛化 holdout |
| Phase 1 竞争集 | M1 / C1 | **重写**：从硬规则改为可学习 + 加 T1/T2 证伪测试 |
| Phase 2 ABSA | M2 | **重写**：加 gold set、LoRA 微调、HotelRec 外部验证 |
| Phase 3 表征 | M3 / C2 | 保留，加贝叶斯收缩与竞争集内标准化 |
| Phase 4 Tourist | M5 | **换标签**：从「评分」改为「需求份额增量」 |
| Phase 5 Manager | M4 / C3 | **升级**：从描述性诊断改为因果处方 |
| Phase 6 评测 | Part 6 | **大幅扩展**：加 T1/T2、event study、placebo、Policy Value、人工校准 |
| Phase 7 写作 | S6 | 保留 |

## 附录 B · 论文结构建议（RecSys 格式，9 页正文）

1. **Introduction**（1 页）：动机 → 三个缺口 → 四个贡献 → 结果预告
2. **Related Work**（0.75 页）：五条线索各一段，最后一段专门对比 WSDM'22
3. **Problem Formulation**（0.75 页）：形式化定义 comp set、CRR、处方问题
4. **Method**（2.5 页）：M1 → M2 → M3 → M4 → M5，配一张系统图
5. **Experimental Setup**（1 页）：三数据集、时序切分、基线、指标
6. **Results**（2.5 页）：
   6.1 竞争集证伪（T1/T2 表 + 图）
   6.2 Tourist 排序（主表 + 消融）
   6.3 因果效应（event study 图 + placebo 表）
   6.4 处方策略价值（主卖点表）
   6.5 双视角耦合（H1）
   6.6 人工评估
7. **Discussion & Limitations**（0.5 页）：价格代理、地域偏差、观测数据的因果局限
8. **Conclusion**（0.25 页）

