# FYP1 · 酒店经理决策与双视角推荐研究

**唯一工作目录：`Desktop/FYP1`；唯一主线：`main`。** 原 autonomous / temporal / demo 分支的全部提交已汇入同一历史。

当前完成的是酒店经理侧的诊断 Demo、评论时序研究流水线和 Track B 工作论文草稿。游客侧排序仍在计划中；研究就绪度为 **WORKING_PAPER_ONLY**，Demo 为 **DESCRIPTIVE**。

## 当前成果与边界

- 研究数据：515,738 条评论、6 城市、1,493 家酒店；酒店×方面×季度面板 89,075 行。
- 测量：7 个方面、贝叶斯收缩、缺失测量标记、完整季度筛选、A/B 交叉拟合；2800 对 ABSA 与弱标签的一致率 84.61%，不是人工 gold 准确率。
- 研究：地理参照组、456 个严格评论感知变化事件、时序预测、探索性事件研究与敏感性分析。参照酒店尚不是经经济学验证的竞争对手，评论变化尚不是管理干预。
- 经理侧：把诊断劣势与可执行行动分开；地理位置不作为直接行动，Demo 提供证据不足时的拒绝建议。研究策略表覆盖 1,485 家酒店，仍是离线启发式，未证实商业收益。
- UI 的 Manager 页面仍使用原 24 家酒店快照（22 家可展示）；研究证据页展示 515K 实验。不要把全量研究覆盖率当成 UI 推荐覆盖率。
- 预测增量仅 PARTIAL：末折 MAE 从 0.37038 到 0.36937，差值置信区间跨零；事件研究 WEAK，不能宣称因果效果、需求增长或 ROI。

数值来自 2026-09-11 已保存的研究产物；本次整理不重新训练或重跑全量研究。详见 [当前状态](PROJECT_STATUS.md)、[事实文件](outputs/autonomous/FACTS.json) 和 [声明边界](FINAL_CLAIMS_LEDGER.md)。

## 启动 Demo

在本机项目目录运行：

```bash
.venv-demo/bin/python -m streamlit run demo/app.py --server.headless true --server.port 8501
```

打开 http://localhost:8501 。新机器先用 `python3 -m venv .venv-demo` 建环境，再用 `.venv-demo/bin/python -m pip install -r requirements-demo.txt` 安装依赖。仓库已包含 Demo 快照，无需下载原始评论即可展示。

## 验证与研究入口

```bash
# 本机研究环境
.venv-fyp/bin/python -m unittest discover -s tests -v
.venv-fyp/bin/python run_research.py --small-fixture --verify-only
```

新机器可用 `python3 -m venv .venv-fyp`，再安装 `requirements-research.txt`。小样本验证写入隔离的 `outputs/autonomous/fixtures/`；它不代表全量实验验收。正式研究入口是 `run_research.py`，历史计划中的 `run.py` 不存在。

原始数据现在位于 `data/cache/d1_europe/Hotel_Reviews.csv`，已 gitignore；也可用 `FYP_DATA_CACHE_ROOT` 覆盖缓存根目录。本机原始比利时数据、模型、人工标注材料与论文 Office 文件均保留，未上传新增原始数据或模型。

## 阅读入口

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：已实现、证据限制与下一步。
- [HANDOFF.md](HANDOFF.md)：从当前主线接手。
- [paper/autonomous/](paper/autonomous/)：Track B 论文分节草稿。
- [docs/CONSOLIDATION_2026-09-13.md](docs/CONSOLIDATION_2026-09-13.md)：版本整理与恢复记录。
- `RESEARCH_MASTER_PLAN.md`、`CODE_PLAN.md`、`AUTORUN_SPEC.md`、`SPRINT_44D.md`、`PAPER_STRATEGY.md`：早期蓝图；不代表全部已实现，也不构成已核实的投稿期限。
