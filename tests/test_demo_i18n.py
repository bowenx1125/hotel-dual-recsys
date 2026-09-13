#!/usr/bin/env python3
"""Unit tests for demo bilingual UI helpers (FYP-CURSOR-004)."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo import en, zh_cn
from demo.app import (
    MGR_CITY_CANONICAL,
    MGR_CS_CANONICAL,
    hydrate_locale_select_state,
    sync_canonical_from_locale_widget,
)
from demo.config import load_config
from demo.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    SUPPORTED_LANGUAGES,
    get_locale,
    normalize_language,
    ui_text,
)

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")


def _placeholder_names(template: str) -> set[str]:
    return {m.split(":")[0].strip() for m in PLACEHOLDER_RE.findall(template)}


class TestLocaleRouting(unittest.TestCase):
    def test_supported_languages(self):
        self.assertEqual(SUPPORTED_LANGUAGES, ("zh", "en"))
        self.assertEqual(LANGUAGE_LABELS["zh"], "中文")
        self.assertEqual(LANGUAGE_LABELS["en"], "English")

    def test_normalize_language_defaults(self):
        self.assertEqual(normalize_language(None), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language("fr"), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language("en"), "en")

    def test_get_locale_returns_distinct_modules(self):
        zh = get_locale("zh")
        en_loc = get_locale("en")
        self.assertIs(zh, zh_cn)
        self.assertIs(en_loc, en)
        self.assertIsNot(zh, en_loc)

    def test_locale_modules_are_stable_singletons(self):
        self.assertIs(get_locale("zh"), get_locale("zh"))
        self.assertIs(get_locale("en"), get_locale("en"))
        self.assertNotEqual(zh_cn.UI["header_title"], en.UI["header_title"])


class TestKeyTranslations(unittest.TestCase):
    def test_tab_labels(self):
        self.assertEqual(zh_cn.UI["tab_improvement"], "改善建议")
        self.assertEqual(zh_cn.UI["tab_history"], "历史变化")
        self.assertEqual(zh_cn.UI["tab_research"], "研究进展")
        self.assertEqual(en.UI["tab_improvement"], "Improvement priorities")
        self.assertEqual(en.UI["tab_history"], "Changes over time")
        self.assertEqual(en.UI["tab_research"], "Research progress")

    def test_header_copy(self):
        self.assertEqual(zh_cn.UI["header_title"], "酒店改善助手")
        self.assertEqual(zh_cn.UI["page_title"], "酒店改善助手")
        self.assertEqual(en.UI["header_title"], "Hotel Improvement Assistant")
        self.assertIn("选一家酒店", zh_cn.UI["header_desc"])
        self.assertIn("Pick a hotel", en.UI["header_desc"])

    def test_manager_facing_labels(self):
        self.assertEqual(zh_cn.UI["peer_group"], "对比酒店分组")
        self.assertEqual(zh_cn.UI["hotel"], "选择酒店")
        self.assertEqual(zh_cn.price_tier_label("low"), "较低")
        self.assertEqual(en.price_tier_label("low"), "Lower")

    def test_policy_summaries_exist(self):
        for key in ("fix_weakest", "largest_peer_gap", "most_criticized", "peer_relative"):
            self.assertTrue(zh_cn.policy_summary(key))
            self.assertTrue(en.policy_summary(key))

    def test_peer_relative_summary_mentions_rate_not_volume_only(self):
        summary = en.policy_summary("peer_relative")
        self.assertIn("negative-review share", summary)
        self.assertNotIn("complaint volume", summary)

    def test_chart_plain_language_zh(self):
        self.assertEqual(zh_cn.UI["chart_sentiment_axis"], "好评与差评的总体倾向")
        self.assertNotIn("净情感", zh_cn.UI["chart_sentiment_axis"])


class TestLocaleCatalog(unittest.TestCase):
    def test_ui_key_sets_match(self):
        self.assertEqual(set(zh_cn.UI.keys()), set(en.UI.keys()))

    def test_format_placeholder_sets_match(self):
        mismatches = []
        for key in sorted(zh_cn.UI):
            zh_ph = _placeholder_names(zh_cn.UI[key])
            en_ph = _placeholder_names(en.UI[key])
            if zh_ph != en_ph:
                mismatches.append((key, zh_ph, en_ph))
        self.assertEqual(mismatches, [])

    def test_helper_numeric_placeholders_match_non_default_config(self):
        cfg = load_config()
        alt = {
            **cfg,
            "min_mentions": 7,
            "weights": {"gap": 0.5, "criticism": 0.3, "unreliable": 0.2},
        }
        for key in ("fix_weakest", "largest_peer_gap", "most_criticized", "peer_relative"):
            zh_nums = re.findall(r"\d+\.?\d*", zh_cn.policy_rule(key, cfg=alt))
            en_nums = re.findall(r"\d+\.?\d*", en.policy_rule(key, cfg=alt))
            self.assertEqual(zh_nums, en_nums, msg=key)
        self.assertIn("7", zh_cn.policy_rule("fix_weakest", cfg=alt))
        self.assertIn("0.5", zh_cn.policy_rule("peer_relative", cfg=alt))

    def test_no_cjk_in_english_display_strings(self):
        english_sources = [
            ("UI", en.UI),
            ("POLICY_LABELS", en.POLICY_LABELS),
            ("POLICY_SUMMARIES", en.POLICY_SUMMARIES),
            ("ASPECT_LABELS", en.ASPECT_LABELS),
            ("EVIDENCE_BANNERS", en.EVIDENCE_BANNERS),
        ]
        for source_name, mapping in english_sources:
            for key, value in mapping.items():
                self.assertFalse(
                    CJK_RE.search(value),
                    msg=f"{source_name}[{key}] contains CJK: {value!r}",
                )


class TestLocaleSelectSync(unittest.TestCase):
    def test_hydrate_copies_canonical_into_locale_widget(self):
        state = {MGR_CITY_CANONICAL: "Paris"}
        value = hydrate_locale_select_state(
            state,
            MGR_CITY_CANONICAL,
            "mgr_city_en",
            ["Brussels", "Paris"],
            "Brussels",
        )
        self.assertEqual(value, "Paris")
        self.assertEqual(state["mgr_city_en"], "Paris")

    def test_hydrate_resets_invalid_canonical_to_default(self):
        state = {MGR_CITY_CANONICAL: "Milan", MGR_CS_CANONICAL: "missing"}
        hydrate_locale_select_state(
            state,
            MGR_CS_CANONICAL,
            "mgr_cs_zh",
            ["(all)", "cs_1"],
            "(all)",
        )
        self.assertEqual(state[MGR_CS_CANONICAL], "(all)")
        self.assertEqual(state["mgr_cs_zh"], "(all)")

    def test_sync_persists_locale_widget_before_language_switch(self):
        state = {
            MGR_CITY_CANONICAL: "Brussels",
            "mgr_city_en": "Paris",
        }
        sync_canonical_from_locale_widget(state, MGR_CITY_CANONICAL, "mgr_city_en")
        self.assertEqual(state[MGR_CITY_CANONICAL], "Paris")
        hydrate_locale_select_state(
            state,
            MGR_CITY_CANONICAL,
            "mgr_city_zh",
            ["Brussels", "Paris"],
            "Brussels",
        )
        self.assertEqual(state["mgr_city_zh"], "Paris")


class TestGapPhrasing(unittest.TestCase):
    def test_format_gap_vs_median_uses_absolute_distance(self):
        self.assertEqual(en.format_gap_vs_median(0.12), "0.120 below comparison median")
        self.assertEqual(en.format_gap_vs_median(-0.05), "0.050 above comparison median")
        self.assertEqual(en.format_gap_vs_median(0.0), "equal to comparison median")
        self.assertEqual(en.format_gap_vs_median(None), "N/A")


class TestUiTextHelper(unittest.TestCase):
    def test_ui_text_formats_placeholders(self):
        out = ui_text(zh_cn, "snapshot_caption", total=24, eligible=22)
        self.assertIn("24", out)
        self.assertIn("22", out)

    def test_backend_aspect_ids_stable(self):
        self.assertEqual(zh_cn.aspect_label("cleanliness", "cleanliness"), "清洁")
        self.assertEqual(en.aspect_label("cleanliness", "cleanliness"), "Cleanliness")
        self.assertEqual(zh_cn.compset_label("(all)"), "（全部）")
        self.assertEqual(en.compset_label("(all)"), "All groups")


if __name__ == "__main__":
    unittest.main()
