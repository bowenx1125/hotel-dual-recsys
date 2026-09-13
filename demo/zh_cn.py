"""Simplified Chinese display strings for the Streamlit demo. Backend keys stay English."""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping

ASPECT_LABELS: dict[str, str] = {
    "location": "位置",
    "cleanliness": "清洁",
    "breakfast": "早餐",
    "service": "服务",
    "noise": "噪音/安静",
    "room": "客房",
    "value": "性价比",
}

CITY_LABELS: dict[str, str] = {
    "Brussels": "布鲁塞尔",
    "Amsterdam": "阿姆斯特丹",
    "Paris": "巴黎",
    "London": "伦敦",
    "Barcelona": "巴塞罗那",
    "Vienna": "维也纳",
    "Milan": "米兰",
    "Bruges": "布鲁日",
    "Antwerp": "安特卫普",
    "Ghent": "根特",
}

PRICE_TIER_LABELS: dict[str, str] = {
    "low": "较低",
    "mid": "中等",
    "high": "较高",
}

ACTIONABILITY_LEVEL_LABELS: dict[str, str] = {
    "immutable": "不可直接改善",
    "high": "较易改善",
    "conditional": "视情况可改善",
    "medium": "中等可改善",
}

POLICY_SUMMARIES: dict[str, str] = {
    "fix_weakest": "选本店评价最低的可改善方面",
    "largest_peer_gap": "选与对比酒店差距最大的可改善方面",
    "most_criticized": "选负面提及最多的可改善方面",
    "peer_relative": "综合评价差距、差评比例和评论数量",
}

POLICY_LABELS: dict[str, str] = {
    "fix_weakest": "优先改善评价最差的",
    "largest_peer_gap": "优先缩小与附近酒店的差距",
    "most_criticized": "优先处理差评最多的",
    "peer_relative": "综合考虑差距与评论数量",
    "competition_aware": "综合考虑差距与评论数量",
    "diagnostic_largest_gap": "与附近差距最大（诊断）",
}

LANG_CODE = "zh"

