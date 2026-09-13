"""Dark theme helpers for the hotel manager Streamlit demo (FYP-CURSOR-004)."""
from __future__ import annotations

import html
import itertools
from pathlib import Path

_CSS_PATH = Path(__file__).resolve().parent / "assets" / "dark.css"

_section_ids = itertools.count(1)


def _load_css() -> str:
    return _CSS_PATH.read_text(encoding="utf-8")


def _inject_html(st, markup: str) -> None:
    if hasattr(st, "html"):
        st.html(markup)
    else:
        st.markdown(markup, unsafe_allow_html=True)


def apply_theme(st) -> None:
    """Inject locally bundled dark-theme CSS into the active Streamlit page."""
    css = _load_css()
    _inject_html(st, f"<style>\n{css}\n</style>")


def render_header(st, title: str, description: str, badge: str) -> None:
    """Render branded page header with subdued description and evidence badge."""
    safe_title = html.escape(title or "", quote=True)
    safe_desc = html.escape(description or "", quote=True)
    safe_badge = html.escape(badge or "", quote=True)
    _inject_html(
        st,
        f"""<header class="fyp-header" role="banner">
  <div class="fyp-header__brand">
    <h1 class="fyp-header__title">{safe_title}</h1>
    <p class="fyp-header__desc">{safe_desc}</p>
  </div>
  <span class="fyp-header__badge" role="status">{safe_badge}</span>
</header>""",
    )


def render_section_header(
    st,
    title: str,
    description: str | None = None,
    *,
    css_class: str | None = None,
) -> None:
    """Render a compact section heading with optional supporting text."""
    sec_id = f"fyp-sec-{next(_section_ids)}"
    safe_title = html.escape(title or "", quote=True)
    desc_block = ""
    labelledby = f"{sec_id}-title"
    if description:
        safe_desc = html.escape(description, quote=True)
        desc_block = f'\n  <p class="fyp-section-header__desc" id="{sec_id}-desc">{safe_desc}</p>'
        labelledby = f"{sec_id}-title {sec_id}-desc"
    section_class = "fyp-section-header"
    if css_class:
        section_class = f"{section_class} {css_class}"
    _inject_html(
        st,
        f"""<section class="{section_class}" id="{sec_id}" aria-labelledby="{labelledby}">
  <h2 class="fyp-section-header__title" id="{sec_id}-title">{safe_title}</h2>{desc_block}
</section>""",
    )


def render_recommendation(
    st,
    aspect_label: str,
    explanation: str,
    reliability_text: str | None = None,
    aria_label: str = "Improvement suggestion",
) -> None:
    """Render a single recommendation card; all caller text is HTML-escaped."""
    safe_aspect = html.escape(aspect_label or "", quote=True)
    safe_expl = html.escape(explanation or "", quote=True)
    safe_aria = html.escape(aria_label or "", quote=True)
    rel_block = ""
    if reliability_text:
        safe_rel = html.escape(reliability_text, quote=True)
        rel_block = f'\n  <p class="fyp-recommendation__reliability">{safe_rel}</p>'
    _inject_html(
        st,
        f"""<article class="fyp-recommendation" aria-label="{safe_aria}">
  <h3 class="fyp-recommendation__aspect">{safe_aspect}</h3>
  <p class="fyp-recommendation__body">{safe_expl}</p>{rel_block}
</article>""",
    )
