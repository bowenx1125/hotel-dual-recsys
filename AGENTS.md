# AGENTS.md — FYP1 shared agent contract

适用整个仓库，供 Cursor、Codex、Claude 及其他 agent 共同遵守。用户当前指令优先；目录内更具体的 AGENTS.md 只细化本目录工作，不能放宽数据与科研约束。

## 1. 开工顺序与事实来源

1. 每次新任务与审计返工均先读本文件、README.md、PROJECT_STATUS.md、docs/AGENT_TASKS.md 当前任务（用户再次强调）。协调者的 Cursor 编码派单必须显式写出先读 AGENTS.md；标注角色使用隔离工作区内的同名精简角色规范，不接触编码上下文或其他模型答案。
2. 核对工作目录、git status、HEAD 和已有改动，再读所负责模块。不能假定磁盘上的文件都已提交。
3. 当前数字以 outputs/autonomous/FACTS.json 为准，声明范围以同目录 CLAIMS_LEDGER.md 为准。outputs/overnight 是历史对照，不得作为最新结论。
4. 当前状态 Track B / WORKING_PAPER_ONLY，Demo DESCRIPTIVE。游客排序、人工 gold 和真实业务收益验证未完成；工程测试通过不能升级科学结论。

## 2. 工具与责任分工（用户 2026-09-13 决定）

- 优先用 Cursor CLI 承担明确范围的代码实现、修复和测试，优先利用用户现有订阅额度。Codex 负责结构化方案、分解任务、独立审计与集成；未经审计的实现不能标成验收通过。
- 使用当前登录账户；默认沿用既有模型，协调者可按具体任务从账户已提供的模型中选择并登记，避免无产出的长时间推理。不擅自启用额外付费、购买额度或切换收费提供商。额度不足或登录失效时报告实际状态，不声称知道剩余量，不靠无意义循环消耗额度。
- “还有一个月额度”不是永久状态或无限后台运行授权。只完成有明确目标与验收条件的工作包；持续沿用 Cursor 优先偏好，直到用户改变，额度可用性每次按实际错误判断。
- 首选本机 Cursor CLI。若工具不能完成必要工作，记录失败原因与替代路径，不把其他工具的实现冒充 Cursor 产物。编码 agent 仍只使用字段定义和合成样本。用户 2026-09-13 另行授权模型标注：仅标注角色可通过 Cursor 接收最少必要的评论片段与不透明 ID/方面；Grok 初标、不同模型盲审、Codex 分层抽查，不要求人类核验。用户授权 Codex 对分歧作最终裁决，记录原文依据；证据含糊可保留不确定。隐藏酒店身份、评分、原正负栏目及其他模型答案；原文与调用日志只存私有目录。

## 3. 多 agent 协作

协调者先登记任务，再派发实现。每个任务必须有：任务 ID、目标、基线提交、负责人、可写文件、禁止修改项、依赖、验收命令、状态。模板与当前任务见 docs/AGENT_TASKS.md。

- 一个文件同一时间只有一个写入者。涉及共享配置、接口或 schema 时，由协调者串行集成。
- agent 不是独自在仓库工作：禁止覆盖、回滚或清理其他人的修改；遇到变化先协调归属，再更新实现。
- 可并行的工作：互不依赖的模块、测试、只读审计。不能为了并行把相互依赖的编辑同时发给多个 agent。
- 主目录 Desktop/FYP1 与远端保持 main。确需隔离时，在 Desktop 之外创建短期 detached worktree，或按需使用 codex/<task> 临时分支；不主动增加远端分支或 Desktop 副本。集成后只删除本任务的临时资源，先确认成果已保留。
- Worker 不自行 commit、push、merge、删除分支、修改 GitHub 设置；这些由协调者在用户已授权范围内完成。协调者遇到未授权的额外外部动作时才请求确认，不重复询问已有授权。
- 任务状态用 PLANNED → IN_PROGRESS → REVIEW → DONE，或 BLOCKED。Worker 不能独立把自己的任务从 REVIEW 标成 DONE。

## 4. 任务完成交接

交接必须写明：改变了什么及为什么；具体文件；实际跑过的命令与退出结果；未跑项目；风险与剩余问题；输出是否包含真实数据。不能只写“已完成/已测试”。不得伪造用户反馈、人工标签或验证结论。

协调者审计：范围与差异 → 数据/路径与科研边界 → 必要测试 → 与当前 main 集成 → 已授权的提交推送 → 对应提交 CI → 检查远端与本地一致。发现问题退回同一任务修复，不并行重复改同一文件。

## 5. 环境、入口与验证

