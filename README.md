# FYP1 · 酒店经理决策研究

**先看 [项目报告](PROJECT_STATUS.md)**：用浅显语言说明做了什么、还缺什么和下一步。

唯一目录为 `Desktop/FYP1`，GitHub 主线为 `main`。当前是经理端研究原型与工作论文草稿；游客端和真实业务效果验证尚未完成。

## 启动演示

在项目目录运行：

```bash
.venv-demo/bin/python -m streamlit run demo/app.py --server.headless true --server.port 8501
```

打开 http://localhost:8501 。新机器先建立 `.venv-demo`，安装 `requirements-demo.txt`。仓库已有演示快照，无需下载原始评论即可展示。

## 验证

```bash
.venv-fyp/bin/python -m unittest discover -s tests -v
.venv-fyp/bin/python run_research.py --small-fixture --verify-only
```

新机器先建立 `.venv-fyp`，安装 `requirements-research.txt`。小样本验证写入 `outputs/autonomous/fixtures/`，不代表全量研究验收。

## 文件入口

| 内容 | 位置 |
|---|---|
| 进展与下一步 | [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| 当前论文草稿 | [paper/autonomous/](paper/autonomous/) |
| 当前事实与声明范围 | [FACTS.json](outputs/autonomous/FACTS.json)、[CLAIMS_LEDGER.md](outputs/autonomous/CLAIMS_LEDGER.md) |
| 人工核对规范 | [docs/HUMAN_ANNOTATION_PROTOCOL.md](docs/HUMAN_ANNOTATION_PROTOCOL.md) |
| 代码、配置、测试 | `demo/`、`src/`、`scripts/`、`conf/`、`tests/` |
| 清理与恢复记录 | [文件清理](docs/FILE_CLEANUP_2026-09-13.md)、[版本整合](docs/CONSOLIDATION_2026-09-13.md) |

本机原始数据在 `data/cache/d1_europe/Hotel_Reviews.csv`，可通过 `FYP_DATA_CACHE_ROOT` 覆盖缓存根目录。原始评论、模型、私有人工标注包、环境和早期 Office 文件仅本机保留。早期报告生成脚本 `build_thesis.js`、`build_deck.js` 输出到 `paper/previous_submission/`。
