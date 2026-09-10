# FYP：双视角酒店推荐系统（Tourist + Manager）

> 这是 Claude Code 启动时自动读取的项目上下文文件。保持精简。
> 完整研究计划见 `RESEARCH_PLAN.md`（需要时再读）。
> 当前任务的爬虫规格见 `SCRAPING_SPEC.md`。

## 一句话定位
基于 Booking.com 评论数据，构建一个**双视角**酒店推荐系统，目标投 B 类学术会议论文。
- **Tourist 视角**：在用户预算档位内，给出该档位综合最优推荐
- **Manager 视角**：为酒店经理提供竞争位置分析 + aspect 诊断 + 定价/改进建议

## 三个核心创新点
1. **对称多利益相关者框架**：同一套底层表征，Tourist 读出"最优选择"，Manager 读出"竞争位置"。现有酒店推荐几乎全是 Tourist 单视角，Manager 侧竞争诊断少见。
2. **本地竞争集（Local Comp Set）建模**：用「地理位置 + 价格档位」定义"抢同一批客人"的竞争集，而不是用绝对价格过滤。
3. **Aspect 级竞争诊断 + 差评情感分析**：把"性价比"和"差评"从模糊概念做成 comp set 内可量化、可解释的指标。

## 数据现状
- **主数据集**：Booking.com Hotel Reviews（Kaggle: thedevastator/booking-com-hotel-reviews）
  - 26,675 条评论 / 821 家唯一酒店 / 96% 为比利时（少量白俄罗斯）
  - 16 列，关键列：`hotel_name`, `hotel_url`, `avg_rating`, `rating`, `review_text`, `tags`, `nationality`, `reviewed_at`
  - **缺失字段**：价格、经纬度、星级、装修年份
- **补全方式**：爬取 `hotel_url` 页面拿到上述缺失字段（见 `SCRAPING_SPEC.md`）。经纬度到手后用坐标做地理聚类，城市识别不再依赖酒店名匹配。

## Scope（重要）
聚焦**比利时主要城市**，因为只有这些城市的酒店密度够构成竞争集：
- Brussels（54 家 / 4696 评论）← 主力
- Antwerp（18）、Bruges（16）、Ghent（10）、Leuven（6）
- 孤立的乡村 B&B（周围无同档竞争者）不纳入竞争集分析。
- 论文 scope 表述："比利时主要城市酒店市场的双视角推荐"——这是合理的 case study 范围。

## 技术栈
- Python 3.x，pandas，numpy，scikit-learn
- 地理：geopy / haversine（距离计算），可选 OpenStreetMap POI（地铁站、景区坐标）
- Aspect 情感（ABSA）：预训练模型（如 PyABSA / HuggingFace ABSA 模型）或 LLM（成本权衡，见 RESEARCH_PLAN）
- 排序模型：LightGBM（learning-to-rank）
- 爬虫：优先解析页面内的 JSON-LD 结构化数据；若需渲染再考虑 Playwright

## 目录结构
```
data/
  raw/            # 原始 Kaggle CSV
  scraped/        # 爬虫补全的字段（价格/经纬度/星级）
  processed/      # 清洗、合并、特征工程后的数据
src/
  scrape/         # Phase 0 爬虫
  compset/        # Phase 1 竞争集构建
  aspect/         # Phase 2 aspect 提取
  model/          # Phase 4-5 双视角模型
  eval/           # Phase 6 评测
outputs/          # 图表、结果表、case study
RESEARCH_PLAN.md  # 完整研究计划
SCRAPING_SPEC.md  # 爬虫需求
```

## 当前进度
**Phase 0：数据补全**（爬 hotel_url 拿价格/经纬度/星级）← 现在在这里

## 编码约定
- 中文注释 OK。
- 每个 phase 的脚本**独立可运行**，中间产物落盘到 `data/`，下一个 phase 从盘读，不耦合。
- 任何凭证、API key、密码**绝不**写进代码或提交到 git。
- 数据处理脚本要可重复运行（幂等），重跑不会污染结果。

## 重要工作模式（省订阅额度）
- **长时间执行的脚本（爬虫、训练、批量 aspect 分析）由普通 `python xxx.py` 运行**，不通过 `claude -p` 程序化调用——后者会消耗订阅额度，前者完全不消耗。
- Claude Code 的额度只花在"帮我写代码、改代码、调试"上。
- 爬虫这类耗时任务：写好脚本 → 我自己 `python` 运行（可外出时跑）→ 跑完回来给 Claude 看结果。
