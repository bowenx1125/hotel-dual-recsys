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
