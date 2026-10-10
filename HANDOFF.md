# FYP1 接手说明

更新：2026-09-14。建议阅读顺序：README → 本文件 → AGENTS。当前是 **Track B / WORKING_PAPER_ONLY / Demo DESCRIPTIVE**。

## 1. 科研到底在做什么

问题是：酒店经理面对大量评论，应先处理什么？输入是历史住客评论、日期、酒店坐标和评分；输出是方面测量、附近酒店差距、建议与证据不足提示。网站只是观察和演示这些结果的窗口。

基础测量按关键词识别七个方面，正负栏目提供弱标签；按酒店和完整季度汇总，进行贝叶斯收缩，避免少数评论造成极端判断。未提及不等于中性。附近参照使用同城市地理近邻，不代表经过验证的经济竞争对手。离线 ABSA 用于测量诊断，当前 Demo 并不是把每条评论实时交给大模型。

共享策略位于 `src/recommendation/scoring.py`：评价最差优先、附近差距最大优先、差评最多优先、综合差距/差评比例/评论数量，以及研究中的可靠性策略。综合权重 0.45/0.35/0.20 是设计选择，未证明最优。行动排除“位置”，方面至少 5 次提及、可靠性至少 0.3；涉及附近比较需至少 2 家有测量依据的参照酒店。没有合格方面就不给建议。情景滑块是模拟假设，不是收益预测。

## 2. 已经做了什么

| 交付 | 当前事实 | 证据 |
|---|---|---|
| 完整 Demo | 源面板 1,493 家，2017Q2 有数据 1,487 家，6 家当季缺失；1,223 家可展示，264 家排除（247 评论不足、17 缺坐标） | `outputs/demo/research_snapshot.json` |
| 同一套算法 | 网页和研究共用实现；7,435 次酒店/策略选择对比无差异 | `outputs/demo/policy_parity.json` |
| 描述性策略评估 | 四策略各对 1,222 家给建议、1 家弃权；共同集合 1,222 家，记录覆盖、约束违反和策略分歧 | `outputs/demo/policy_evaluation.json` |
| 双语界面 | 深色、中文/English、按稳定酒店 ID 选择；排除原因和弃权说明可见；快照固定配置，避免运行时漂移 | `demo/` |
| 模型诊断标注 | 210 项，Grok/Claude 原始一致率 92.38%；Codex 审查 54 项，保留 202、未决 8 | [标注报告](outputs/autonomous/model_annotation/REPORT.md) |
| 复现保护 | 锁定依赖；CSV/模型哈希；新输出目录；断点指纹；失败不冒充成功；完整统计与截图独立开关 | `run_research.py`、`docs/ASSETS.json` |

这些是工程与描述性结果，**不是准确率、因果或商业有效性证明**。已保存科研结果来自此前实验：515,738 条评论、456 个严格变化事件；预测误差 0.370384 → 0.369371，差值区间跨零。不要写“方法显著更好”。权威数字与声明范围分别见 [FACTS](outputs/autonomous/FACTS.json)、[CLAIMS_LEDGER](outputs/autonomous/CLAIMS_LEDGER.md)。今晚的新运行单独记录，不覆盖旧结果。

## 3. 今晚验收与执行证据

功能提交：`23cd463`。Cursor Composer 2.5 实现共享算法、转换、UI、ABSA 路径；Luna max 实现描述性评价和复现保护；Codex 独立审计、退回修复、集成。

- 整体 236 项 unittest 通过；随后新增 NEXT 续跑模式回归，复现专项 16 项通过。
- 隔离 `--small-fixture --verify-only` 的 Wave 0–10 全部通过，不代表全量统计实验通过。
- 24 组双语×六城市×两情景强度 AppTest 通过；浏览器检查桌面、窄屏、切换选项与真实弃权酒店。
- 新 Python 3.12.3 环境安装研究及 Demo 依赖成功，`pip check` 无冲突。
- 原始 CSV 和离线模型已打包、逐项哈希核验。全新 GitHub clone 和全新研究/Demo环境通过237项测试；精简及续跑保护追加后本地主目录238项测试、小样本Wave0–10再次通过。

