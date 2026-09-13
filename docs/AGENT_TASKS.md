# Agent task register

规范见 ../AGENTS.md。协调者登记、分配写权限并负责最终 DONE；不把排期当作已经完成。

## Task template

- ID / 目标：
- 基线提交 / 依赖：
- 负责人 / 协调审计者：
- 可写文件 / 不可修改项：
- 验收命令 / 预期证据：
- 状态：PLANNED | IN_PROGRESS | REVIEW | DONE | BLOCKED
- 交接：改变、理由、测试结果、未跑项目、风险、是否涉及真实数据。

## FYP-CURSOR-001 · 人工标注试用表导出

- 目标：把已有私有样本导出为隐藏机器标签的人工填写表，保留第二标注人复核所需重叠样本；不修改研究结论。
- 基线：952d983；输入字段已由协调者核对，现有包 126 项 / 3 城市 / 7 酒店，只作为标注流程试用。
- 实现者：Cursor CLI；方案、审计与集成：Codex。
- 可写：scripts/export_annotation_tasks.py、tests/test_annotation_export.py；仅这两个文件。
- 不可修改：研究估计器、门槛、当前 FACTS、原始数据、现有样本、其他 agent 文件、Git refs/远端。编码 agent 不读取真实评论。
- 验收：合成单元测试；导出不能泄露弱标签/评分，不能覆盖已有目录，防 CSV 公式注入；输入哈希与抽样限制可追溯；协调者再本地试导出、只检查元数据。
- 状态：DONE（协调者完成独立审计与本地真实样本试导出，尚无人填写标签）。

## FYP-COORD-001 · 协作规范与人工推进指南

- 负责人：Codex（与代码任务不共享可写文件）。
- 可写：AGENTS.md、CLAUDE.md、README.md、PROJECT_STATUS.md、docs/AGENT_TASKS.md、docs/PROJECT_GUIDE.md、outputs/decisions.md。
- 目标：统一规则、解释目录与推进步骤，明确 Cursor 优先实现和独立审计；完成用户授权的 main 同步。
- 验收：事实核对、文档链接有效、代码任务审计完成、GitHub 与本地一致且对应 CI 通过。
- 状态：DONE（已同步 main，提交 90fba70 的 GitHub CI 全部通过）。


### FYP-CURSOR-001 执行与审计记录

- Cursor CLI 2026.09.10-fd3934a 已安装并通过用户浏览器授权；独立最小调用成功。不能从登录状态推断余额。
- 两次 Auto 调用在未产出文件时终止：首次纯文本模式缺乏可观察进度，第二次流式模式持续推理超过十分钟。未把它们登记成已完成代码。
- 协调者在当前账户可用模型中选择 Composer 2.5，首次实现约 88 秒完成，12 项自测通过。没有更改付费设置。
- 独立合成审计发现：默认父目录不存在导致首次 CLI 失败；中途写失败留下半成品；并发输出目录创建冲突时可能误删他人目录。已退回 Cursor 修复，并要求新增回归测试、单次读取输入用于哈希与校验。
- 人工样本来源核查：126 项全部可按酒店 ID 和文本匹配原始 CSV，覆盖 3 城市、7 酒店；旧构造器先取前 8,000 个候选，存在覆盖集中，正式验证须重新抽样。只记录聚合审计结果，不上传原文。

- Cursor 修复首轮审计问题后 19 项测试通过；复审发现源 item_id 带正负标签，进一步退回实现不透明导出 ID。最终 21 项专项测试通过。
- 协调者逐文件审查并只导入两份授权代码，亲自运行专项测试及完整 74 项 unittest，均通过。未运行全量研究或模型推理。
- 本机试导出得到 A=126、B=26；空白 label/notes、匿名 ID、两表重叠和文件哈希均核对通过；输入包与研究 FACTS 不变。输出在 gitignored 私有目录，未上传评论原文。
- 实现来源为 Cursor CLI / Composer 2.5；审计与文档为 Codex。实际 CLI 流式日志、退回原因与本地验收日志保留在 Documents/FYP1-agent-work，不提交模型过程日志或评论。