UI: dict[str, str] = {
    "snapshot_config_error": '快照缺少完整的计算配置或格式无效，请重新生成：{cmd} --overwrite',
    "page_title": "酒店改善助手",
    "header_title": "酒店改善助手",
    "header_desc": "选一家酒店，看看哪里值得先改善，以及建议依据。",
    "header_badge": "研究演示版",
    "lang_selector_label": "语言",
    "tab_improvement": "改善建议",
    "tab_history": "历史变化",
    "tab_research": "研究进展",
    "section_improvement_desc": "面向经理 · 基于评论与对比酒店的描述性建议",
    "evidence_expander": "这些建议有哪些限制？",
    "evidence_level_prefix": "等级：",
    "city": "城市",
    "peer_group": "对比酒店分组",
    "peer_group_help": "研究中选定的附近酒店，用于参考，未证明是直接竞争对手。",
    "hotel": "选择酒店",
    "snapshot_missing_error": "未找到研究演示快照：{path}。请在本机项目目录运行：{cmd}",
    "data_period_caption": "数据时期：{period}（最近完整季度）。下方评论数为该季度住客评论条数，不是预订量。",
    "version_caption": "快照版本 {schema} · 评分版本 {scoring}",
    "coverage_summary_heading": "数据覆盖摘要",
    "coverage_total": "选定时期酒店总数",
    "coverage_eligible": "可展示酒店",
    "coverage_excluded": "已排除酒店",
    "coverage_source_panel": "源面板共 {count} 家",
    "coverage_absent_period": "选定时期无数据 {count} 家",
    "coverage_exclusion_breakdown": "排除原因汇总：{breakdown}",
    "expander_excluded_hotels": "已排除酒店及原因",
    "col_hotel_name": "酒店名称",
    "col_hotel_id": "酒店编号",
    "col_exclusion_reason": "排除原因",
    "snapshot_caption": "演示快照共 {total} 家酒店，当前可选 {eligible} 家符合展示条件。",
    "no_eligible_hotels": "演示快照中没有符合展示条件的酒店，无法选择酒店或生成建议。请检查快照是否已正确构建。",
    "metric_peer_count": "对比酒店数",
    "metric_reviews": "当季评论数",
    "metric_nearby_hotels": "附近可参考酒店",
    "metric_aspects_review_evidence": "有足够评论证据的方面",
    "metric_aspects_peer_references": "有足够附近参考的方面",
    "metric_low_reviews": "低分评论数",
    "metric_price_range": "价格范围",
    "section_compare": "本店与对比酒店",
    "chart_no_data": "暂无足够数据绘制对比图。",
    "chart_altair_fallback": "图表组件不可用，以下以表格展示非缺失对比。",
    "chart_caption": '越接近 1 表示正面评价越多，越接近 −1 表示负面评价越多。评论少时已作适度修正；没有提及的方面不作判断。',
    "chart_smoothing_caption": "评论较少时，估计会向中性靠拢；这不是把缺失当作中性。",
    "chart_aspect_col": "方面",
    "chart_series_own": "本店",
    "chart_series_peer": "对比酒店的中间水平",
    "chart_sentiment_axis": "好评与差评的总体倾向",
    "chart_legend": "图例",
    "expander_detail_table": "对比明细表",
    "section_recommendation": "建议先关注",
    "section_policies": "不同优先规则对比",
    "policies_caption": "行动建议排除位置等无法直接改变的方面。下方卡片对应当前情景假设。",
    "expander_scenario_try": "试一试：如果附近酒店也在改善",
    "expander_scenario_try_caption": "以下为假设情景，不代表已观测到的竞争变化。",
    "expander_calculation": "查看计算方法",
    "slider_label": "假定对比酒店改善强度",
    "slider_help": "假设/示意值，非拟合的竞争弹性。",
    "recommendation_none": "暂无",
    "recommendation_evidence_insufficient": "证据不足，暂不建议投入",
    "recommendation_evidence_insufficient_body": "当前评论与附近酒店参考不足以给出明确改善建议。",
    "policy_evidence_insufficient": "证据不足",
    "excluded_aspect_generic": "未达到建议门槛",
    "recommendation_fallback_actionable": "综合考虑与附近酒店的差距、差评和评论数量，建议先关注这一方面。",
    "recommendation_fallback_none": "当前证据下暂无明确短板或可执行建议。",
    "recommendation_evidence_note": "建议来自历史评论，尚未验证改善后能提高评分或收入。",
    "expander_scores": "查看详细得分与模拟结果",
    "expander_scores_caption": "「得分@0」为默认竞争强度；「得分@强度」对应当前滑块假定强度。",
    "expander_score_table": "得分表",
    "expander_formula_terms": "得分公式术语说明（可选）",
    "expander_scenario": "竞争拥挤假设（情景分析）",
    "expander_scenario_caption": "情景分析 — 假定/示意。非经验拥挤曲线，非因果估计。",
    "expander_criticism": "差评指标核对",
    "expander_criticism_caption": "默认「差评最多」使用负面提及次数；比率与每条评论均值仅供核对。",
    "expander_annotation": "电脑如何理解评论？",
    "expander_provenance": "数据从哪里来？",
    "expander_limitations": "使用前需要了解什么？",
    "col_aspect": "方面",
    "col_actionability": "可改善程度",
    "col_direct_action": "可直接改善",
    "col_own_sentiment": "本店",
    "col_peer_median": "对比中间水平",
    "col_gap": "差距(对比−本店)",
    "col_percentile": "百分位",
    "col_mentions": "提及次数",
    "col_neg_mentions": "负面提及",
    "col_neg_rate": "负面率",
    "col_neg_per_review": "每评论负面",
    "col_reliability": "可靠性",
    "col_score_at_intensity": "得分@强度{intensity}",
    "col_score_at_zero": "得分@0",
    "col_assumed_intensity": "假定强度",
    "col_top_aspect": "首选可改善方面",
    "col_top_score": "最高得分",
    "col_actionable": "可改善",
    "col_field": "字段",
    "col_value": "值",
    "prov_evidence_level": "证据等级",
    "prov_hotel_id": "酒店编号",
    "prov_compset_id": "对比分组编号",
    "prov_diagnostic_aspect": "诊断方面",
    "prov_action_aspect": "行动建议方面",
    "prov_policy_selection": "策略选型",
    "prov_config": "配置",
    "prov_actionability_config": "可操作性配置",
    "prov_synthetic": "合成数据",
    "temporal_subheader": "历史变化",
    "temporal_caption": "观察住客评价随时间的变化，了解分析方法是否可用。",
    "temporal_warning": "**历史对照页：** 本页使用旧版宽松规则（**{legacy_n}** 条候选事件），与当前严格认定（**{strict_n}** 条，判定 **{verdict}**，{evt_strength}）不同。请以「研究进展」页为准。",
    "temporal_panel_missing": "时序面板尚未构建。",
    "temporal_peer_section": "地理参考集",
    "temporal_peer_summary": "主设定：同城 Haversine k={k} · 酒店={hotels} · 城市={cities} · 术语：**地理参考集/候选对比集**（非经核验的经济竞争对手）。",
    "temporal_feasibility_green": "可行性判定：**{label}**（历史宽松流水线）",
    "temporal_feasibility_amber": "可行性判定：**{label}**（历史宽松流水线）",
    "temporal_feasibility_red": "可行性判定：**{label}**（历史宽松流水线）",
    "metric_quarter_rows": "季度单元格",
    "metric_valid_mentions": "有效提及单元格",
    "metric_candidate_events": "候选事件（宽松）",
    "metric_event_hotels": "涉及酒店",
    "metric_with_peer_ref": "附近有酒店评价变好",
    "metric_without_peer_ref": "附近未发现评价变好",
    "temporal_bullets": "- 变化阈值（预先确定）：**{threshold}**\n- 有效酒店-季度-方面单元格：**{valid_cells}**\n- 覆盖 ≥4 期的酒店：**{coverage}**\n- 变化项含义：**评论感知方面变化**（非管理干预）",
    "temporal_charts_heading": "图表",
    "chart_verdict_no_data": "暂无可绘制的候选事件汇总数据。",
    "chart_verdict_caption": "基于 feasibility_metrics.json 的宽松规则候选事件概览（非当前严格认定）。",
    "chart_verdict_candidate": "候选事件（宽松规则）",
    "chart_verdict_with_ref": "附近有酒店评价变好",
    "chart_verdict_without_ref": "附近未发现评价变好",
    "chart_verdict_hotels": "涉及酒店",
    "chart_verdict_metric_col": "指标",
    "chart_verdict_count_col": "数量",
    "chart_peer_missing": "未找到 candidate_events.csv，无法绘制对比参考分布。",
    "chart_peer_empty": "对比参考列为空，无法绘制分布。",
    "chart_peer_caption": "横轴为附近酒店在同一方面评价变好的比例（0–1），反映评论中的参照信号，不代表实际装修或改造。",
    "chart_peer_bin_col": "参考区间",
    "chart_delta_missing": "未找到 delta_q_sample.csv，无法绘制变化分布。",
    "chart_delta_empty": "变化列为空，无法绘制分布。",
    "chart_delta_caption": "评论感知方面变化（Δq）分布（来自 delta_q_sample.csv）。",
    "chart_delta_bin_col": "变化区间",
    "chart_freq_col": "频数",
    "chart_mae_no_data": "暂无模型平均绝对误差数据可绘制。",
    "chart_mae_empty": "模型平均绝对误差均为空，无法绘制对比图。",
    "chart_mae_caption": "各模型预测误差的对比；数值越低越好。这不代表已证明能改善经营效果。",
    "expander_raw_feasibility": "原始可行性指标（机器 JSON，可选下载）",
    "expander_raw_feasibility_caption": "下方为英文 schema 原始文件，仅供审计；普通阅读请以上方中文摘要为准。",
    "download_feasibility": "下载 feasibility_metrics.json",
    "temporal_feasibility_missing": "时序可行性产物尚未构建。预期包含：面板覆盖、候选变化、对比参考、绿/琥珀/红判定。",
    "temporal_predict_header": "早期预测实验",
    "temporal_predict_skipped": "预测试点不可用或未通过门槛。（{reason}）",
    "temporal_predict_info": "仅为预测关联 — **不会**将改善建议页升级为预测性证据，**也不是**因果效应。",
    "temporal_predict_caption": "预测目标：{target} · 测试期：{periods} · 同行模型是否优于持久性：{beats}",
    "temporal_predict_missing": "预测试点不可用或未通过门槛。",
    "download_predict_metrics": "下载 metrics.json（原始）",
    "temporal_claims_header": "本实验台可/不可宣称",
    "temporal_claims_body": "**可宣称：** 描述性覆盖；时序测量的可行性；留出测试集上的预测关联（非因果）。\n\n**不可宣称：** 同行因果干扰；投资回报；需求提升；将地理邻居称为经核验竞争对手；将情感变化等同于管理干预；将宽松候选事件等同于当前严格事件认定。",
    "expander_go_no_go": "通过/否决原始记录（可选下载）",
    "expander_go_no_go_caption": "英文 Markdown 原文仅供下载审计，界面不直接展示全文。",
    "download_go_no_go": "下载 GO_NO_GO.md",
    "research_subheader": "研究进展",
    "research_caption": "目前已完成评论整理和建议原型，正在检验建议是否可靠。",
    "research_info": "改善建议页仍为描述性参考，不代表因果效果、投资回报或预订增长。模型一致率不等于人工准确率。",
    "metric_measurement": "评论数据覆盖",
    "metric_strict_events": "筛选后的评价变化",
    "metric_strict_events_caption": "统计评论中检测到的评价变化次数，不代表已知的酒店改造或管理行动。",
    "metric_peer_predictive": "加入附近酒店信息是否更好",
    "metric_track": "当前研究方向",
    "research_facts_caption": "历史宽松候选事件仅供对照：{legacy}",
    "research_facts_sha_caption": "数据来源校验：FACTS sha256 `{sha}…`",
    "research_summary_heading": "当前事实摘要",
    "research_row_complete_periods": "完整季度",
    "research_row_partial_periods": "不完整季度（已排除）",
    "research_row_strict_verdict": "严格事件判定",
    "research_row_strict_count": "筛选后的评价变化",
    "research_row_event_strength": "事件研究证据强度",
    "research_row_track_formulation": "轨道 {track} 表述",
    "research_row_non_causal": "非因果声明",
    "research_row_non_causal_value": "是",
    "research_compare": "**与历史页对照：** 旧版宽松流水线共 **{legacy}** 条宽松候选事件；当前严格认定 **{strict}** 条，同行预测 **{peer}**，**{strength}**。",
    "research_facts_missing": "尚未构建 autonomous/FACTS.json。",
    "research_claims_heading": "主张台账",
    "research_claims_empty": "台账表格为空或无法解析。",
    "expander_claims_raw": "原始台账文件（可选下载）",
    "expander_claims_caption": "英文 Markdown 原文；界面以上方中文表为准，状态值来自实时文件。",
    "download_claims": "下载 CLAIMS_LEDGER.md",
    "research_claims_missing": "尚未构建 CLAIMS_LEDGER.md。",
    "expander_facts_raw": "原始 FACTS（可选下载）",
    "download_facts": "下载 FACTS.json",
    "model_annotation_heading": "电脑读懂评论了吗？",
    "model_annotation_missing": "模型标注终审报告尚未生成（预期路径：`{path}`）。生成前本页不展示任何一致率或接受率数字。",
    "model_annotation_private_note": "终审标签 CSV 将保存在本机私有目录 `{path}`（含评论原文，仅本机保存）。",
    "model_annotation_unknown_status": "标注报告状态未知，以下数字仅作参考。",
    "model_annotation_metric_items": "检查的评论片段",
    "model_annotation_metric_accepted": "保留的判断",
    "model_annotation_metric_unresolved": "仍无法确定",
    "model_annotation_metric_audited": "复查的片段",
    "model_annotation_per_aspect": "各方面终审标签计数",
    "model_annotation_footer": "完整逐条标签（含原文）仅本机保存：`{path}`。公开报告不含评论原文、酒店名或逐条裁决理由。",
    "col_claim_id": "编号",
    "col_claim": "主张",
    "col_status": "状态",
    "col_notes": "备注",
    "col_model": "模型",
    "track_prefix": "轨道",
    "recommendation_aria": "改善建议",
}


