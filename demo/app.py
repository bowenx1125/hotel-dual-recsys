"""Streamlit: 酒店经理决策演示 + 时序研究实验台。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from demo.config import ROOT, load_actionability_config, load_config
from demo.data_adapter import eligible_hotels, load_snapshot
from demo.evidence import decide_evidence_level
from demo.scoring import (
    all_policies,
    criticism_metrics,
    explain_action_vs_diagnostic,
    ranking_under_intensity,
)
from demo import zh_cn as zh

SNAPSHOT_PATH = ROOT / "outputs" / "night_demo" / "demo_snapshot.json"

OVERNIGHT_FEAS = ROOT / "outputs" / "overnight" / "feasibility"
OVERNIGHT_TABLES = OVERNIGHT_FEAS / "tables"
PRED_METRICS_PATH = ROOT / "outputs" / "overnight" / "predictive_pilot" / "metrics.json"


def _load():
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(
            f"缺少 {SNAPSHOT_PATH}。请运行：python3 scripts/build_demo_snapshot.py"
        )
    snap = load_snapshot(SNAPSHOT_PATH)
    cfg = load_config()
    snap_cfg = snap.get("config") or {}
    cfg = {**snap_cfg, **cfg}
    return snap, cfg


def _load_facts() -> dict | None:
    facts_p = ROOT / "outputs" / "autonomous" / "FACTS.json"
    if not facts_p.exists():
        return None
    return json.loads(facts_p.read_text(encoding="utf-8"))


def _facts_waves(facts: dict | None) -> dict:
    return (facts or {}).get("waves") or {}


def _legacy_event_count(waves: dict) -> str:
    w0, w2 = waves.get("0") or {}, waves.get("2") or {}
    val = w2.get("legacy_permissive_event_count", w0.get("legacy_event_count_reproduced"))
    return zh.fmt_na(val)


def _strict_event_count(waves: dict) -> str:
    w2 = waves.get("2") or {}
    val = w2.get("strict_crossfit_events")
    if val is None:
        val = (w2.get("metrics") or {}).get("n")
    return zh.fmt_na(val)


def _download_button(st, label: str, path: Path, mime: str):
    if path.exists():
        st.download_button(
            label,
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
        )


def _render_verdict_event_chart(st, metrics: dict):
    """Chinese bar chart: historical permissive event counts from feasibility_metrics.json."""
    keys = [
        ("candidate_events", "候选事件（宽松规则）"),
        ("events_exposure_gt0", "暴露>0"),
        ("events_exposure_eq0", "暴露=0"),
        ("event_hotels", "涉及酒店"),
    ]
    rows = [
        {"指标": label, "数量": metrics.get(key)}
        for key, label in keys
        if metrics.get(key) is not None
    ]
    if not rows:
        st.info("暂无可绘制的候选事件汇总数据。")
        return
    import pandas as pd

    df = pd.DataFrame(rows).set_index("指标")
    st.caption("基于 feasibility_metrics.json 的宽松规则候选事件概览（非当前严格认定）。")
    st.bar_chart(df)


def _render_peer_exposure_chart(st):
    path = OVERNIGHT_TABLES / "candidate_events.csv"
    if not path.exists():
        st.info("未找到 candidate_events.csv，无法绘制同行暴露分布。")
        return
    import pandas as pd

    df = pd.read_csv(path, usecols=["peer_exposure"])
    series = df["peer_exposure"].dropna()
    if series.empty:
        st.info("同行暴露列为空，无法绘制分布。")
        return
    counts = series.value_counts(bins=30, sort=False)
    chart_df = pd.DataFrame(
        {"频数": counts.values},
        index=[zh.format_hist_bin(i) for i in counts.index],
    )
    chart_df.index.name = "暴露区间"
    st.caption("同行暴露分布（来自 candidate_events.csv）。")
    st.bar_chart(chart_df, sort=False)


def _render_delta_q_chart(st):
    path = OVERNIGHT_TABLES / "delta_q_sample.csv"
    if not path.exists():
        st.info("未找到 delta_q_sample.csv，无法绘制 Δq 分布。")
        return
    import pandas as pd

    df = pd.read_csv(path, usecols=["delta_q"])
    series = df["delta_q"].dropna()
    if series.empty:
        st.info("Δq 列为空，无法绘制分布。")
        return
    counts = series.value_counts(bins=30, sort=False)
    chart_df = pd.DataFrame(
        {"频数": counts.values},
        index=[zh.format_hist_bin(i) for i in counts.index],
    )
    chart_df.index.name = "变化区间"
    st.caption("评论感知维度变化（Δq）分布（来自 delta_q_sample.csv）。")
    st.bar_chart(chart_df, sort=False)


def _render_mae_chart(st, models: dict):
    if not models:
        st.info("暂无模型平均绝对误差数据可绘制。")
        return
    import pandas as pd

    rows = [
        {"模型": zh.model_name(k), "MAE": v.get("mae")}
        for k, v in models.items()
        if v.get("mae") is not None
    ]
    if not rows:
        st.info("模型平均绝对误差均为空，无法绘制对比图。")
        return
    mae_col = zh.mae_column_label()
    df = pd.DataFrame(rows).set_index("模型").rename(columns={"MAE": mae_col})
    st.caption("时间留出测试集上各基线模型的平均绝对误差对比。")
    st.bar_chart(df[[mae_col]])


def render_manager_tab(st, snap, cfg):
    ev = decide_evidence_level(snap)
    labels = cfg.get("aspect_labels") or {}
    act = load_actionability_config()["aspects"]
    hotels = eligible_hotels(snap)

    def albl(a: str) -> str:
        return zh.aspect_label(a, labels.get(a, a))

    st.subheader("酒店经理诊断")
    st.caption("面向经理 · 描述性证据 · 无外部 API")
    st.error(zh.evidence_banner(ev["level"]))
    with st.expander("证据等级说明 / 不可宣称事项", expanded=False):
        st.markdown(f"**等级：** {zh.evidence_level_label(ev['level'])}")
        st.write(zh.evidence_why(ev["level"], ev["why"]))
        for c in zh.CANNOT_CLAIM_ZH:
            st.markdown(f"- {c}")
        st.caption(
            f"数据来源：`{snap['sources']['aspect_features']}` · "
            f"`{snap['sources']['compsets']}` · `{snap['sources']['review_aspects_jsonl']}`"
        )

    cities = sorted({h["city"] for h in hotels})
    c1, c2, c3 = st.columns(3)
    with c1:
        city = st.selectbox(
            "城市",
            cities,
            index=0,
            key="mgr_city",
            format_func=zh.city_label,
        )
    hotels_c = [h for h in hotels if h["city"] == city]
    with c2:
        cs = st.selectbox(
            "标注参考同行集",
            ["(all)"] + sorted({h["compset_id"] for h in hotels_c}),
            key="mgr_cs",
            format_func=zh.compset_label,
        )
    hotels_f = hotels_c if cs == "(all)" else [h for h in hotels_c if h["compset_id"] == cs]
    with c3:
        names = {h["hotel_name"]: h["hotel_id"] for h in hotels_f}
        name = st.selectbox("酒店", list(names.keys()), key="mgr_hotel")
    hotel = next(h for h in hotels_f if h["hotel_id"] == names[name])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("参考集规模", hotel["compset_size"])
    m2.metric("标注评论数", hotel["n_reviews"])
    m3.metric("低分评论（<7）", hotel["n_negative"])
    m4.metric("价格档位", zh.price_tier_label(hotel.get("price_tier")))

    st.markdown("### 本店与同行对比（诊断层）")
    rows = []
    for a in cfg["aspects"]:
        rec = hotel["aspects"][a]
        meta = act.get(a, {})
        rows.append({
            "维度": albl(a),
            "可操作性": zh.actionability_label(meta.get("actionability_level")),
            "可直接行动": zh.fmt_bool(meta.get("eligible_for_direct_action")),
            "本店净情感": rec.get("net"),
            "同行中位数": rec.get("peer_median_net"),
            "差距(同行−本店)": rec.get("gap"),
            "百分位": rec.get("percentile"),
            "提及次数": rec.get("mention_count"),
            "负面提及": rec.get("neg_mentions"),
            "负面率": rec.get("neg_rate"),
            "每评论负面": criticism_metrics(hotel, a)["neg_per_review"],
            "可靠性": rec.get("reliability"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    expl = explain_action_vs_diagnostic(hotel, cfg)
    st.markdown("### 诊断劣势与可行动建议")
    d1, d2 = st.columns(2)
    d1.metric(
        "最大诊断劣势",
        albl(expl["diagnostic_aspect"]) if expl["diagnostic_aspect"] else "暂无",
    )
    d2.metric(
        "可行动建议（默认启发式）",
        albl(expl["actionable_recommendation"]) if expl["actionable_recommendation"] else "暂无",
    )
    zh_expl = zh.build_diagnostic_explanation(expl, albl)
    if zh_expl:
        st.warning(zh_expl)
    else:
        st.info("最大诊断劣势维度可直接行动；诊断层与行动层在可操作性上一致。")

    st.markdown("### 行动策略对比")
    st.caption(
        "行动层排除不可变维度（如位置）。权重为设计选择，非学习所得回报。"
    )
    intensity = st.slider(
        "竞争拥挤假设 — 假定同行改善强度（情景/示意）",
        min_value=0.0,
        max_value=1.0,
        value=float(cfg["scenario"]["default_intensity"]),
        step=0.05,
        help="假设/示意值，非拟合的竞争弹性。",
        key="mgr_intensity",
    )
    policies = all_policies(hotel, cfg, assumed_intensity=intensity)
    order = ["fix_weakest", "largest_peer_gap", "most_criticized", "peer_relative"]
    cols = st.columns(4)
    for col, key in zip(cols, order):
        p = policies[key]
        chosen = p["chosen_aspect"]
        col.metric(
            zh.policy_label(key, p.get("label")),
            albl(chosen) if chosen else "暂无",
        )
        col.caption(zh.policy_rule(key, p.get("rule"), cfg))

    pr = policies["peer_relative"]
    st.markdown(f"##### {zh.policy_label('peer_relative', pr.get('label'))} 得分表")
    scores0 = ranking_under_intensity(hotel, cfg, 0.0)
    scoresI = ranking_under_intensity(hotel, cfg, intensity)
    st.table({
        "维度": [albl(a) for a, _ in scoresI],
        f"得分@强度{intensity}": [round(s, 4) for _, s in scoresI],
        "得分@0": [round(dict(scores0).get(a, 0.0), 4) for a, _ in scoresI],
    })
    st.caption(zh.formula_caption(cfg))
    st.caption(zh.weights_caption(cfg))
    with st.expander("得分公式术语说明（可选）", expanded=False):
        st.markdown(zh.SCORE_TERM_DEFINITIONS)

    st.markdown("### 竞争拥挤假设（情景分析）")
    st.warning("情景分析 — 假定/示意。非经验拥挤曲线，非因果估计。")
    scen_rows = []
    for g in (0.0, 0.25, 0.5, 0.75, 1.0):
        rnk = ranking_under_intensity(hotel, cfg, g)
        scen_rows.append({
            "假定强度": g,
            "首选可操作维度": albl(rnk[0][0]) if rnk else None,
            "最高得分": round(rnk[0][1], 4) if rnk else None,
        })
    st.dataframe(scen_rows, hide_index=True, use_container_width=True)

    with st.expander("批评指标审计（计数、比率与每评论）"):
        crit_rows = []
        for a in cfg["aspects"]:
            if a not in hotel["aspects"]:
                continue
            m = criticism_metrics(hotel, a)
            crit_rows.append({
                "维度": albl(a),
                "负面提及": m["neg_mentions"],
                "负面率": m["neg_rate"],
                "每评论负面": round(m["neg_per_review"], 4),
                "可操作": zh.fmt_bool(act.get(a, {}).get("eligible_for_direct_action")),
            })
        st.dataframe(crit_rows, hide_index=True, use_container_width=True)
        st.caption(
            "默认「最受批评项」使用负面提及次数；比率与每评论指标仅供审计，不会静默替换。"
        )

    with st.expander("人工需确认的事项（非自动验收）", expanded=False):
        st.markdown(zh.HUMAN_CONFIRM_EXPANDER)

    st.markdown("### 数据溯源")
    prov_rows = [
        {"字段": "证据等级", "值": zh.evidence_level_label(ev["level"])},
        {"字段": "酒店编号", "值": hotel["hotel_id"]},
        {"字段": "参考组编号", "值": hotel["compset_id"]},
        {
            "字段": "诊断维度",
            "值": albl(expl["diagnostic_aspect"]) if expl["diagnostic_aspect"] else "暂无",
        },
        {
            "字段": "行动建议维度",
            "值": albl(expl["actionable_recommendation"])
            if expl["actionable_recommendation"]
            else "暂无",
        },
        {
            "字段": "策略选型",
            "值": zh.format_policy_selection(policies, order, albl),
        },
        {"字段": "配置", "值": "conf/demo.json"},
        {"字段": "可操作性配置", "值": "conf/actionability.json"},
        {"字段": "合成数据", "值": zh.fmt_bool(snap.get("synthetic"))},
    ]
    st.dataframe(prov_rows, hide_index=True, use_container_width=True)

    st.markdown("### 局限与边界")
    st.markdown(zh.LIMITATIONS_ZH)


def render_temporal_tab(st):
    st.subheader("历史时序分析")
    st.caption(
        "研究实验台 · 评论感知维度变化 · 地理参考集 · "
        "非因果 · 非管理干预 · 非经核验竞争对手"
    )
    waves = _facts_waves(_load_facts())
    w2, w5 = waves.get("2") or {}, waves.get("5") or {}
    legacy_n = _legacy_event_count(waves)
    strict_n = _strict_event_count(waves)
    strict_verdict = zh.strict_verdict_label(w2.get("verdict"))
    evt_strength = zh.event_study_strength_label(w5.get("classification"))
    st.warning(
        "**历史对照页：** 本页图表与指标来自 `outputs/overnight` 的**旧版宽松规则**流水线"
        f"（宽松候选事件 **{legacy_n}** 条）。"
        "这**不是**当前 `outputs/autonomous/FACTS.json` 中的严格交叉拟合事件认定"
        f"（当前严格事件 **{strict_n}** 条，判定 **{strict_verdict}**，{evt_strength}）。"
        "请以第三页「当前研究证据」为准。"
    )

    gate_path = OVERNIGHT_FEAS / "GO_NO_GO.md"
    metrics_path = OVERNIGHT_FEAS / "feasibility_metrics.json"
    panel_manifest = ROOT / "outputs" / "overnight" / "temporal_panel" / "panel_manifest.json"
    peer_manifest = ROOT / "outputs" / "overnight" / "peer_sets" / "peer_set_manifest.json"

    if panel_manifest.exists():
        pm = json.loads(panel_manifest.read_text(encoding="utf-8"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("季度单元格", pm.get("quarter_rows"))
        c2.metric("酒店数", pm.get("quarter_hotels"))
        c3.metric("城市数", pm.get("cities"))
        c4.metric("有效提及单元格", pm.get("valid_mention_cells_quarter"))
        st.caption(
            f"标注：结构性弱标签维度情感 · 先验强度={pm.get('prior_strength_main')} · "
            f"来源 sha256 `{str(pm.get('source_sha256', ''))[:12]}…`（本地缓存）"
        )
    else:
        st.info("时序面板尚未构建。")

    if peer_manifest.exists():
        peers = json.loads(peer_manifest.read_text(encoding="utf-8"))
        st.markdown("### 地理参考集")
        st.write(
            f"主设定：同城 Haversine k={peers.get('main_k')} · "
            f"酒店={peers.get('n_hotels')} · 城市={peers.get('n_cities')} · "
            "术语：**地理参考集/候选同行集**（非经核验的经济竞争对手）。"
        )

    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        verdict = metrics.get("verdict", "UNKNOWN")
        vlabel = zh.feasibility_verdict_label(verdict)
        if verdict == "GREEN":
            st.success(f"可行性判定：**{vlabel}**（历史宽松流水线）")
        elif verdict == "AMBER":
            st.warning(f"可行性判定：**{vlabel}**（历史宽松流水线）")
        else:
            st.error(f"可行性判定：**{vlabel}**（历史宽松流水线）")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("候选事件（宽松）", metrics.get("candidate_events"))
        m2.metric("涉及酒店", metrics.get("event_hotels"))
        m3.metric("暴露 > 0", metrics.get("events_exposure_gt0"))
        m4.metric("暴露 = 0", metrics.get("events_exposure_eq0"))
        st.markdown(
            f"- 变化阈值（预先确定）：**{metrics.get('main_delta_threshold')}**\n"
            f"- 有效酒店-季度-维度单元格：**{metrics.get('valid_cells')}**\n"
            f"- 覆盖 ≥4 期的酒店：**{metrics.get('hotels_with_enough_coverage')}**\n"
            f"- 变化项含义：**评论感知维度变化**（非管理干预）"
        )
        st.markdown("#### 图表")
        c_left, c_mid, c_right = st.columns(3)
        with c_left:
            _render_verdict_event_chart(st, metrics)
        with c_mid:
            _render_peer_exposure_chart(st)
        with c_right:
            _render_delta_q_chart(st)

        with st.expander("原始可行性指标（机器 JSON，可选下载）", expanded=False):
            st.caption("下方为英文 schema 原始文件，仅供审计；普通阅读请以上方中文摘要为准。")
            _download_button(st, "下载 feasibility_metrics.json", metrics_path, "application/json")
    else:
        st.info(
            "时序可行性产物尚未构建。"
            "预期包含：面板覆盖、候选变化、同行暴露、绿/琥珀/红判定。"
        )

    st.markdown("### 时间留出法预测试点（历史宽松上下文）")
    if PRED_METRICS_PATH.exists():
        pm = json.loads(PRED_METRICS_PATH.read_text(encoding="utf-8"))
        if pm.get("skipped"):
            st.warning(
                f"预测试点不可用或未通过门槛。"
                f"（{pm.get('verdict') or pm.get('reason') or '暂无原因'}）"
            )
        else:
            st.info(
                "仅为预测关联 — **不会**将经理页升级为预测性证据，"
                "**也不是**因果效应。"
            )
            models = pm.get("models") or {}
            st.dataframe(
                [
                    {
                        "模型": zh.model_name(k),
                        zh.mae_column_label(): v.get("mae"),
                        zh.rmse_column_label(): v.get("rmse"),
                    }
                    for k, v in models.items()
                ],
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                f"预测目标：{zh.target_label(pm.get('target'))} · "
                f"测试期：{pm.get('test_periods') or '暂无'} · "
                f"同行模型是否优于持久性：{zh.fmt_bool(pm.get('peer_model_improves_on_persistence'))}"
            )
            _render_mae_chart(st, models)
            _download_button(st, "下载 metrics.json（原始）", PRED_METRICS_PATH, "application/json")
    else:
        st.warning("预测试点不可用或未通过门槛。")

    st.markdown("### 本实验台可/不可宣称")
    st.markdown(
        """
