# 爬虫需求规格（Phase 0：数据补全）

> 把这份给 Claude Code 阅读，让它据此写爬虫脚本。
> 目的：补全原始数据集缺失的字段，不重复爬已有的评论。

---

## 1. 任务目标
对原始数据集里 **821 个唯一 `hotel_url`**，逐个访问其 Booking.com 页面，补全以下字段，使其能 join 回评论数据。

**评论已经在原数据集里，不要再爬评论。** 只补缺失的酒店级属性。

## 2. 要抓取的字段

### 必需（核心，决定竞争集能否成立）
| 字段 | 说明 |
|---|---|
| `hotel_url` | 主键，用于 join 回原数据 |
| `latitude`, `longitude` | 精确经纬度（地理聚类、算地铁/景区距离的基础） |
| `star_rating` | 酒店星级（竞争集类型匹配） |
| `city` / `address` | 城市与地址（辅助分组、验证 scope） |

### 重要（best-effort，拿到最好）
| 字段 | 说明 |
|---|---|
| `price` | 统一查询条件下的当前价格（见第 3 节）。Booking 价格是动态/JS 渲染，最难拿，拿不到走降级。 |
| `property_type` | 酒店/公寓/民宿/B&B |
| `renovation_year` | 翻新/装修年份（部分页面有，没有就留空） |
| `review_score`, `review_count` | 用于和原数据集交叉验证、确认 URL 没失效 |

## 3. 价格的统一查询条件（保证跨酒店可比，必须固定）
价格只用于判断"在竞争集里相对贵/便宜"，所以所有酒店必须在**完全一致**的条件下取价：
- 入住日期：选一个**未来 30–60 天的普通工作日**（避开周末、节假日、旺季），如某个周三；离店为入住次日（住 1 晚）。
- 房客：2 成人，0 儿童，1 间房。
- 取页面**默认/最低可用房价**（lowest available rate）。
- 货币统一为 **EUR**。
- 记录 `price_currency` 和 `scraped_at` 时间戳。
- 把上述查询参数写进脚本配置，便于复现。

## 4. 技术现实与抓取策略（重要，别假设简单 requests 能成）
Booking.com 反爬较强（Cloudflare、JS 动态渲染、可能弹验证码）。按以下优先级：

1. **优先解析页面内 JSON-LD 结构化数据**（`<script type="application/ld+json">`，schema.org/Hotel）。经纬度、地址、星级、评分、价格区间常在这里，比解析 HTML 稳，且静态请求即可拿到。**先验证这条路能拿到多少字段。**
2. 如果 JSON-LD 拿不全（尤其是实时价格，通常是 JS 渲染的），再考虑用 **Playwright** 渲染页面后提取。
3. 经纬度/星级/地址相对容易（多在 meta 或 JSON-LD）；**价格最难**，作为 best-effort，拿不到就走降级方案（RESEARCH_PLAN 第 3 节 Phase 0 降级）。

## 5. 合规与红线（必须遵守）
- 用途为**学术研究**，规模小（821 页），**每次请求间随机延迟 3–8 秒**，不对服务器造成压力。
- 先读 `robots.txt`，尊重其规则。
- 只抓本规格列出的必要字段，不抓个人数据。
- **红线：不绕过验证码、不绕过任何 bot 检测机制。** 若页面要求验证码或明确阻止自动访问，**停止对该页的自动抓取**，记录为失败，走降级方案。不要用任何手段破解人机验证。
- 不在代码里硬编码任何凭证。

## 6. 鲁棒性要求
- **断点续爬**：每爬一个酒店就把结果追加落盘（如写入 `data/scraped/hotel_attributes.csv` 或逐行 JSONL）。脚本中断后重跑，应跳过已成功的 URL，只爬剩下的。
- **重试**：网络超时/5xx 错误重试 2–3 次（带指数退避）。
- **失效处理**：URL 404 或酒店下架，记录到 `data/scraped/failed_urls.csv`，不要让单个失败中断整个任务。
- **超时**：单页请求设合理超时（如 30s）。
- **进度可见**：打印进度（已完成 / 总数 / 失败数）。
- **User-Agent**：设置常规浏览器 UA；如需可在合理范围轮换，但不做激进伪装。

## 7. 输出格式
- 主输出：`data/scraped/hotel_attributes.csv`
  - 列：`hotel_url, latitude, longitude, star_rating, city, address, property_type, renovation_year, price, price_currency, review_score, review_count, scraped_at, status`
  - `status`：success / partial（缺部分字段）/ failed
- 失败清单：`data/scraped/failed_urls.csv`
- 必须能用 `hotel_url` 与原始评论数据集 join。

## 8. 给 Claude Code 的执行步骤（按顺序）
1. 先从原始 CSV 提取去重后的 `hotel_url` 列表，确认数量（应为 821，去掉空值）。
2. **先只对 5–10 个 URL 做试抓**，验证：JSON-LD 能拿到哪些字段？价格能否拿到？把试抓结果展示给我，我们据此决定是否需要 Playwright、价格是否走降级。
3. 试抓确认后，再写全量脚本（含断点续爬、延迟、失败记录）。
4. 全量爬取**由我自己 `python` 运行**（耗时主要在 3–8 秒延迟 × 821 ≈ 1 小时上下，我可外出时跑，不消耗订阅额度）。
5. 跑完把 success/partial/failed 的数量统计给我，进入 Phase 1。

> 注意：第 2 步的试抓很关键——不要直接写全量脚本就开跑。先确认能拿到什么，再决定策略。