## 4. 同事从零复现

### A. 克隆与轻量验收

```bash
git clone https://github.com/bowenx1125/hotel-dual-recsys.git
cd hotel-dual-recsys
python3.12 -m venv .venv-fyp
.venv-fyp/bin/python -m pip install -r requirements-research.txt
.venv-fyp/bin/python -m unittest discover -s tests -v
.venv-fyp/bin/python run_research.py --small-fixture --verify-only
```

私有仓库需要项目拥有者已授予 GitHub 访问权。Demo 启动见 README。小样本产物位于 `outputs/autonomous/fixtures/`，不能与正式结果混用。

### B. 恢复 GitHub 之外的资产

项目拥有者本机已准备 `Documents/FYP1-handoff-assets-20260914.tar.gz`（675,753,800 bytes，约 644 MiB）。包含原始 CSV 与离线 ABSA 模型/分词器，不含环境、账户凭证或私有模型标注答案。需要由拥有者另行交给同事，GitHub 不能替代它。

在仓库根目录解压前核对 SHA256：

```bash
shasum -a 256 /path/to/FYP1-handoff-assets-20260914.tar.gz
# 7dd7940ef05a63ef604e0dd3b41b5454863ac264b97f4fe83967d1f8f4b6dfb9
tar -xzf /path/to/FYP1-handoff-assets-20260914.tar.gz
.venv-fyp/bin/python scripts/verify_reproduction_assets.py --root "$PWD"
```

所有文件预期路径、大小和哈希见 [ASSETS.json](docs/ASSETS.json)。CSV 的公开来源也在该清单；模型源在本次检查返回 HTTP 401，因此不假定同事可以直接在线下载。私有逐项标注不是全量 Wave 0–10 的前置输入；若要重复模型标注，另按 [模型协议](docs/MODEL_ANNOTATION_PROTOCOL.md)生成新独立样本并保留私有记录。

### C. 完整研究与断点续跑

```bash
python3.12 -m venv .venv-absa
.venv-absa/bin/python -m pip install -r requirements-absa.txt
HF_HUB_OFFLINE=1 .venv-fyp/bin/python run_research.py \
  --output-root outputs/runs/reproduce-01 --skip-ui
```

输出目录必须是新的。默认运行 Wave 0–10：历史只读审计 → 原始评论面板/ABSA → 严格事件 → 附近参照 → 时间预测 → 事件描述 → 共享建议 → 敏感性/负结果 → 论文 → 对抗审查 → 最终报告。原始评论会在本地读取，公开结果不得含原文。

`--skip-ui` 只跳过截图，不减少 100 次参照随机化、1,000 次 bootstrap 或 2,000 次后验抽样；`--verify-only` 是轻量检查，不能用于完整科研验收。首次完整运行可能较慢，终端按阶段显示进度。中断后原配置、输入和模式不变才能续跑：

```bash
HF_HUB_OFFLINE=1 .venv-fyp/bin/python run_research.py \
  --output-root outputs/runs/reproduce-01 --skip-ui --resume
```

使用输出内 `NEXT.md` 的续跑命令。配置或输入改变时新建运行目录，不覆盖旧结论。可用 `FYP_DATA_CACHE_ROOT`、`FYP_PRIVATE_MODEL_ROOT` 指向外部资产；模型解释器可用 `FYP_ABSA_PYTHON` 指定。

### D. 从新结果重建 Demo 并验收

```bash
.venv-fyp/bin/python scripts/build_research_demo.py \
  --panel outputs/runs/reproduce-01/hotel_aspect_quarter_v2.parquet \
  --peers outputs/runs/reproduce-01/geo_reference_sets_v2.parquet \
  --output outputs/runs/reproduce-01/demo_snapshot.json
.venv-fyp/bin/python scripts/evaluate_recommendations.py \
  --snapshot outputs/runs/reproduce-01/demo_snapshot.json \
  --output outputs/runs/reproduce-01/policy_evaluation.json
```

