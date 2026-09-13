# 文件精简记录 · 2026-09-13

按用户要求清理过时与重复文件，根目录的阅读入口收敛为 README.md（启动）、PROJECT_STATUS.md（总报告）与 CLAUDE.md（协作约束）。本次不改变研究算法、门槛和结论。

删除 31 个文件：旧研究蓝图、已结束任务说明、重复交接、根目录 FINAL 副本、重复 Demo 说明、被当前截图取代的旧截图/静态页面/启动测试日志，以及两个系统缓存文件。根目录 FINAL_FACTS、FINAL_CLAIMS_LEDGER、FINAL_ARTIFACT_INDEX、FINAL_REVIEWER_REPORT 均有完全一致的下层来源；科学摘要合并到 outputs/autonomous/RESEARCH_SUMMARY.md。

迁移 5 个文件：仍被 Wave 0 读取的旧交接放入 outputs/overnight/HANDOFF_HISTORICAL.md；人工核对规范放入 docs；3 份内容不完全相同的早期 Office 文件放入 paper/previous_submission，未按时间戳擅自删掉。仍被 Demo 与历史对照读取的数据保留；每波研究快照即使与主表相同，也有独立的复现用途，予以保留。

已同步修改 UI、研究核查和文档生成入口，后续执行不再生成根目录 FINAL 副本。科学事实与原始数据保持原样。

恢复备份：本机 ~/Documents/FYP1-backups/20260913-201419-file-cleanup/。before-cleanup.bundle 已验证，removed-and-moved-files.tar 中 36 个文件与源文件 SHA-256 一致；完整路径、删除或移动动作见 manifest.json。备份不上传 GitHub。

验证完成：53 项单元测试全部通过（新增防止根目录重复报告再生成的回归检查）；隔离小样本 Wave 0–10 全部通过；Streamlit 三个页面无异常，且确认页面读取了唯一的声明表；两份旧 Office 生成脚本通过语法检查。37 份研究数据/事实/结果文件的哈希在验证前后不变，3 份 Office 文件迁移前后哈希相同。验证后清除了可重新生成的 fixtures 临时输出，避免遗留旧 FINAL 副本；运行日志保存在备份目录。

这次检查没有运行全量研究、模型训练或真实酒店业务验证。
