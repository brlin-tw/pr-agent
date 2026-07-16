"""Internationalization helpers for user-visible PR-Agent messages."""

from __future__ import annotations

import gettext as gettext_module
import re
from functools import lru_cache
from pathlib import Path

from pr_agent.config_loader import get_settings

DOMAIN = "pr_agent"
LOCALE_DIR = Path(__file__).with_name("locales")
DEFAULT_LOCALE = "en_US"
_LOCALE_PATTERN = re.compile(
    r"^(?P<language>[A-Za-z]{2,3})(?:[-_](?P<territory>[A-Za-z]{2}|\d{3}))?(?:\.[A-Za-z0-9_-]+)?$"
)


def normalize_locale(locale: str | None) -> str:
    """Normalize a locale code to the language[_TERRITORY] form used by gettext."""
    if not locale:
        return DEFAULT_LOCALE
    match = _LOCALE_PATTERN.fullmatch(str(locale).strip())
    if not match:
        return DEFAULT_LOCALE
    language = match.group("language").lower()
    territory = match.group("territory")
    return f"{language}_{territory.upper()}" if territory else language


def get_locale() -> str:
    """Return the locale selected for the current request or process settings."""
    return normalize_locale(get_settings().config.get("response_language", DEFAULT_LOCALE))


@lru_cache(maxsize=64)
def get_translation(locale: str) -> gettext_module.NullTranslations:
    """Load and cache an immutable translation catalog for a normalized locale."""
    return gettext_module.translation(
        DOMAIN,
        localedir=LOCALE_DIR,
        languages=[normalize_locale(locale)],
        fallback=True,
    )


def gettext(message: str, locale: str | None = None) -> str:
    """Translate a user-visible message using the configured response locale."""
    selected_locale = normalize_locale(locale) if locale is not None else get_locale()
    return get_translation(selected_locale).gettext(message)


def ngettext(singular: str, plural: str, count: int, locale: str | None = None) -> str:
    """Translate a plural-aware user-visible message."""
    selected_locale = normalize_locale(locale) if locale is not None else get_locale()
    return get_translation(selected_locale).ngettext(singular, plural, count)
