# FYP1 项目协作守则

## 当前入口

工作目录 `Desktop/FYP1`，主线 `main`。先读 `README.md` 和 `PROJECT_STATUS.md`；当前研究事实以 `outputs/autonomous/FACTS.json` 为准，结论边界以同目录 `CLAIMS_LEDGER.md` 为准。代码和已记录实验优先于文字计划。当前 Track B / WORKING_PAPER_ONLY；Demo 为 DESCRIPTIVE，游客排序和因果业务收益未完成。

过时蓝图、重复交接及根目录 FINAL 副本已按用户要求删除。不要恢复旧入口或凭旧计划启动新研究阶段。版本与文件清理记录在 `docs/`，旧资料可从 Git 历史及 Documents 恢复备份追溯。

## 环境与入口

- `.venv-fyp`：研究与测试；依赖见 `requirements-research.txt`。
- `.venv-demo`：Streamlit 演示；依赖见 `requirements-demo.txt`。
- `.venv-absa` 与 `models/absa/`：既有本地模型，设置 `HF_HUB_OFFLINE=1`，不默认在线下载。
- 全量研究入口 `run_research.py`；默认缓存 `data/cache/`，环境变量可覆盖。小样本用 `--small-fixture --verify-only`，必须与正式结果隔离。

## 研究纪律

1. 每次研究变更前检查 `conf/autonomous_research.json` 中对应阈值与门槛、`outputs/autonomous/DECISIONS.md` 和 `outputs/decisions.md`；保留失败与负结果，不能为过关而调低门槛。
2. 预测和评估按时间切分，排除不完整季度；不能使用包含未来信息的全期 Average_Score。A/B 评论折用于交叉拟合，不代替时间切分。
3. 没有评论提及不等于中性质量；保留缺失标记和可靠性。地理参照酒店不自动等于经济竞争对手，评论变化不自动等于管理干预。
4. 机器与弱标签的一致率不能称为人工 gold 准确率。人工核对遵循 `docs/HUMAN_ANNOTATION_PROTOCOL.md`。
5. 所有方法更优或因果主张必须有相应评测支持；不把启发式权重、模拟滑块或单元测试当成商业收益证据。
6. 若使用 LLM，只负责解释结构化结果，不能自行编造数字。论文引用必须核对原始文献；未核验的新颖性与投稿日期不能写成事实。

## 执行与验证

长时间爬取、训练、全量推理和大型实验默认由用户运行；代理负责代码、调试、结果分析及清晰命令。脚本支持幂等重跑、断点和进度输出，不程序化调用自身订阅做批处理。

用中文沟通，区分已实现、演示、测试、全量实验和真实效果；报告数字及局限。改动后运行相关测试与门槛，决策写入 `outputs/decisions.md`。当前基础验证为 unittest 全套和隔离小样本流程；它们不能替代人工或真实业务验收。

中间表优先使用 parquet，经现有 schema 校验后落盘。酒店 ID 遵循数据集前缀和稳定哈希，随机种子来自配置，正式实验回落到脚本。

## 文件与数据

事实文件、声明表、索引和每波审查结果各有唯一来源；不要生成根目录 FINAL 副本。给用户的总报告只维护 `PROJECT_STATUS.md`。早期实验输入虽然较旧，但仍可能被 Demo 或 Wave 0 核查使用，删除前必须检查读取依赖。

不提交凭证、`.env`、原始评论、私有标注文本、虚拟环境和模型权重；提交代码、配置和不含原始文本的研究结果。爬取仅收集必要酒店信息，遵守 robots、随机延迟与访问限制；不绕过验证码或 bot 检测。当前用户的授权与范围优先于历史惯例。