def _min_mentions(cfg: dict | None) -> int:
    if cfg and cfg.get("min_mentions") is not None:
        return int(cfg["min_mentions"])
    return 5


def policy_rules(cfg: dict | None = None) -> dict[str, str]:
    min_m = _min_mentions(cfg)
    w = (cfg or {}).get("weights") or {}
    gap_w = w.get("gap", 0.45)
    crit_w = w.get("criticism", 0.35)
    unrel_w = w.get("unreliable", 0.20)
    return {
        "fix_weakest": (
            f"在提及次数≥{min_m} 且可着手改善的方面中，选本店评价最低的一项"
            "（位置等无法搬迁的方面不参与）"
        ),
        "largest_peer_gap": (
            f"在提及次数≥{min_m} 且可着手改善的方面中，选与对比酒店中间水平差距最大的一项"
            "（对比中间水平−本店；位置不参与行动层）"
        ),
        "most_criticized": (
            f"在提及次数≥{min_m} 且可着手改善的方面中，选负面提及次数最多的一项"
            "（同时展示比率与每条评论均值供核对）"
        ),
        "peer_relative": (
            f"得分 = {gap_w}×差距归一化 + {crit_w}×负面率归一化 "
            f"− {unrel_w}×(1−可靠性) "
            "【设计权重，非学习所得】。竞争拥挤强度仅在情景分析中单独施加。"
        ),
        "diagnostic_largest_gap": (
            f"在诊断可见且提及次数≥{min_m} 的方面中，选与对比中间水平差距最大的一项"
            "（可含位置）"
        ),
    }