先核查时期、酒店数、排除/缺失账目、输入哈希及配置，再经协调者审计更新 `outputs/demo/research_snapshot.json`（构建器需显式 `--overwrite`）。重启 Demo 后检查普通案例 Hotel Arena 和证据不足案例 Villa Eugenie Paris；切换语言不应改变酒店和建议。完整结果验收需检查每个阶段状态、指标、区间、负结果及声明限制，不能只看程序退出码。

## 5. 接下来做什么，为什么

1. **先复现**：跑上述完整流程，与保存的 FACTS 按字段比较；记录环境、输入、运行配置和差异，不静默覆盖。新 Wave 6 覆盖与旧策略表不同是已知实现变化。
2. **固定最终评测方案**：210 项是已看过的诊断集。新测量测试集应与开发集按酒店隔离，检查近重复和抽样偏差；报告相对模型参考的 Macro-F1、混淆表、保留率和未决分布，不能称人工准确率。
3. **公平比较与消融**：在相同酒店、时期和可用信息上，分别移除附近参照、可操作性、可靠性和弃权；报告覆盖、错误/分歧风险和稳定性及酒店聚类区间。不可用本方法自定评分证明本方法优越。现有零约束违反只是规则执行正确。
4. **写论文**：用真实结果更新草稿，保留无提升的实验。待验证贡献是把附近比较、行动约束、可靠性与弃权结合到酒店经理建议；组件本身是已有方法，尚未完成系统文献查重，不写“首创”。
5. **未来扩展**：游客排序、真实经理采纳及业务效果，需要另外的数据和实验，今晚范围不包含这些成果。

项目负责人无需逐条填 label。你需要向同事/导师说明研究问题、比较标准和局限，并提供学校格式、截止日期及导师反馈；这些真实要求不能由 agent 猜测。网页人工查看主要回答“文字是否理解、建议是否有用”，不能替代科研评测。

## 6. 协作与精简记录

任务登记格式：ID / 目标 / 起始提交 / 负责人 / 可写文件 / 禁止项 / 依赖 / 验收命令 / 状态。状态由协调者推进 PLANNED → IN_PROGRESS → REVIEW → DONE，失败退回同一任务修复。

- NIGHT-005：DONE。共享算法、完整 Demo、描述性评价，经Codex审计验收；功能CI34773228100与精简CI34773710930均通过。
- NIGHT-006：DONE。资产、真实全量复现、防覆盖、交接精简已验收；仅最终验收记录的文档提交随后同步。
- 以前 001–004 的实现/审计记录保留于 Git 历史，不再要求新同事通读。

本次将旧 PROJECT_STATUS、PROJECT_GUIDE、RESEARCH_PLAN、任务长日志与整理说明合并到本文件。保留必要模型协议、科研 FACTS/声明/负结果和仍被读取的历史资产；清理后的精确文件差异可从 Git 提交查看。今后只在本文件维护进展和任务，不再创建重复“最新报告”。

精简范围：删除 7 份重复/过时入口文档、5 个旧审计/静态演示脚本、6 个旧爬取/方面/分组构建脚本和 4 个旧 Office/Node 生成文件，以及不再使用的旧论文制图脚本和5张旧图。历史 Office 成品和科研输入保留；旧 Office 自动重生成已退出维护。当前科学与兼容测试依赖未删除。

最近额度检查：2026-09-14 02:04（中国时间），Codex CLI 核心窗口剩余39%；未触发30%阈值，已主动进入验收与精简收尾。

## 7. 完整复现实验验收补记

从 GitHub 克隆的功能提交23cd463，以新Python3.12.3研究/Demo环境及核验后的交接资产，实际完整运行Wave0–10，退出0。ABSA使用本机现有已验证的`.venv-absa`，不是全新安装ABSA环境；离线执行2800项，弱标签一致率84.6071%，零执行失败。科研参数保持100次参照随机化、1000次bootstrap及2000次后验抽样，截图显式跳过；真实UI另行验收。

