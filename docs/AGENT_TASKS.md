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