POLICY_RULES: dict[str, str] = policy_rules()

HEURISTIC_NAME_ZH = POLICY_LABELS["peer_relative"]

EVIDENCE_LEVEL_LABELS: dict[str, str] = {
    "DESCRIPTIVE": "描述性证据",
    "PREDICTIVE": "预测性证据",
    "CAUSAL": "因果证据",
}

EVIDENCE_BANNERS: dict[str, str] = {
    "DESCRIPTIVE": (
        "描述性证据 — 建议基于与附近酒店的相对差距和评论数量，"
        "并非经验证的因果效应估计。"
    ),
    "PREDICTIVE": "预测性证据",
    "CAUSAL": "因果证据",
}

EVIDENCE_WHY: dict[str, str] = {
    "DESCRIPTIVE": (
        "改善建议页所用快照仅包含横截面方面得分与研究者定义的对比酒店分组，"
        "本页证据等级为描述性。"
        "项目在「历史变化」「研究进展」另有按时间切分的预测实验与严格事件认定，"
        "但不将本页升级为预测性或因果证据，亦无带置信区间的处理效应识别。"
    ),
    "PREDICTIVE": "快照包含按时间切分划分的样本外预测指标。",
    "CAUSAL": "快照中全部因果验证检查项均为真。",
}

CANNOT_CLAIM_ZH: list[str] = [
    "改善某一方面会带来因果效应",
    "预订需求或收入提升",
    "对比酒店分组是经核验的经济替代品",
    "评论情感变化等于实际管理干预",
    "保证改进或投资回报率（ROI）",
]

