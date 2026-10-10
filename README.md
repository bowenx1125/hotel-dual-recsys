# FYP1 · 酒店改善助手

这是一个**酒店经理决策研究原型**：把住客评论按清洁、早餐、服务等方面整理，与附近酒店比较，再给出“先改善什么、依据是什么”的建议。网站用来展示研究，核心成果是可复现的评论分析与建议算法。

目前支持深色中文 / English 界面，覆盖最近完整季度的 1,487 家酒店，其中 1,223 家符合展示条件。它还没有证明能增加评分、预订或利润，也没有完成游客选酒店功能。

**关于「增加收益」这条线**：已有四轮实证研究（效应估计、离线策略评估、方面价值向量、揭示性干预事件研究），结论是**算法侧有真实信号、收益侧按现有数据不可识别**——缺的是干预/采纳日志与收益序列，不是更好的算法。四轮的零结果本身是论文的实证主干。六份报告见 [`docs/fyp1/`](docs/fyp1/README.md)，**新同事建议先读其中的进度盘点**（自包含，附术语小词典）。

只需先读三份文件：**本页**了解项目并启动；[HANDOFF.md](HANDOFF.md)看最新进展、完整复现和下一步；[AGENTS.md](AGENTS.md)约束所有编码 agent。

## 五分钟启动 Demo

使用 Python **3.12.3**（也在 3.13.12 验证通过），在仓库根目录执行：

```bash
python3.12 -m venv .venv-demo
.venv-demo/bin/python -m pip install -r requirements-demo.txt
.venv-demo/bin/python -m streamlit run demo/app.py --server.headless true --server.port 8501
```

打开 http://localhost:8501 。先选城市和酒店，查看建议，再展开依据。顶部切换中英文。仓库已包含无评论原文的快照，**启动 Demo 不需要原始 CSV 或模型**。Windows 使用 `.venv-demo\Scripts\python.exe` 替换上述 Python 路径。

## 文件夹怎么读

| 位置 | 用途 |
|---|---|
| `demo/` | 网页、深色样式与中英文文案 |
| `src/recommendation/` | Demo 和研究共用的建议算法、面板转换 |
| `src/effect/` | 效应估计、离线策略评估、价值向量、揭示性干预事件研究（P1–P5A） |
| `src/autonomous/`、`src/temporal/` | 测量、时间切分、比较实验和报告 |
| `run_research.py` | 从原始数据到实验报告的统一入口 |
| `scripts/` | 构建快照、评估策略、核验资产和模型标注等工具 |
| `conf/` | 科研门槛、建议权重和可操作性规则 |
| `tests/` | 合成测试、边界测试和复现保护 |
| `outputs/demo/` | 当前完整 Demo 快照和描述性验收结果 |
| `outputs/autonomous/` | 已保存的科研结果、声明边界和模型标注报告 |
| `data/processed/` | 无评论原文的必要处理表 |
| `paper/autonomous/` | 工作论文草稿，仍需按复现实验修订 |
| `docs/` | 模型标注协议、外部资产哈希清单；`docs/fyp1/` 为 FYP1 六份实证报告 |
| `outputs/overnight/`、`outputs/night_demo/` | 当前流程仍读取的历史对照；不是最新 Demo |

`data/cache/`、`models/`、虚拟环境和私有标注只在本机，不能上传。完整研究的资产、命令、续跑和验收见 [HANDOFF.md](HANDOFF.md)。