**可宣称：** 描述性覆盖；时序测量的可行性；留出测试集上的预测关联（非因果）。

**不可宣称：** 同行因果干扰；投资回报；需求提升；将地理邻居称为经核验竞争对手；
将情感变化等同于管理干预；将宽松候选事件等同于当前严格事件认定。
"""
    )
    if gate_path.exists():
        with st.expander("通过/否决原始记录（可选下载）", expanded=False):
            st.caption("英文 Markdown 原文仅供下载审计，界面不直接展示全文。")
            _download_button(st, "下载 GO_NO_GO.md", gate_path, "text/markdown")


def render_research_evidence_tab(st):
    st.subheader("当前研究证据")
    st.caption("数字来自 outputs/autonomous/FACTS.json；演示不捏造指标。")
    facts_p = ROOT / "outputs" / "autonomous" / "FACTS.json"
    claims_p = ROOT / "outputs" / "autonomous" / "CLAIMS_LEDGER.md"

    if facts_p.exists():
        facts = json.loads(facts_p.read_text(encoding="utf-8"))
        waves = facts.get("waves") or {}
        w0 = waves.get("0") or {}
        w1, w2, w4, w5, w6 = (
            waves.get("1") or {},
            waves.get("2") or {},
            waves.get("4") or {},
            waves.get("5") or {},
            waves.get("6") or {},
        )
        st.info(
            "经理诊断页保持**描述性**证据等级，除非本台账正式升级。"
            "无因果效应 / 投资回报 / 需求提升宣称。"
            "测量证据与人工标注准确率是不同概念；**尚无独立人工复核验收**。"
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("测量证据", zh.measurement_label(w1.get("measurement_verdict")))
        c2.metric("严格交叉拟合事件", zh.fmt_na(w2.get("strict_crossfit_events")))
        c3.metric("同行预测主张", zh.peer_predictive_label(w4.get("peer_predictive_claim")))
        c4.metric("论文轨道", f"轨道 {w6.get('selected_track', '暂无')}")
        st.caption(
            f"FACTS sha256 `{str(facts.get('facts_sha256') or '')[:16]}…` · "
            f"历史宽松事件（仅对照）= {w2.get('legacy_permissive_event_count', w0.get('legacy_event_count_reproduced', '暂无'))}"
        )

        st.markdown("#### 当前事实摘要")
        track = w6.get("selected_track")
        summary_rows = [
            {"项目": "完整季度", "值": ", ".join(w1.get("complete_periods") or []) or "暂无"},
            {"项目": "不完整季度（已排除）", "值": ", ".join(w1.get("partial_periods") or []) or "暂无"},
            {"项目": "严格事件判定", "值": zh.strict_verdict_label(w2.get("verdict"))},
            {
                "项目": "严格事件数",
                "值": zh.fmt_na((w2.get("metrics") or {}).get("n", w2.get("strict_crossfit_events"))),
            },
            {"项目": "事件研究证据强度", "值": zh.event_study_strength_label(w5.get("classification"))},
            {
                "项目": f"轨道 {track or '暂无'} 表述",
                "值": zh.track_formulation(track, w6),
            },
            {"项目": "非因果声明", "值": "是"},
        ]
        st.dataframe(summary_rows, hide_index=True, use_container_width=True)

        st.markdown(
            f"**与历史页对照：** 旧版宽松流水线共 **{_legacy_event_count(waves)}** 条宽松候选事件；"
            f"当前严格认定 **{_strict_event_count(waves)}** 条，"
            f"同行预测 **{zh.peer_predictive_label(w4.get('peer_predictive_claim'))}**，"
            f"**{zh.event_study_strength_label(w5.get('classification'))}**。"
        )
    else:
        st.warning("尚未构建 autonomous/FACTS.json。")

    if claims_p.exists():
        md = claims_p.read_text(encoding="utf-8")
        rows = zh.parse_claims_ledger(md)
        st.markdown("#### 主张台账")
        if rows:
            st.dataframe(
                [
                    {
                        "编号": r["id"],
                        "主张": r["claim_zh"],
                        "状态": r["status_zh"],
                        "备注": r["notes"],
                    }
                    for r in rows
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("台账表格为空或无法解析。")
        with st.expander("原始台账文件（可选下载）", expanded=False):
            st.caption("英文 Markdown 原文；界面以上方中文表为准，状态值来自实时文件。")
            _download_button(st, "下载 CLAIMS_LEDGER.md", claims_p, "text/markdown")
    else:
        st.warning("尚未构建 CLAIMS_LEDGER.md。")

    if facts_p.exists():
        with st.expander("原始 FACTS（可选下载）", expanded=False):
            _download_button(st, "下载 FACTS.json", facts_p, "application/json")

    with st.expander("人工需确认的事项（非自动验收）", expanded=False):
        st.markdown(zh.HUMAN_CONFIRM_EXPANDER)


def main():
    import streamlit as st

    st.set_page_config(page_title="酒店经理决策演示", layout="wide")
    snap, cfg = _load()
    st.title("酒店经理决策演示")
    tab1, tab2, tab3 = st.tabs([
        "酒店经理诊断",
        "历史时序分析",
        "当前研究证据",
    ])
    with tab1:
        render_manager_tab(st, snap, cfg)
    with tab2:
        render_temporal_tab(st)
    with tab3:
        render_research_evidence_tab(st)


if __name__ == "__main__":
    main()
