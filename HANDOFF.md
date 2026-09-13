# 当前接手入口

唯一目录 `Desktop/FYP1`，主线 `main`。先读 `CLAUDE.md` → `PROJECT_STATUS.md` → `NEXT.md`。最新事实为 `outputs/autonomous/FACTS.json`，结果边界为 `FINAL_CLAIMS_LEDGER.md`；论文草稿在 `paper/autonomous/`。

研究已到 Track B / WORKING_PAPER_ONLY。不要从旧交接中的 S0 或不存在的 `run.py` 重新开始，也不要据旧文档断言 GitHub 认证失败。当前数据缓存已并入 `data/cache/`，默认路径基于项目位置；环境变量仍可覆盖。

本机使用 `.venv-fyp/bin/python` 做研究验证，`.venv-demo/bin/python` 启动 UI，`.venv-absa/bin/python` 使用既有离线模型。模型、原始数据、私人标注包及全量 checkpoint 已留在唯一工作目录，未纳入新增 Git 提交。

本次版本整理没有推进新研究 Wave。全量实验重跑前先看配置、产物和 checkpoint；小样本验证用 `--small-fixture --verify-only`，不得将其结果覆盖全量事实。

历史分支和资产恢复见 `docs/CONSOLIDATION_2026-09-13.md`。早期研究计划仍保留供追溯，当前实现和研究强度以代码及事实表为准。
