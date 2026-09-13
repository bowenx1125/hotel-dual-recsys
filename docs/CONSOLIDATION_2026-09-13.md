# FYP1 版本整理 · 2026-09-13

## 整合依据

| 原入口 | 原 HEAD | 处理依据 |
|---|---|---|
| FYP1 / demo/provider-side-20260910-grok | 0f5ebd5 | 较旧，独有一张历史截图，完整 merge 保留 |
| FYP1-temporal / research/temporal-feasibility-20260910-grok | 2586827 | autonomous 的祖先，全部成果已继承 |
| FYP1-autonomous / research/autonomous-paper-20260911 | f45ba59 | 最新研究主线，作为整合基础 |

检查时三个工作区均无未提交的受版本控制改动，远端 HEAD 与本地一致。GitHub 默认分支仍指向旧 Demo。main 通过普通 merge 汇合所有历史，不使用 force-push。

## 本地资产

研究环境 .venv-fyp、全量 checkpoint、私有标注材料、temporal 的中间月面板与 FYP_DATA_CACHE 已移入 FYP1；缓存新位置为 data/cache/d1_europe/Hotel_Reviews.csv。数据、模型、Office 论文、旧爬取存档均保留。环境入口中的旧绝对路径已迁移；代码默认路径改为基于项目根目录，环境变量可覆盖。

Desktop 的 files 2、files.zip 和 files 中的三个 FYP Markdown 经比对均为 FYP1 现有 BG.md / RESEARCH_PLAN.md / SCRAPING_SPEC.md 的精确副本；files 中另有无关 PDF，必须保留。FYP1/Source.zip 的所有非系统文件都已有完全一致的项目文件。

## 恢复备份

本机备份在 `~/Documents/FYP1-backups/20260913-195908/`，不在 Desktop，也不上传 GitHub。all-branches.bundle 已通过 git bundle verify；desktop-assets.tar 的 1,348 个普通文件全部与源文件 SHA-256 一致。assets-manifest.json 和 refs-before.txt 记录原位置、哈希和分支。备份不含可重新安装的虚拟环境及 node_modules；三个环境的 pip freeze 已单独保留。

可通过 git bundle list-heads 检查历史，再从 bundle fetch 指定旧分支到临时恢复仓库；资产先解包到独立目录核对，避免覆盖当前工作目录。旧工作区的 .git 链接不用于恢复，Git 历史来自 bundle。

## 验证与完成记录

- 52 项 unittest 全部通过。
- small-fixture / verify-only 的 Wave 0–10 完整通过，输出在 fixtures 隔离目录。
- Streamlit AppTest 三个页面均执行完成，0 exception；旧 use_container_width API 有弃用提示，但未阻止运行。本次不声称做过浏览器视觉验收。
- 研究/时序两套入口均通过新缓存默认路径与环境变量覆盖检查；515K 原始 CSV 的 SHA-256 与配置一致。
- 受版本控制的研究结果、数据表、论文结果及 FINAL_FACTS.json 在验证前后哈希完全一致；现有 smoke test 会重建 Demo 快照，验证后已恢复原始快照。
- 16 个迁移的私人标注、checkpoint、中间面板和缓存文件均逐个与备份哈希一致。
- 本地已删除两个重复工作区、files 2、files.zip、files 中三份重复 FYP 文档和 Source.zip；files 中两份无关 PDF 保留。Desktop 只剩一个 FYP 项目目录 FYP1。
- GitHub 主线发布与旧分支清理待最后同步确认。

研究事实文件不重算，不把小样本验证当成全量研究验收。完整运行日志保存在上述恢复备份目录。