FEASIBILITY_VERDICT_ZH: dict[str, str] = {
    "GREEN": "可行（绿）",
    "AMBER": "谨慎（琥珀）",
    "RED": "不可行（红）",
    "UNKNOWN": "未知",
}

MEASUREMENT_VERDICT_ZH: dict[str, str] = {
    "MEASUREMENT_STRONG": "测量覆盖较充分",
    "MEASUREMENT_WEAK": "测量覆盖不足",
}

PEER_PREDICTIVE_ZH: dict[str, str] = {
    "PARTIAL": "部分支持（非因果）",
    "STRONG": "较强（非因果）",
    "WEAK": "较弱",
    "NONE": "暂无",
}

STRICT_VERDICT_ZH: dict[str, str] = {
    "AMBER_ASSOCIATIONAL": "仅关联性（非因果确认）",
    "GREEN": "绿（预注册门槛通过）",
    "RED": "红",
}

EVENT_STUDY_STRENGTH_ZH: dict[str, str] = {
    "WEAK": "弱",
    "STRONG": "强",
}

TRACK_FORMULATION_ZH: dict[str, str] = {
    "A": "同行参考下的供给侧推荐（研究轨道 A）",
    "B": "诊断≠行动；位置不可直接行动；证据不足时不给出建议",
    "C": "评论情感变化≠服务改进：测量风险视角（研究轨道 C）",
}

CLAIM_TEXT_ZH: dict[str, str] = {
    "Demo is descriptive unless ledger upgrades it": "演示默认为描述性证据，除非本台账升级认定",
    "Geo kNN are candidate peers / geo reference sets": "地理 kNN 为候选对比/地理参考集（非经核验竞争对手）",
    "Location is not a direct operational action": "位置不是可直接运营干预的杠杆",
    "Overnight 5774 is legacy_permissive only": "历史宽松流水线计数仅为旧版宽松规则结果，非当前严格认定",
    "Zero-mention is not observed neutral": "零提及不等于观测到的中性",
    "Partial 2015Q3/2017Q3 excluded from main analyses": "不完整季度 2015Q3/2017Q3 已从主分析排除",
    "Peer incremental prediction": "同行增量预测（关联性，非因果）",
    "Strict events support confirmatory event-study": "严格事件是否足以支持确认性事件研究",
    "Causal wording": "因果措辞（禁止在演示中宣称）",
    "Selected track B": "选定论文轨道",
}

CLAIM_STATUS_ZH: dict[str, str] = {
    "SUPPORTED": "已支持",
    "PARTIAL": "部分支持",
    "AMBER_ASSOCIATIONAL": "仅关联性（非因果确认）",
    "FORBIDDEN": "禁止宣称",
    "DECISION": "决策记录",
}

CLAIM_NOTES_ZH: dict[str, str] = {
    "evidence_level=DESCRIPTIVE": "证据等级：描述性",
    "Wave 3 PEER_SIGNAL_STRONG": "第 3 波：同行信号较强",
    "actionability.json": "依据可操作性配置",
    "Wave 2": "第 2 波严格事件认定",
    "Wave 1 has_measurement": "第 1 波：具备测量覆盖",
    "Wave 1 completeness": "第 1 波：季度完整性规则",
    "Wave 4": "第 4 波：时间预测实验",
    "Wave 2; GREEN not lowered": "第 2 波严格事件结果",
    "Wave 5 WEAK": "第 5 波：事件研究证据强度为弱",
    "Wave 6": "第 6 波：论文轨道决策",
}

MODEL_NAME_ZH: dict[str, str] = {
    "city_mean": "城市均值基线",
    "persistence": "持久性基线",
    "own_trend": "自身趋势",
    "own_features": "自身特征",
    "own_plus_peer_state": "自身+对比酒店状态",
    "own_plus_peer_exposure": "自身+对比酒店参考",
    "own_plus_same_aspect_peer_state": "自身+同方面对比状态",
    "own_plus_same_aspect_peer_exposure": "自身+同方面对比参考",
}

TARGET_LABEL_ZH: dict[str, str] = {
    "next_quarter_mean_reviewer_score": "下一季度平均住客评分",
}