- GitHub 验收：[90fba70 research-smoke](https://github.com/bowenx1125/hotel-dual-recsys/actions/runs/34758568793) 成功，覆盖全部单元测试、隔离小样本研究与泄漏检查。临时 detached worktree 已移除，保留唯一 Desktop/FYP1 和远端 main。


## FYP-CURSOR-002 · Demo 简体中文界面

- 目标：三个页面的界面文案、表头、策略说明、状态与图表中文化，保留真实数值和研究边界。
- 基线：2d86169；实现 Cursor CLI / Composer 2.5，协调审计 Codex。
- 可写：demo/app.py、demo/zh_cn.py；补充依赖范围为 scripts/capture_autonomous_screenshots.py、scripts/capture_live_demo_screenshots.py、src/autonomous/report.py 中仅截图选择器与页面标题。配置、事实文件与科研参数不改。
- 协调者可写：本任务记录、PROJECT_STATUS.md、outputs/decisions.md。
- 验收：既有单元测试、Streamlit AppTest 交互及浏览器核查；历史宽松结果不得翻译成当前确认结论；选择器和滑块结果不变。
- 状态：DONE（中文界面、8 组交互、浏览器核查及 74 项测试通过；已同步 main）。

- FYP-CURSOR-002 审计：中文显示层不改后端键、配置或分数；修复首版 pandas.Interval 格式异常、补全策略/台账翻译、当前结论改为实时读取 FACTS，修复直方图按字符串排序。截图调用方的等待文字与页签名一并更新。
- 协调者运行 8 组参考组/滑块交互，中文显示的策略选择与后端计算一致；浏览器实际检查三个页签、中文控件与图表坐标，0 页面异常。Streamlit 自带工具栏/下载工具提示和技术文件名仍可能使用英文；酒店名保留原文。
- 手工标注内容、原始评论、研究结果和数值门槛均未改；不增加低风险翻译断言测试。截图脚本只做语法与选择器对应检查，实际浏览器检查通过 CUA 完成，未运行全量研究或重新生成既有截图产物。

- FYP-CURSOR-002 GitHub 验收：[99bc2d4 research-smoke](https://github.com/bowenx1125/hotel-dual-recsys/actions/runs/34761712547) 成功。测试与显示语言变更均不构成科研结论升级。


## FYP-CURSOR-003 · 全自动模型标注与独立审计

- 目标：全数据确定性分层抽样；Grok 标注、Claude 盲审、Codex 抽查；原始 126 项人工表不变。
- 基线：388bad2；用户明确选择无需人类核验的模型参考标签路线。
- 实现：Cursor CLI / Composer 2.5；标注 cursor-grok-4.6-medium；盲审 claude-sonnet-5-medium；协调与第三方抽查 Codex。
- Cursor 可写：scripts/model_annotation.py、tests/test_model_annotation.py；协调者可写协作文档、当前指南、模型协议、无原文汇总及 Demo 说明。
- 不可改：既有标注导出器、人工样本、原始数据、研究估计器/门槛、FACTS、其他 agent 文件、Git refs。编码者不得读取原文，不额外派 agent。
- 预设规模：6 城市×7 方面×正负栏目×2=168 个关键词命中项，加 6×7=42 个该方面未命中项，共目标 210；完整 CSV 扫描，seed=42，截取前 800 字符后筛选。此为分层诊断样本，不是人口加权准确率或最终无偏测试集。
- 验收：来源哈希、盲化与完整 ID 校验、原文证据子串校验、断点重试不覆盖成功批次；两模型独立、全量分歧复查及分层一致项抽查；合成单测、真实运行、只上传聚合结果。
- 状态：DONE（210 项标注与54项终审完成；b7afe3c 已同步 GitHub，102项单测、隔离研究流程与泄漏检查 CI 通过）。

- FYP-CURSOR-003 已核对首次实现日志存在实际 AGENTS.md 读取调用；用户再次提醒后，后续编码派单显式重复先读规范要求。标注工作区只保留该角色需要的精简 AGENTS.md，避免注入其他答案。

- FYP-CURSOR-003 补充文件分工：第二个 Cursor / Composer 2.5 调用只负责 scripts/finalize_model_annotation.py、tests/test_model_annotation_finalization.py、demo/app.py、demo/zh_cn.py；与修复初标脚本的 Cursor 不共享写文件。调用明确要求先读 AGENTS.md、不增派 agent、不得提交或读取真实评论。Codex 提供最终裁决数据并独立运行测试。
- 首轮审计发现随机抽样遍历顺序、截断字段、提示词/输入哈希、恢复校验、锁及统计分母问题，退回修复。Cursor 内部测试命令被 CLI 拒绝且无具体原因，协调者改在本地直接运行；不把工具尝试记为测试通过。


- FYP-CURSOR-003 真实验收：完整 CSV 哈希匹配，210 样本/210 源评论/6 城市/184 酒店；独立来源复核210/210。Grok 11 次批次调用（一次引文失败重试）、Claude 10 次；最终各210标签。原始一致194/210=92.38%，κ=0.8904；Codex真实审查54项，最终202保留/8未决，包含1项确定共识的更正。
- 代码验收：102 项 unittest 通过；初标与终审专项覆盖恢复、引文、路径、完整队列及原始答案篡改等风险。协调者另修正输出预检查/无覆盖发布与终审队列重建；测试后的旧 Demo 快照仅按原字节恢复。原 FACTS、研究门槛和人工包哈希不变。标注展示已单独提交 db066ee，并交还另一窗口美化；此后 UI 验收由 FYP-CURSOR-004 负责。
- FYP-CURSOR-003 GitHub 验收：[b7afe3c research-smoke](https://github.com/bowenx1125/hotel-dual-recsys/actions/runs/34764121571) 全部通过。仅清除本任务 cursor-003 临时 worktree，保留另一窗口 cursor-004 工作区；原始评论与逐项标签未上传。

## FYP-CURSOR-004 · 深色 Demo UI（另一个用户主窗口）

- 用户主窗口：01a09b2d-4230-76b2-949e-f07b1b391788；负责人该窗口 Codex + Cursor Composer 2.5。
- 基线：388bad2；接手 app/zh_cn 时以 db066ee 中已提交的自动标注展示为准。
- 可写：demo/app.py、demo/zh_cn.py、demo/theme.py、demo/assets/dark.css、.streamlit/config.toml、新增 i18n 文件与对应 UI 测试（用户追加中英文切换，中文需浅显易懂）；本窗口 FYP-CURSOR-003 不再写这些 UI 文件。
- 不可改：研究算法、数据、标注管线/结果、其他窗口文件；不得把对方未提交改动一并提交。共享文档由本窗口登记，Git 提交/推送串行协调。
- 验收：AppTest 与浏览器；该窗口独立验收深色样式，本窗口不冒认其完成。
- 状态：REVIEW（实现、本地测试与浏览器验收通过，待 GitHub CI）。

- FYP-CURSOR-004 补充范围：scripts/capture_autonomous_screenshots.py、scripts/capture_live_demo_screenshots.py、src/autonomous/report.py 仅页面标题/页签选择器，禁止改变科研报告生成逻辑。

- 实现与审计：Cursor CLI / Composer 2.5 完成主题、双语目录、布局与语言控件同步；Codex 独立审查并修正重复提示、手机标题伸展、当前 Streamlit tab 选择器、图例位置与文案精度。未读取/修改私有评论或标注答案。
- 主题依据：UI UX Pro Max 深色 dashboard 设计查询、Web Design Guidelines；深蓝黑背景/青绿重点色/中文系统字体。真实桌面与390px手机检查，两语言选项/标题/图表/表格/研究标注区可用；语言切换保留酒店/分组/滑块。原生平台工具栏仍可能英文。
- 测试：122项 unittest通过；独立AppTest覆盖多次双语切换、3组酒店、滑块，数值/推荐与原后端匹配；语法与diff检查通过。增加语言目录完整性、占位符与选择同步测试。全量研究、业务效果和截图脚本批量生成未运行；截图调用仅审计选择器。
- 集成以主目录c3a567d为准，仅复制UI拥有文件；保留标注窗口b7afe3c/c3a567d，FACTS、配置、scoring、evidence、demo快照哈希不变。旧CSS/翻译模块缓存导致加载错误，通过重启本Demo服务解决。
