# HANDOFF · 交接说明（给接手执行的人 / Agent）

## 你拿到的是什么

一个已完成数据层、需要**方法论重构**才能投顶会的酒店推荐研究项目。
四份文档，按这个顺序读：

1. **`CLAUDE.md`** — Agent 守则（5 分钟，必读）
2. **`RESEARCH_MASTER_PLAN.md`** — 研究蓝图（30 分钟，必读 Part 0/1/3）
3. **`CODE_PLAN.md`** — 工程计划（做到哪个 Stage 读哪一节）
4. `BG.md` / `RESEARCH_PLAN.md` — 旧文档，历史参考，**已被上面取代**

## 第一步做什么（不要跳过）

```bash
# 1. 修环境（当前 numpy 2.4.6 与 pandas/sklearn 二进制不兼容，import 直接崩）
python3 -m venv .venv-fyp && source .venv-fyp/bin/activate
pip install -U pip
pip install "numpy>=2.1,<3" pandas pyarrow scikit-learn lightgbm scipy statsmodels linearmodels
pip install torch transformers datasets peft accelerate sentence-transformers geopy tqdm pyyaml python-dotenv
python -c "import numpy,pandas,sklearn,lightgbm,statsmodels; print('env OK')"
```

```bash
# 2. 下载新的主数据集（这是整个重构的地基）
#    515K Hotel Reviews in Europe —— 1,493 家酒店 / 6 城市 / 自带 lat,lng
#    kaggle datasets download -d jiashenliu/515k-hotel-reviews-data-in-europe -p data/raw/d1
```

然后按 `CODE_PLAN.md` §0 → §1 → §2 → §3 逐个 Stage 推进。

## 给 Agent 的启动 prompt（可直接复制）

> 读 `CLAUDE.md`，然后读 `RESEARCH_MASTER_PLAN.md` 的 Part 0、Part 1.4、Part 3、Part 4，
> 再读 `CODE_PLAN.md` 的 §0 和 §1。
> 我们现在从 **Stage S0** 开始：修环境、建新仓库结构、接入 D1（515K Europe 数据集）。
> 规则：每个 Stage 有 Gate，不过 Gate 不许进下一个 Stage；偏离计划的决定写进 `outputs/decisions.md`。
> 长任务（爬取/微调/全量推理）你只写脚本，我自己跑。

## 最重要的三件事（如果只记得住三条）

1. **换数据底盘**：主数据集从"比利时 821 家"换成"515K Europe 6 城市 1,493 家"。
   现在的竞争集只形成了 **1 个有效地理簇**——核心创新点在数据上立不住，这是必须先修的。
2. **换核心命题**：从"你在竞争集里排第 4"（描述）升级到
   "把清洁度提到竞争集第 30 百分位，预计评分 +0.18 [0.07, 0.29]"（**因果处方**）。
   这是论文从"系统 demo"变成"研究贡献"的唯一杠杆。
3. **竞争集 = 对照组**：这是全篇最优雅的一点——同一个构造，产品上是"可比市场"，
   统计上是"匹配对照组"，让 DiD 的平行趋势假设变得可信。


## ★ 执行入口：AUTORUN_SPEC.md

**`AUTORUN_SPEC.md`** 是给 Agent 的可执行规范：40 个 STEP，每步写清【怎么做/为什么/创新点/预期结果】，
全部 Gate 改为**预注册数值阈值 + 自动分支**，人类触点归零（数据走 HuggingFace 公开镜像，无需任何账号；
aspect 验证用三重自动协议替代人工标注）。目标：连续运行约 10 天 → 数据库 + 代码 + 论文全部产出。

启动命令：
```bash
python run.py            # 从 state.json 的断点继续；首次运行从 STEP_00 开始
```

## ★ 时间日历：44 天冲刺

**`SPRINT_44D.md`** 是现在真正在执行的计划：目标 WWW 2027（摘要 2026-10-11，全文 2026-10-18）。
Day 1 就并行开六条工作流；Day 7 用粗糙版 Figure 1 做 Plan A/B/C 的 go-no-go 决策。

## ★ 顶会强度版本

若目标是 A 类主会（不只是"发出去"），先读 **`PAPER_STRATEGY.md`**。
核心命题从"我们做了一个双视角系统"升级为：

> **处方式推荐是 performative 的** —— 给供给方的改进建议，其估计收益会因为建议被采纳而消失，
> 因为竞争集内的质量是相对的。所有现存的供给侧诊断工具都隐含假设回报固定，这个假设是错的。

最关键的单一动作：**2026-10 下旬做出粗糙版 Figure 1**（回报 vs 同集竞争者同向改进数量的下降曲线），
用它决定后面几个月的投入方向。这是整个项目的 go / no-go 点。

## 时间表（倒推 RecSys 2027，截稿 2027-04-25）

| 何时 | 做什么 |
|---|---|
| 2026-09 | S0 数据底盘 + 价格代理 |
| 2026-10 | S1 竞争集与证伪测试；顺手投 **ENTER 2027 working paper（10-11 截稿）** 练兵 |
| 2026-11 | S2 ABSA + 人工 gold set |
| 2026-12 | S3 表征 + Tourist ranker |
| 2027-01 ~ 02 | **S4 因果处方（最重，也是全论文的价值所在）** |
| 2027-03 | S5 评测 + 人工评估 |
| 2027-04 | S6 写作 → 投稿 |

## 不要做的事

- ❌ 不要为了"数据更多"继续爬 Booking（时间花在这上面回报最低，且 P2 的时间错配问题爬多少都解决不了）
- ❌ 不要在没有 gold set 的情况下扩大 ABSA 规模
- ❌ 不要用"高评分=好酒店"当 Tourist 侧的标签（循环论证 + 泄漏）
- ❌ 不要只靠 LLM-as-judge 评 Manager 侧（2025 年文献已证明单用不可靠）
- ❌ 不要跳 Gate
