"""Simplified Chinese display strings for the Streamlit demo. Backend keys stay English."""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping

# --- Aspects (7) ---
ASPECT_LABELS: dict[str, str] = {
    "location": "位置",
    "cleanliness": "清洁",
    "breakfast": "早餐",
    "service": "服务",
    "noise": "噪音/安静",
    "room": "客房",
    "value": "性价比",
}

# --- Cities ---
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

# --- Price bands ---
PRICE_TIER_LABELS: dict[str, str] = {
    "low": "低档",
    "mid": "中档",
    "high": "高档",
}

# --- Actionability levels ---
ACTIONABILITY_LEVEL_LABELS: dict[str, str] = {
    "immutable": "不可直接干预",
    "high": "高可操作性",
    "conditional": "条件性可操作",
    "medium": "中等可操作性",
}

# --- Policy keys ---
POLICY_LABELS: dict[str, str] = {
    "fix_weakest": "修复最弱项（可操作）",
    "largest_peer_gap": "最大同行差距（可操作）",
    "most_criticized": "最受批评项（可操作）",
    "peer_relative": "同行相对证据加权（启发式）",
    "competition_aware": "同行相对证据加权（启发式）",
    "diagnostic_largest_gap": "最大诊断劣势",
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
            f"在提及次数≥{min_m} 的可操作维度中，选取本店净情感最低者"
            "（位置等不可直接干预维度不参与）"
        ),
        "largest_peer_gap": (
            f"在提及次数≥{min_m} 的可操作维度中，选取与同行中位数差距最大者"
            "（同行中位数−本店；位置不参与行动层）"
        ),
        "most_criticized": (
            f"在提及次数≥{min_m} 的可操作维度中，选取负面情感提及次数最多者"
            "（同时展示比率与每条评论均值供核对）"
        ),
        "peer_relative": (
            f"得分 = {gap_w}×差距归一化 + {crit_w}×负面率归一化 "
            f"− {unrel_w}×(1−可靠性) "
            "【设计权重，非学习所得】。竞争拥挤强度仅在情景分析中单独施加。"
        ),
        "diagnostic_largest_gap": (
            f"在诊断可见且提及次数≥{min_m} 的维度中，选取与同行中位数差距最大者"
            "（可含位置）"
        ),
    }


POLICY_RULES: dict[str, str] = policy_rules()

HEURISTIC_NAME_ZH = "同行相对证据加权（启发式）"

# --- Evidence ---
EVIDENCE_LEVEL_LABELS: dict[str, str] = {
    "DESCRIPTIVE": "描述性证据",
    "PREDICTIVE": "预测性证据",
    "CAUSAL": "因果证据",
}

EVIDENCE_BANNERS: dict[str, str] = {
    "DESCRIPTIVE": (
        "描述性证据 — 建议基于相对维度差距与评论证据，"
        "并非经验证的因果效应估计。"
    ),
    "PREDICTIVE": "预测性证据",
    "CAUSAL": "因果证据",
}

EVIDENCE_WHY: dict[str, str] = {
    "DESCRIPTIVE": (
        "经理诊断页所用快照仅包含横截面维度得分与研究者定义的参考同行集，"
        "本页证据等级为描述性。"
        "项目在「历史时序分析」「当前研究证据」另有按时间切分的预测实验与严格事件认定，"
        "但不将本页升级为预测性或因果证据，亦无带置信区间的处理效应识别。"
    ),
    "PREDICTIVE": "快照包含按时间切分划分的样本外预测指标。",
    "CAUSAL": "快照中全部因果验证检查项均为真。",
}

CANNOT_CLAIM_ZH: list[str] = [
    "改善某一维度会带来因果效应",
    "预订需求或收入提升",
    "参考同行集是经核验的经济替代品",
    "评论情感变化等于实际管理干预",
    "保证改进或投资回报率（ROI）",
]

# --- Feasibility / research verdicts ---
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
    "A": "同行暴露下的供给侧推荐（研究轨道 A）",
    "B": "诊断≠行动；位置不可直接行动；证据不足时弃权",
    "C": "评论情感变化≠服务改进：测量风险视角（研究轨道 C）",
}

