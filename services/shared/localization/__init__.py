"""Multi-language localization framework for the Rural Credit Advisory System.

Supports Requirement 10.1 (multiple local languages) and Requirement 10.3
(culturally appropriate examples/explanations).

Supported languages:
- en: English (default / fallback)
- hi: Hindi (हिन्दी)
- ta: Tamil (தமிழ்)
- te: Telugu (తెలుగు)
- kn: Kannada (ಕನ್ನಡ)
- mr: Marathi (मराठी)

Usage:
    from services.shared.localization import get_translator, SupportedLanguage

    t = get_translator(SupportedLanguage.HINDI)
    msg = t.translate("risk.category.high")
    # → "उच्च जोखिम"

    # With variable substitution:
    msg = t.translate("loan.emi_amount", amount="₹4,500", months=12)
    # → "आपकी मासिक EMI ₹4,500 होगी, 12 महीनों के लिए"
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------
class SupportedLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    TAMIL = "ta"
    TELUGU = "te"
    KANNADA = "kn"
    MARATHI = "mr"


LANGUAGE_NAMES: dict[SupportedLanguage, str] = {
    SupportedLanguage.ENGLISH: "English",
    SupportedLanguage.HINDI: "हिन्दी (Hindi)",
    SupportedLanguage.TAMIL: "தமிழ் (Tamil)",
    SupportedLanguage.TELUGU: "తెలుగు (Telugu)",
    SupportedLanguage.KANNADA: "ಕನ್ನಡ (Kannada)",
    SupportedLanguage.MARATHI: "मराठी (Marathi)",
}

DEFAULT_LANGUAGE = SupportedLanguage.ENGLISH


# ---------------------------------------------------------------------------
# Message catalog type
# ---------------------------------------------------------------------------
MessageCatalog = dict[str, str]  # key -> translated message


# ---------------------------------------------------------------------------
# Translator
# ---------------------------------------------------------------------------
class Translator:
    """Translates message keys to the target language.

    Falls back to English if a key is not found in the target language.
    Supports {variable} substitution in messages.
    """

    def __init__(
        self,
        language: SupportedLanguage,
        catalog: MessageCatalog,
        fallback_catalog: MessageCatalog | None = None,
    ) -> None:
        self._language = language
        self._catalog = catalog
        self._fallback = fallback_catalog or {}

    @property
    def language(self) -> SupportedLanguage:
        return self._language

    def translate(self, key: str, **kwargs: Any) -> str:
        """Look up a message key and substitute variables.

        Falls back to English if key not found, then to the raw key.
        """
        template = self._catalog.get(key)
        if template is None:
            template = self._fallback.get(key)
        if template is None:
            logger.warning(
                "Missing translation: lang=%s key=%s", self._language, key,
            )
            return key
        try:
            return template.format(**kwargs) if kwargs else template
        except KeyError as exc:
            logger.warning(
                "Translation format error: lang=%s key=%s missing=%s",
                self._language, key, exc,
            )
            return template

    def has_key(self, key: str) -> bool:
        return key in self._catalog or key in self._fallback

    def available_keys(self) -> list[str]:
        keys = set(self._catalog.keys())
        if self._fallback:
            keys |= set(self._fallback.keys())
        return sorted(keys)


# ---------------------------------------------------------------------------
# Catalog registry
# ---------------------------------------------------------------------------
_catalogs: dict[SupportedLanguage, MessageCatalog] = {}


def register_catalog(
    language: SupportedLanguage,
    catalog: MessageCatalog,
) -> None:
    """Register a message catalog for a language."""
    existing = _catalogs.get(language, {})
    existing.update(catalog)
    _catalogs[language] = existing
    logger.debug("Registered %d messages for %s", len(catalog), language.value)


def get_catalog(language: SupportedLanguage) -> MessageCatalog:
    """Get the message catalog for a language."""
    return _catalogs.get(language, {})


def get_translator(language: SupportedLanguage | str) -> Translator:
    """Get a Translator for the given language.

    Falls back to English for missing keys.
    """
    if isinstance(language, str):
        try:
            language = SupportedLanguage(language)
        except ValueError:
            logger.warning("Unsupported language '%s', falling back to English", language)
            language = DEFAULT_LANGUAGE

    catalog = get_catalog(language)
    fallback = get_catalog(DEFAULT_LANGUAGE) if language != DEFAULT_LANGUAGE else {}
    return Translator(language, catalog, fallback)


def list_supported_languages() -> list[dict[str, str]]:
    """Return a list of supported languages with metadata."""
    return [
        {"code": lang.value, "name": LANGUAGE_NAMES[lang]}
        for lang in SupportedLanguage
    ]