SCORE_TERM_DEFINITIONS = (
    "**术语（可选）：** "
    "总体倾向 = 经贝叶斯收缩的净好评倾向，约为 (正面提及−负面提及)/(提及次数+先验强度)，"
    "评论少时向中性靠拢；"
    "差距 = 对比酒店中间水平 − 本店；"
    "负面率 = 负面提及占该方面提及的比例；"
    "可靠性 = 提及量越高越接近 1（经收缩处理），反映评论提及多少而非判断真伪或准确率；"
    "差距/负面率归一化 = 本店各可改善方面内的 0–1 缩放。"
)

INELIGIBLE_REASONS: dict[str, str] = {
    'missing_coordinates': '缺少酒店坐标',
    'no_measured_aspects': '没有可用的评论方面数据',

    "compset_valid=0": "对比分组无效",
    "peer_count<2": "附近可参考酒店不足",
    "absent_selected_period": "选定时期无评论数据",
    "missing_from_panel": "不在研究面板中",
}

ABSTENTION_REASONS: dict[str, str] = {
    'missing_coordinates': '缺少酒店坐标',
    'no_measured_aspects': '没有可用的评论方面数据',
    'no_eligible_aspects': '没有方面同时满足证据和可改善条件',
    'crowding_data_unavailable': '缺少模拟场景所需的附近酒店数据',
    'crowding_unavailable': '缺少模拟场景数据',
    'hotel_ineligible': '酒店数据尚未达到展示条件',
    'insufficient_mentions': '相关评论太少',
    'insufficient_peers': '可比较的附近酒店太少',
    'insufficient_reliability': '评论数量所提供的证据不足',
    'invalid_counts': '评论计数不完整或无效',
    'invalid_neg_mentions': '缺少有效的差评计数',
    'invalid_neg_rate': '缺少有效的差评比例',
    'missing_aspect_record': '缺少这个方面的数据',
    'missing_aspects': '缺少评论方面数据',
    'no_measurement': '没有提及这个方面',
    'nonfinite_gap': '缺少可用的附近酒店差距',
    'nonfinite_net': '缺少有效评价数据',
    'not_actionable': '不属于可以直接改善的方面',
    'unknown_aspect': '尚未定义这个方面的改善规则',

    "insufficient_evidence": "评论与附近参考均不足以给出建议",
    "no_actionable_aspect": "没有可直接改善的方面达到门槛",
    "all_aspects_excluded": "各方面均未达到建议门槛",
}

LIMITATIONS_ZH = """
- 评论条数**不等于**预订量或需求。
- 方面总体倾向来自评论，**不等于**经核验的管理干预效果。
- 对比酒店分组为研究参考集，**不等于**经核验的经济替代品。
- **综合考虑差距与评论数量**使用**设计权重**，非学习所得业务回报。
- **竞争拥挤假设**滑块为**假设/示意**，非拟合弹性。
- 位置可呈现为短板，但**不是**可直接运营的行动杠杆。
- 本演示**不宣称**事件研究、安慰剂或因果估计。
"""

MODEL_ANNOTATION_BOUNDARY_EXPANDER = """
**自动标注与使用边界**（本演示不要求人工填写标签，也不宣称真实业务验收）：

1. **流程**：Grok 初标 → 不同模型盲审（如 Claude）→ 分歧与不确定项由 Codex 作最终裁决；证据不足时保留为未决。
2. **一致率含义**：模型间原始一致率与 Cohen κ 仅反映标注一致性，**不等于**人工准确率或总体正确率。
3. **经理决策**：界面建议仍为描述性证据；是否可运营干预、是否带来预订或收入变化，需管理层独立判断，**尚未经真实酒店业务验证**。

完整标注文本与逐条理由保存在本机私有目录，不进入公开仓库。
"""

HUMAN_CONFIRM_EXPANDER = MODEL_ANNOTATION_BOUNDARY_EXPANDER

SENTIMENT_LABELS: dict[str, str] = {
    "positive": "正面",
    "negative": "负面",
    "neutral": "中性",
    "not_about_aspect": "未提及",
}

MODEL_ANNOTATION_REPORT_PATH = "outputs/autonomous/model_annotation/final_20260913.json"
MODEL_ANNOTATION_PRIVATE_CSV = (
    "outputs/autonomous/private/model_annotation_rounds/round_20260913/final_labels.csv"
)


def model_annotation_status_label(status: str | None) -> str:
    mapping = {
        "MODEL_AUDITED_REFERENCE": "已完成模型审计（参考结果）",
        "accepted_consensus": "双模型一致（未抽审计）",
        "accepted_codex": "Codex 裁决接受",
        "unresolved": "未决（证据不足）",
    }
    return mapping.get(status or "", status or "暂无")


def format_model_agreement_caption(raw_rate: float | None, kappa: float | None) -> str:
    raw = f"{raw_rate * 100:.1f}%" if raw_rate is not None else "暂无"
    kappa_s = "未定义" if kappa is None else f"{kappa:.3f}"
    return (
        f"模型原始一致率 {raw} · Cohen κ {kappa_s}。"
        "此为模型间配对一致率，不代表人工准确率或总体正确率。"
    )