# --- Claims ledger finite mappings ---
CLAIM_TEXT_ZH: dict[str, str] = {
    "Demo is descriptive unless ledger upgrades it": "演示默认为描述性证据，除非本台账升级认定",
    "Geo kNN are candidate peers / geo reference sets": "地理 kNN 为候选同行/地理参考集（非经核验竞争对手）",
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

# --- Predictive model display names ---
MODEL_NAME_ZH: dict[str, str] = {
    "city_mean": "城市均值基线",
    "persistence": "持久性基线",
    "own_trend": "自身趋势",
    "own_features": "自身特征",
    "own_plus_peer_state": "自身+同行状态",
    "own_plus_peer_exposure": "自身+同行暴露",
    "own_plus_same_aspect_peer_state": "自身+同维度同行状态",
    "own_plus_same_aspect_peer_exposure": "自身+同维度同行暴露",
}

TARGET_LABEL_ZH: dict[str, str] = {
    "next_quarter_mean_reviewer_score": "下一季度平均住客评分",
}

SCORE_TERM_DEFINITIONS = (
    "**术语（可选）：** "
    "净情感 = 维度正面与负面提及的净值；"
    "差距 = 同行中位数净情感 − 本店净情感；"
    "负面率 = 负面提及占该维度提及的比例；"
    "可靠性 = 提及量越高越接近 1（经收缩处理）；"
    "差距/负面率归一化 = 本店各可操作维度内的 0–1 缩放。"
)

LIMITATIONS_ZH = """
- 评论条数**不等于**预订量或需求。
- 维度净情感来自评论情感，**不等于**经核验的管理干预效果。
- 参考同行集为标注参考集，**不等于**经核验的经济替代品。
- **同行相对证据加权**使用**设计权重**，非学习所得业务回报。
- **竞争拥挤假设**滑块为**假设/示意**，非拟合弹性。
- 位置可呈现为诊断劣势，但**不是**可直接运营的行动杠杆。
- 本演示**不宣称**事件研究、安慰剂或因果估计。
"""

HUMAN_CONFIRM_EXPANDER = """
人工仍需独立确认的事项（本演示**不能**替代人工标注或业务验收）：

1. **情感标注**：评论在某一维度上的正面/负面/中性判断是否准确？
2. **行动可行性**：建议维度在当前酒店是否真正可运营干预（含资本、合规、供应链约束）？
3. **证据充分性**：提及量、可靠性与时间覆盖是否足以支持决策，而非仅作探索性参考？

弱标签一致率反映机器规则一致性，**不等于**人工标注准确率；本仓库尚未完成独立人工复核验收。
"""


def aspect_label(aspect_id: str, fallback: str | None = None) -> str:
    return ASPECT_LABELS.get(aspect_id, fallback or aspect_id)


def city_label(city: str) -> str:
    return CITY_LABELS.get(city, city)


def compset_label(cs: str) -> str:
    if cs == "(all)":
        return "（全部）"
    return cs


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
    if key == "peer_relative" and backend_label:
        return HEURISTIC_NAME_ZH
    return POLICY_LABELS.get(key, backend_label or key)


def policy_rule(key: str, backend_rule: str | None = None, cfg: dict | None = None) -> str:
    rules = policy_rules(cfg) if cfg else POLICY_RULES
    return rules.get(key, backend_rule or "")


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


def build_diagnostic_explanation(expl: dict, label_fn: Callable[[str], str] = aspect_label) -> str | None:
    """Build Chinese explanation from diagnostic/action fields, not backend English text."""
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
        return (
            f"诊断层最大劣势维度为「{diag_label}」。"
            f"该维度不属于可直接运营干预的杠杆（如地理位置无法搬迁），"
            f"行动建议层因此转向可操作维度「{act_label}」。"
        )
    return (
        f"诊断层最大劣势维度为「{diag_label}」。"
        "该维度不属于可直接运营干预的杠杆，当前证据下行动层暂无对应直接建议。"
    )


def translate_claim_text(text: str) -> str:
    return CLAIM_TEXT_ZH.get(text.strip(), text.strip())


def translate_claim_status(status: str) -> str:
    s = status.strip()
    return CLAIM_STATUS_ZH.get(s, s)


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
    """Format pandas Interval or scalar bin label for histogram axes."""
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
