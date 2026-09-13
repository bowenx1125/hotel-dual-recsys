"""Locale routing for the Streamlit demo. No session-scoped mutable module state."""
from __future__ import annotations

from demo import en as _en
from demo import zh_cn as _zh

SUPPORTED_LANGUAGES: tuple[str, ...] = ("zh", "en")
DEFAULT_LANGUAGE = "zh"

LANGUAGE_LABELS: dict[str, str] = {
    "zh": "中文",
    "en": "English",
}


def normalize_language(code: str | None) -> str:
    if code in SUPPORTED_LANGUAGES:
        return code
    return DEFAULT_LANGUAGE


def get_locale(code: str | None = None):
    """Return the locale module for ``code`` (immutable per language)."""
    return _zh if normalize_language(code) == "zh" else _en


def ui_text(loc, key: str, **kwargs: object) -> str:
    """Look up a UI string; format with kwargs when placeholders are present."""
    template = loc.UI[key]
    return template.format(**kwargs) if kwargs else template