def aspect_label(aspect_id: str, fallback: str | None = None) -> str:
    return ASPECT_LABELS.get(aspect_id, fallback or aspect_id)


def city_label(city: str) -> str:
    return CITY_LABELS.get(city, city)


def compset_label(cs: str) -> str:
    return "（全部）" if cs == "(all)" else cs


def price_tier_label(tier: str | None) -> str:
    if not tier:
        return "暂无"
    return PRICE_TIER_LABELS.get(str(tier).lower(), tier)


def actionability_label(level: str | None) -> str:
    if not level:
        return "暂无"
    return ACTIONABILITY_LEVEL_LABELS.get(level, level)


def fmt_na(value: Any, empty: str = "暂无") -> str:
    if value is None:
        return empty
    if isinstance(value, str) and value.strip().lower() in ("n/a", "na", ""):
        return empty
    return str(value)


def fmt_bool(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return fmt_na(value)


def evidence_banner(level: str) -> str:
    return EVIDENCE_BANNERS.get(level, f"{level} 证据")


def evidence_level_label(level: str) -> str:
    return EVIDENCE_LEVEL_LABELS.get(level, level)


def evidence_why(level: str, backend_why: str) -> str:
    return EVIDENCE_WHY.get(level, backend_why)


def policy_label(key: str, backend_label: str | None = None) -> str:
    return POLICY_LABELS.get(key, backend_label or key)


def policy_rule(key: str, backend_rule: str | None = None, cfg: dict | None = None) -> str:
    rules = policy_rules(cfg) if cfg else POLICY_RULES
    return rules.get(key, backend_rule or "")


def policy_summary(key: str) -> str:
    return POLICY_SUMMARIES.get(key, "")


def formula_caption(cfg: dict) -> str:
    w = cfg.get("weights") or {}
    return (
        f"得分 = {w.get('gap', 'gap')}×差距归一化 + {w.get('criticism', 'criticism')}×批评归一化 "
        f"− {w.get('unreliable', 'unreliable')}×(1−可靠性) "
        "【设计权重，非学习所得收益】。竞争拥挤项仅在情景分析中单独施加。"
    )


def weights_caption(cfg: dict) -> str:
    w = cfg.get("weights") or {}
    return (
        f"设计权重：差距={w.get('gap')}，批评={w.get('criticism')}，不可靠={w.get('unreliable')}。"
        "非估计所得业务回报。"
    )


def _aspect_stats_line(rec: Mapping[str, Any], label: str) -> str:
    mentions = fmt_na(rec.get("mention_count"))
    neg = fmt_na(rec.get("neg_mentions"))
    gap = rec.get("gap")
    if gap is None:
        comparison = "暂时没有足够数据与附近酒店比较"
    elif isinstance(gap, (int, float)):
        if gap > 0:
            comparison = f"评价比对比酒店的中间水平低 {gap:.3f}"
        elif gap < 0:
            comparison = f"评价比对比酒店的中间水平高 {abs(gap):.3f}"
        else:
            comparison = "评价与对比酒店的中间水平持平"
    else:
        comparison = "暂时无法比较评价水平"
    return f"「{label}」被提到 {mentions} 次，其中 {neg} 次是负面评价；{comparison}。"


def build_diagnostic_explanation(
    expl: dict,
    label_fn: Callable[[str], str] = aspect_label,
    hotel: dict | None = None,
) -> str | None:
    diag_a = expl.get("diagnostic_aspect")
    act_a = expl.get("actionable_recommendation")
    if not diag_a:
        return None
    diag = expl.get("diagnostic") or {}
    if diag.get("actionable"):
        return None
    diag_label = label_fn(diag_a)
    if act_a:
        act_label = label_fn(act_a)
        act_rec = ((hotel or {}).get("aspects") or {}).get(act_a) or {}
        stats = _aspect_stats_line(act_rec, act_label)
        return (
            f"与附近酒店相比，「{diag_label}」差距最大，但这类问题通常无法直接改变"
            f"（例如位置无法搬迁）。因此建议先关注可改善的方面：{stats}"
        )
    return (
        f"与附近酒店相比，「{diag_label}」差距最大，但不属于可直接改善的方面，"
        "当前证据下暂无对应行动建议。"
    )


def build_recommendation_explanation(
    expl: dict,
    hotel: dict,
    label_fn: Callable[[str], str] = aspect_label,
) -> str | None:
    diag_expl = build_diagnostic_explanation(expl, label_fn, hotel)
    if diag_expl:
        return diag_expl
    act_a = expl.get("actionable_recommendation")
    if not act_a:
        return None
    rec = (hotel.get("aspects") or {}).get(act_a) or {}
    return _aspect_stats_line(rec, label_fn(act_a))


def translate_claim_text(text: str) -> str:
    return CLAIM_TEXT_ZH.get(text.strip(), text.strip())


def translate_claim_status(status: str) -> str:
    return CLAIM_STATUS_ZH.get(status.strip(), status.strip())


def translate_claim_notes(notes: str) -> str:
    raw = notes.strip()
    if not raw:
        return "暂无"
    return CLAIM_NOTES_ZH.get(raw, raw)


def format_policy_selection(
    policies: Mapping[str, Mapping[str, Any]],
    order: list[str],
    label_fn: Callable[[str], str],
) -> str:
    parts: list[str] = []
    for key in order:
        chosen = policies[key].get("chosen_aspect")
        aspect = label_fn(chosen) if chosen else "暂无"
        parts.append(f"{policy_label(key)}：{aspect}")
    return "；".join(parts)


def format_hist_bin(idx: Any) -> str:
    if hasattr(idx, "left") and hasattr(idx, "right"):
        lo, hi = float(idx.left), float(idx.right)
        return f"{lo:.2f}–{hi:.2f}"
    try:
        return f"{float(idx):.2f}"
    except (TypeError, ValueError):
        return str(idx)


def target_label(code: str | None) -> str:
    if not code:
        return "暂无"
    return TARGET_LABEL_ZH.get(code, code)


def event_study_strength_label(code: str | None) -> str:
    if not code:
        return "暂无"
    strength = EVENT_STUDY_STRENGTH_ZH.get(code, code)
    return f"事件研究证据强度：{strength}"


def track_formulation(track: str | None, wave6: dict | None = None) -> str:
    if not track:
        return "暂无"
    if wave6 and wave6.get("formulation"):
        if track == "B":
            return TRACK_FORMULATION_ZH.get("B", wave6["formulation"])
    return TRACK_FORMULATION_ZH.get(track, f"轨道 {track}")


def mae_column_label() -> str:
    return "平均绝对误差（MAE）"


def rmse_column_label() -> str:
    return "均方根误差（RMSE）"


def parse_claims_ledger(md_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in md_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|[-\s|]+\|$", line):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 4 or parts[0].upper() == "ID":
            continue
        rows.append({
            "id": parts[0],
            "claim_en": parts[1],
            "claim_zh": translate_claim_text(parts[1]),
            "status_en": parts[2],
            "status_zh": translate_claim_status(parts[2]),
            "notes": translate_claim_notes(parts[3]),
        })
    return rows


def model_name(key: str) -> str:
    return MODEL_NAME_ZH.get(key, key)


def measurement_label(code: str | None) -> str:
    if not code:
        return "暂无"
    return MEASUREMENT_VERDICT_ZH.get(code, code)


def peer_predictive_label(code: str | None) -> str:
    if not code:
        return "暂无"
    return PEER_PREDICTIVE_ZH.get(code, code)


def strict_verdict_label(code: str | None) -> str:
    if not code:
        return "暂无"
    return STRICT_VERDICT_ZH.get(code, code)


def feasibility_verdict_label(code: str | None) -> str:
    if not code:
        return "未知"
    return FEASIBILITY_VERDICT_ZH.get(code, code)


def ineligible_reason_label(reason: str) -> str:
    if not reason:
        return fmt_na(None)
    if reason in INELIGIBLE_REASONS:
        return INELIGIBLE_REASONS[reason]
    if reason.startswith("n_reviews<"):
        return f"当季评论数不足（需≥{reason.split('<', 1)[1]}）"
    if reason.startswith("mention_count<"):
        return f"提及次数不足（需≥{reason.split('<', 1)[1]}）"
    if reason.startswith("reliability<"):
        return f"可靠性不足（需≥{reason.split('<', 1)[1]}）"
    if reason.startswith("peer_n<"):
        return f"附近可参考酒店不足（需≥{reason.split('<', 1)[1]}）"
    return reason


def abstention_reason_label(reason: str) -> str:
    if not reason:
        return fmt_na(None)
    if reason in ABSTENTION_REASONS:
        return ABSTENTION_REASONS[reason]
    return ineligible_reason_label(reason)


def format_excluded_aspect_reasons(
    excluded: Any,
    label_fn: Callable[[str], str],
) -> str:
    if not excluded:
        return ""
    pairs: list[tuple[str | None, str]] = []
    if isinstance(excluded, dict):
        pairs = [(str(k), str(v or "")) for k, v in excluded.items()]
    elif isinstance(excluded, list):
        for item in excluded:
            if isinstance(item, str):
                pairs.append((item, ""))
            elif isinstance(item, dict):
                pairs.append((item.get("aspect"), str(item.get("reason") or "")))
    lines: list[str] = []
    for aspect, reason in pairs:
        if not aspect:
            continue
        lbl = label_fn(aspect)
        reason_txt = abstention_reason_label(reason) if reason else UI["excluded_aspect_generic"]
        lines.append(f"· {lbl}：{reason_txt}")
    return "\n".join(lines)