- 研究：.venv-fyp/bin/python；依赖 requirements-research.txt。
- 演示：.venv-demo/bin/python；依赖 requirements-demo.txt。
- 离线模型：.venv-absa 与 models/absa；设 HF_HUB_OFFLINE=1，不默认在线下载。
- 研究入口 run_research.py。缓存默认为 data/cache，可用 FYP_DATA_CACHE_ROOT 覆盖。
- 基础验证：`.venv-fyp/bin/python -m unittest discover -s tests -v`。
- 研究链路变更追加：`.venv-fyp/bin/python run_research.py --small-fixture --verify-only`，输出必须留在 fixtures 隔离目录。纯文档修改只做链接、路径和内容核对；不为低风险排版改动新增测试。
- 现有 smoke test 会重建 outputs/night_demo/demo_snapshot.json；审计时保存原字节，测试后只恢复该测试改写的快照，不能广泛 git restore 用户文件。
- 全量爬取、训练、全量模型推理、大规模研究默认交给用户运行；本地轻量数据准备可在任务授权内运行。脚本应支持断点、幂等或明确拒绝覆盖，打印进度但不打印评论和秘密。

## 6. 科研与代码纪律

1. 修改研究前读 conf/autonomous_research.json 对应门槛与 outputs/autonomous/DECISIONS.md；不为显著性降低门槛，保留负结果。
2. 预测/评估按时间切分，排除不完整季度；不能使用含未来信息的全期 Average_Score。A/B 评论折交叉拟合不替代时间切分。
3. 没有提及不等于中性质量；保留缺失标记与可靠性。地理邻居不自动等于经济竞争对手，评论变化不自动等于管理干预。
4. 弱标签一致率不是人工准确率。当前按 docs/MODEL_ANNOTATION_PROTOCOL.md 实施模型独立标注与审计；不称人工 gold、不把模型一致率称真实准确率。旧人工流程保留为可选，不再是当前推进前提。不得隐藏抽样偏差。
5. 方法更优、因果、预订增长和 ROI 各需对应证据；启发式权重、场景滑块与合成测试不能充当真实收益证据。
6. LLM 可按固定规则标注文本和解释结构化数字；统计指标必须由代码计算，不能创造数字。新颖性与引用必须核对原始论文，未核验的主张和投稿日期要标明待核验。
7. 中间研究表优先 parquet，落盘前使用现有 schema 校验。随机种子来自配置，酒店 ID 稳定；正式结论回落到脚本。
8. 新增面向人工的 CSV/表单必须保护原始文本，避免公式注入，记录输入哈希与用途；操作便利不等于统计上已完成验证。

## 7. 文件、隐私和同步边界

- 主进展报告只维护 PROJECT_STATUS.md；README 管启动；当前事实、声明、索引各有唯一来源。不生成根目录 FINAL 副本，不恢复旧研究蓝图。
- 原始评论、data/cache、data/interim、私有标注文本、.env、凭证、虚拟环境、模型权重与本地运行日志不提交。上传代码、配置、无原文的统计结果和文档；“同步文件夹”遵守上述边界。
- GitHub 不是本机全盘备份。Office 历史文件、环境和大模型仍按 .gitignore 本机保留；不能声称克隆仓库就具备所有本地资产。
- 不读取或打印 token、账户配置中的凭证或私人运行信息；评论仅限已授权标注与受控抽查，不在公开报告或常规日志中打印原文。爬取遵守 robots、访问限制，不绕验证码或 bot 检测。
- 删除旧资产前检查运行依赖。禁止未经当前任务授权的 reset --hard、force-push、git clean -fdx 或广泛清空文件。
- 重要决策记入 outputs/decisions.md；执行证据与任务状态记入 docs/AGENT_TASKS.md。用户沟通用中文，区分实现、测试、全量实验和真实业务验收。

## 8. Demo 界面约定（用户 2026-09-13 追加）

- 默认深色，提供中文 / English 切换；中文面向非技术酒店经理，先展示建议与依据，公式、原始字段和审计细节放入展开区。
- UI 设计使用 UI UX Pro Max 与 Web Design Guidelines；本机已安装于 ~/.codex/skills/，源码来自 nextlevelbuilder/ui-ux-pro-max-skill 与 vercel-labs/agent-skills。跨机器若不可用先说明；仓库主题与翻译文件足以运行 Demo。
- 文案在 demo/zh_cn.py 和 demo/en.py，语言选择由 demo/i18n.py 路由，禁止共享可变的全局语言状态。语言切换只改展示，不改酒店 ID、配置、分数或结论。
- 城市/分组采用带语言后缀的控件 key，并用 mgr_city/mgr_cs 保存跨语言选择；修改后必须实际浏览器检查选项文字，不能仅依赖 AppTest。
- 原生 Streamlit 工具栏/图表下载等平台控件可能保留英文，不宣称平台控件全部汉化。
