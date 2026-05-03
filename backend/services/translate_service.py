"""
backend/services/translate_service.py
──────────────────────────────────────
Google Cloud Translation API wrapper.

Supports multi-language voter education content for:
  - English (en) — default
  - Hindi (hi)
  - Marathi (mr)
  - Tamil (ta)

Uses Google Cloud Translation Basic (v2) API.
Free tier: 500,000 characters/month.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final

import requests

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Supported languages — aligned with Indian voter accessibility requirements
SUPPORTED_LANGUAGES: Final[dict[str, str]] = {
    "English": "en",
    "Hindi": "hi",
    "Marathi": "mr",
    "Tamil": "ta",
}

_TRANSLATE_URL: Final[str] = (
    "https://translation.googleapis.com/language/translate/v2"
)


class TranslateService:
    """
    Google Cloud Translation API v2 wrapper.

    Translates election guide responses into regional Indian languages
    to serve voters who are not comfortable with English.

    All methods degrade gracefully when the API key is not configured.
    """

    def __init__(self) -> None:
        self._api_key = settings.google_api_key  # Reuses the same GCP key
        self._cache: dict[str, str] = {}
        logger.info("TranslateService ready", supported=list(SUPPORTED_LANGUAGES.keys()))

    def translate(self, text: str, target_language: str) -> str:
        """
        Translate text to the target language.

        Parameters
        ----------
        text            : Source text to translate (English).
        target_language : BCP-47 language code, e.g. 'hi', 'mr', 'ta'.

        Returns
        -------
        Translated text, or the original text if translation fails.
        """
        if not text or not text.strip():
            return text

        if target_language == "en":
            return text  # No-op for English

        if not self._api_key:
            logger.debug("Translation API key not configured — returning original text")
            return text

        # Cache key: first 100 chars of text + target language
        cache_key = f"{text[:100]}:{target_language}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            resp = requests.post(
                _TRANSLATE_URL,
                params={"key": self._api_key},
                json={"q": text, "target": target_language, "format": "text"},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            translated = data["data"]["translations"][0]["translatedText"]
            self._cache[cache_key] = translated
            logger.debug("Translation complete", target=target_language, chars=len(text))
            return translated

        except Exception as exc:
            logger.warning(
                "Translation failed — returning original",
                target=target_language,
                error=str(exc),
            )
            return text

    def get_language_code(self, language_name: str) -> str:
        """
        Convert a display language name to BCP-47 code.

        Parameters
        ----------
        language_name : Display name, e.g. 'Hindi'.

        Returns
        -------
        BCP-47 code (e.g. 'hi') or 'en' if not found.
        """
        return SUPPORTED_LANGUAGES.get(language_name, "en")

    def is_available(self) -> bool:
        """Return True if the Translation API is configured and reachable."""
        return bool(self._api_key)


# ── Module-level singleton ────────────────────────────────────────────────────
_translate_service: TranslateService | None = None


@lru_cache(maxsize=1)
def get_translate_service() -> TranslateService:
    """Return the cached singleton TranslateService instance."""
    return TranslateService()