新面板和附近酒店parquet与已保存文件逐值、类型完全一致；Wave2/3/4/5/7/9及最终结论逐字段一致。456严格事件、预测误差及跨零区间均复现；新Wave6改为共享算法和1487家覆盖。结论仍为WORKING_PAPER_ONLY。汇总证据见[reproduction_acceptance.json](outputs/demo/reproduction_acceptance.json)。完整本地运行保留于`outputs/runs/overnight-validation-20260914/`，包含私有中间材料，不提交；此目录是已完成结果副本，不用于原路径续跑。

该全量运行后的代码变化仅增加temporal配置的resume指纹保护和清理无调用旧文件；未重跑相同全量模型与统计。精简代码提交6e2c1be的GitHub CI已通过；该提交在独立GitHub克隆和新环境中再跑238项测试、Wave0–10小样本与中英文AppTest，全部通过。其后只更新验收记录，不改变代码或科研结果。

最终验收：[6e2c1be research-smoke](https://github.com/bowenx1125/hotel-dual-recsys/actions/runs/34773710930)成功。唯一远端分支main，Desktop唯一主目录FYP1；本任务临时worktree已清除，实施归档与验收日志在拥有者本机Documents/FYP1-agent-work/overnight-20260914。

## 8. P1/P2 效应估计进展（2026-09-14，未提交）

任务：为"证明增加酒店收益"补上可信的效应证据链。起始提交 `378981c`，环境 `.venv-fyp`。

**P1 基线冻结**：`outputs/autonomous/baseline/BASELINE.json`。冻结 9 个产物哈希、算法权重（gap .45 / criticism .35 / unreliable .20，设计选择非学习得到）、面板统计，并把现有效应估计连同缺陷一并记录：Wave5 用池化 `smoothed_net` 当结果变量，而事件按折检测，属自指；违反 `conf/autonomous_research.json` 的 `crossfit.rule`（detect_on_one_fold_measure_outcome_on_the_other）。P3 验收标准写入基线：必须超过 P2 折外效应，禁止降门槛。

**P2a 分折因变量**：面板只有池化 `mean_reviewer_score`，无法执行折外测量。按 `sha1(review_fingerprint) % 2` 重扫 515,738 行 CSV 生成 `data/processed/hotel_quarter_fold.parquet`。校验：与已发布面板 0 条不匹配，池化均分最大偏差 2.3e-14，折 A/B = 258244/257494。

**P2b 交叉折连续处理**：`outputs/autonomous/p2/effect_estimates.json`。处理取检测折 F 的方面情感，结果取另一折 G 的评分，双向固定效应 + 酒店聚类稳健标准误，A→B 与 B→A 分别估计后取均值。四个时序：

- 滞后·差分 −0.034 (p=0.13)；同期·差分 +0.101 (p=3.1e-7)；滞后·水平 +0.057 (p=0.0025)；同期·水平 +0.187 (p=7.5e-27)
- 同折（机械耦合）对照为 −0.377 / +0.755 / −0.072 / +0.834，是交叉折的 4.5–11 倍，滞后·水平符号翻转——量化了 Wave5 的自指偏差
- 置换检验 sd 0.0247 与解析 se 0.0224 吻合，标准误标定正确
- 分方面：service +0.191 (p=7.5e-6) 最强，breakfast +0.060 (p=0.099) 最弱

**P2c 匹配 DiD 对照**：`outputs/autonomous/p2/event_study_p2c.json`。同一匹配跑两臂，唯一差别是结果序列。Wave5 池化臂逐位复现 0.16971589236138307（p=5.7e-38）且效应不衰减；折外评分臂 k=0 为 +0.1139 (p=0.0019)，k=−2 平行趋势 −0.0219 (p=0.55)，k=1/k=2 衰减且不显著。

**结论（AMBER_ASSOCIATIONAL，不升级）**：方面口碑与其他客人评分**同步**关联稳健（两个独立设计互相印证），但**领先效应为负结果**——"改善方面 X 会提升下季度评分"无证据。仍无价格、间夜、成本字段，`no_roi`/`no_demand_lift` 维持 True。location 阴性对照在同期·水平下 p=0.046 边际显著，作为阴性对照偏弱（客人对位置的评价随整体满意度波动），已如实记录。

**验证**：新增 `tests/test_effect_estimation.py` 9 项全通过；全量 247 项测试 245 通过，2 项失败为此前已确认的环境问题（泄漏扫描自指误报、Windows 路径分隔符），无新增回归。P2b 连跑两次逐位一致。修复真实 bug：`cluster_robust_mean` 分母误写为 G·√(G−1)，标准误偏小 √n 倍，已补回归测试。

**待办**：P3 算法优化（以折外效应为靶标，先做 P4 离线策略评估再报增益）；P5 收益折算需要外部价格弹性假设；location 阴性对照偏弱需在论文中说明。

## 9. P4 离线策略评估（已完成，2026-09-14）

**方法边界**：本项目无日志策略，`wave6/policy.json` 记录 `no_ips_snips: true`，R1 P2 明令「不得把离线评估包装成 IPS/SNIPS」。因此 P4 采用**直接法（结果回归）+ 交叉拟合**，不需要倾向性得分。状态也做了折分离（`src/effect/ope.py::fold_panel`），把结果折的评论从策略输入中剔除。

**结论（AMBER_NO_DISCRIMINATION）**：

- 前瞻规格（决策相关）：七个方面的 γ 全部不显著（|t| ≤ 1.39）；分样本 best−worst gap **0.0260** 对置换安慰剂 gap **0.0216**，**比值仅 1.20** —— 该 gap 主要是 6 个噪声系数取极值的次序统计偏误，协议无区分力。
- 现行策略 `peer_relative` 与随机挑方面**无法区分**（+0.0004 分，t=0.24；bootstrap t=0.17）。
- 同期规格（描述性）：service γ=+0.1917（t=3.20）独立复现 P2 的 +0.191；oracle 超随机 +0.0179（t=2.65 / bootstrap 2.80）显著；「总推 service」优于现行 +0.0175 但 bootstrap 下不稳健（t 由 2.45 降至 1.56）。
- 阴性对照与质量：location-as-action 违规率 **0.000**；交叉拟合与全样本最大价值差 0.00017；弃权率 3.8%–4.1%；min_mentions 敏感度为零结果（`min_reliability=0.3` 配 k=10 已隐含 n≥5，min_mentions 非绑定）。

**P4b 预测探针**：折分离后季度评分变化不可预测（R²≈0.0010）；池化状态 R²=0.0445，**机械膨胀 +0.0435，即 98% 的表观预测力来自同一批评论的重叠**；酒店横截面（折A 方面画像 → 折B 评分水平）**R²=0.4490、r=0.670**（n=1300）。

**对 P3 的含义**：唯一可评估且有信号的目标是**横截面评分水平**（学习方面价值向量，把 `weights_are_design_choices: True` 变为 False），而非季度变化（噪声）或收益（无数据）。现行排序缺「方面专属价值系数」，service 的 γ 显著高于其余方面是结构性缺失项。验收口径：必须折分离 + 酒店外样本 + 报告相对置换安慰剂的倍数。

**验证**：新增 `tests/test_effect_ope.py` 8 项全通过；全量 **255 项测试 253 通过**，2 项失败仍为此前已确认的环境问题，无新增回归。修复 bug：`clustered_fe_ols` 在 `cell_col == cluster_col` 时重复选列导致 `Grouper ... not 1-dimensional`，已在估计器内去重并补回归测试。

**待办**：P3（以横截面水平为靶标，权重由拟合得到）；P5 收益折算需外部价格弹性；覆盖率 53%（单元要求 7 个方面在连续两季、单一折上均有提及）需在论文中说明。

## 10. P3 方面价值向量与价值感知排序（已完成，2026-09-15）

**靶标**（来自 P4b）：酒店横截面——折 A 的方面画像 → 折 B 的评分水平，这是唯一有可迁移信号的估计目标。回归式 `y_i = c + Σ_a v_a·x_{i,a}`（fold-pure，状态与结果互斥），得到「1 SD 方面情感 = 多少评分点」。

**Q1 真实吗：REAL_AND_STABLE。** 折外 CV R² **0.4413**（A→B）/ 0.4601（B→A）；打乱标签 placebo R² −0.0015 / −0.0048，**比值 304 / 97**；n = 1300 / 1292。系数（评分点/SD，A→B，bootstrap 300）：room **+0.2786**(t=15.27)、service **+0.2599**(13.56)、noise +0.0814(5.89)、value +0.0004(−0.02)、breakfast −0.0102(−0.89)、cleanliness **−0.0814**(−5.34)、location −0.0564(−2.67，不可行动)。

**Q2 迁移：能。** 两个不相交酒店半区估出的 v，在 6 个可行动方面上相关性 **0.982**（sd 0.010，40 次重复 100% 为正）。

**Q3 策略实验（⚠️ 近同义反复，勿引用其绝对值）**：奖励定义为「被选中方面的 v 值」，故 `value_aware` 赢 `peer_relative`/`random` 是定义必然。唯一不循环的是 `placebo_permuted_v`（同权重、打乱方面）：`value_aware − placebo = +0.895`（t=10.50，98% 重复为正），placebo 比值 **2.31**。与现役策略一致率 **59.2%** ⇒ **40.8% 的推荐会改变**。

**Q3b 唯一碰真实评分的测试**（只用选中方面预测未见酒店的评分）：条件规格 R² **0.0762**，打乱向量 0.0580（差 +0.018，t=1.94，60% 为正），随机参照 0.0441，现役最大缺口 0.0149，oracle 上界 0.3341。**设计修正**：第一版只对比 `random_uniform` 时出现「随机比现役好」的假象——随机器是六方面混合、继承了平均斜率，而最大缺口永远挑极端低值、被噪声主导。已改为以 `placebo_permuted_v` 为公平地板，并补 3 项测试锁定（`SingleAspectProbeTests`）。

**Q4 决定性复核（P4 直接法重跑，交叉拟合 v）：收益没动。** 四种配置（A→B/B→A × forward/contemp）下 `value_aware − peer_relative` = −0.00021 / −0.00483 / +0.00434 / +0.00257 评分点，**全部 |t| ≤ 0.95**；一致率 0.482–0.490（一半以上推荐变了但收益差连符号都不定）；检测阈值约 0.013 评分点，**无任何效应接近**。完全复现 P4 的 `AMBER_NO_DISCRIMINATION`。

**规格分歧（必须写进论文）**：条件（多变量）与边缘（单变量）系数在 cleanliness（−0.0814 vs +0.1801）、location（−0.0564 vs +0.0196）、breakfast（−0.0102 vs +0.0470）上**符号相反**。设计矩阵条件数 3.1、最大非对角相关 0.589，共线性轻微，**非数值假象**——是信号被 room/service 吸收。无干预数据则不可判定。**选条件规格**，理由可证伪：只有它在 Q3b 上同时赢过打乱向量与随机参照；边缘向量归一化后太平（room 1.97 → cleanliness 1.00），几乎不改变选择。该选择已写入 `value_vector.json` 的 `recommended_spec`。

**交付与开关**：新增 `src/effect/learn_value.py`、`src/effect/run_p3.py`、`src/recommendation/value_policy.py`、`tests/test_effect_p3.py`（**24 项全通过**，含 7 项与现役策略逐位一致的 parity 测试）；改动 `scoring.py`（opt-in 钩子）、`conf/demo.json`（`use_learned_value_vector: false`）、`ope.py`（支持 `value_by_hotel`）。**默认关闭，Demo 行为逐字节不变**——v 是估计量，带自己的 n/R²/placebo/稳定性，不得混入 `conf/` 冒充设计常量。产物：`outputs/autonomous/p3/{p3_values.json, P3.md, value_vector.json}`。

**结论与出路**：P3 拿到了真实、可迁移、可解释的价值向量，把排序从等权启发式升级为数据驱动，并发现现役推荐有近一半在「哪个方面更值钱」上是错的；但**「增加酒店收益」仍无证据，且按当前路线拿不到**——瓶颈不在排序而在奖励侧（任何两策略的回报差都小于检测阈值）。三条出路：A 换 estimand 为「推荐的是经理会采纳且采纳后收益最高的动作」（需真实干预记录，是唯一能兑现原始目标的路径）；B 改奖励模型为预订/价格（需 ADR 与价格弹性，即「收益=推算」的上限）；C 定位为可解释性与决策一致性贡献，把 P1–P4 的零结果本身作为贡献。**需外部数据，待决定。**

**待办**：P5 收益折算（需外部价格弹性 / ADR）；论文须披露 53% 覆盖率、location 负对照偏弱、Direct Method 的模型依赖、条件/边缘规格分歧不可判定；**改动全部未提交，提交时机由负责人决定。**

## 11. P5-A 揭示性干预与样本量要求（已完成，2026-09-15）

**路线选择**：负责人选 **A**——把靶标换成「推荐的是经理会采纳、且采纳后能提收益的动作」。

**先做的可识别性审计（结论：缺的不是估计量，是数据）**：因果链 `策略 → 推荐动作 → 经理是否采纳？ → 整改 → 评分回升 → 需求上升 → 收益上升`，中间三个问号在数据集里**一个都观测不到**。原始 Booking 评论只有 17 列，无任何管理侧或收益字段。曾尝试用爬取价格补：，`data/processed/hotels_all.csv` 821 行、321 行有价（EUR 中位数 129），但**全是比利时城市**，面板城市是 Paris/London/Barcelona/Milan/Vienna/Amsterdam，→ **交集为空集**。ID 映射本身是通的（`hotel_id = 'd1_europe:' + legacy[:12]`，1493/1493 匹配），缺的是那张表。ADR 129 只当**量级锚点**，未连接、不参与任何估计。

**能估的最近替代 = 揭示性干预事件研究**（新增 `src/effect/interventions.py`）：把「评论里持续性的方面情感跃迁」当作干预的揭示性代理——`net_a^D[t] − net_a^D[t−1] ≥ τ` 且 `net_a^D[t+1] − net_a^D[t−1] ≥ τ·persist_frac`；在检测折识别、在互斥折测结果（A→B 与 B→A 都跑）；对照 = 同酒店-季度任何方面都无事件者；三期可靠性下限 0.30。**全程直接法（DID + 结果回归），未碰 IPS/SNIPS**（规则 R1 P2 禁止，且无记录策略即无倾向性得分）。τ=0.25 下 **1607 事件 / 800 家酒店 / 9632 酒店-季度**。

**判定：`IMPROVEMENT_PAYS_REPLICATED_ACROSS_FOLDS__SPECIFICITY_DIRECTION_DEPENDENT`。** 关键设计是把结论**拆成两条独立主张，各自要求跨折复现**——因为两个方向真实地给出了不同答案：

| 主张 | A→B | B→A | 判定 |
|---|---|---|---|
| 改进有回报（合并 ATT） | +0.0656 (t=3.46)，前趋势 t=−0.94 | +0.0652 (t=3.43)，前趋势 t=−2.11 | **跨折复现** |
| 方面间差距 vs placebo | 0.1152/0.1119，比值 1.029，p=0.402 | 0.2035/0.1092，比值 1.863，p=0.008 | **方向依赖** |
| 点名的方面 | cleanliness | value | 不一致 |

A→B 差距与随机置换 placebo 等大（次序统计量膨胀）；B→A 虽过 placebo，但**该方向前趋势 t=−2.11 未通过**——事件前这些酒店已在动，那部分是均值回归。**故不采纳任何「X 方面最值钱」的表述。** τ 敏感性：合并效应稳健（t=2.57–4.45），但最佳方面比值 1.34/1.04/1.18/0.66 乱跳、被点名方面来回翻转 → 效应稳、**排序根本没识别出来**。支撑项两个方向一致：事件确实是方面特异的（+0.0386 t=8.23 / +0.0407 t=8.44）；恶化臂符号相反（−0.0118 / −0.0461）。

**Q3 迁移：不能。** 交叉拟合下 `V(value_aware) − V(peer_relative)` = +0.0209（se 0.0032，92% 为正），但打乱 γ 的零分布 sd 0.0271 → **z=0.753, p=0.227, NO_TRANSFER**。合理：P3 的 v 估的是**水平**，这里 γ 是**变化**，两个不同估计目标，不得混用。

**Q4 功效/MDE**：σ=0.909 评分点/酒店-季度，当前每方面中位事件 227 → **MDE 0.171 评分点**。要检出 0.02/0.05/0.10/0.20/0.50 评分点，需每方面 32,437 / 5,190 / 1,298 / 325 / 52 条记录（6 个可行动方面合计 194,622 / 31,140 / 7,788 / 1,950 / 312）。**这张表把「我们需要干预记录」变成了「我们需要 N 条」**——可直接用于谈数据或写 limitation。收益折算（ADR 129 锚点，弹性为外部假设）：MDE 相当于 1%/2%/5% 弹性下的 0.171% / 0.343% / 0.857% 收益。

**能对外说的**：① 持续性改进后评分回升约 +0.065 点（t≈3.4，双折复现）；② 事件是方面特异的（t≈8.2+）；③ 可辩护的推荐逻辑是「对最薄弱、测量可靠的方面行动」；④ 判定方面间差异需要约 N 条干预记录。**不能说的**：任何「X 方面回报最高」、任何「本系统提升收益」、任何把 ADR 129 参与计算的收益数字、任何 IPS/SNIPS 包装。**注意现役 peer-relative 排序实现的正是第 ③ 条**——本轮产物不是新算法，而是**给现役算法补上此前没有的正当性证明，并划清它不能主张的边界**。

**要兑现原始目标还缺**（按优先级）：① 干预/采纳日志（最小集 `hotel_id, action_aspect, action_date, adopted`）——决定性；② 收益序列 `ADR, occupancy/RevPAR`；③ 至少要有面板城市的价格（当前比利时样本用不上）。

**交付**：新增 `src/effect/interventions.py`、`src/effect/run_p5a.py`、`tests/test_effect_p5a.py`（**14 项全通过**，含注入效应恢复、零效应、前趋势为 0、特异性、功效表）；产物 `outputs/autonomous/p5a/{p5a.json, P5A.md}` + 详细报告 `docs/fyp1/FYP1_P5A_揭示性干预与样本量要求.md`；wave 14 已合并进 `FACTS.json`、`experiments.jsonl` 已登记。**未改动任何现役算法或 Demo 配置，本轮纯测量。**
**全量测试 293 项：2 项失败，均为 P5-A 之前就存在的环境类问题**（`test_no_leakage` 扫描到自身源码里的密钥标记串，属自指误报；`test_next_resume_command_preserves_mode_flags` 在 Git Bash 下的 `\` vs `/` 路径分隔符比较）。`tests/test_effect_p5a.py` 14/14 通过。

**待办**：P5 收益折算仍阻塞（需外部价格弹性 / ADR）；论文须披露 53% 覆盖率、location 负对照偏弱、Direct Method 的模型依赖、条件/边缘规格分歧、**以及本轮的方面排序方向依赖**；**改动全部未提交，提交时机由负责人决定。**
