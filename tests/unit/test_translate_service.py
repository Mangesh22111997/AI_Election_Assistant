"""
tests/test_translate_service.py
────────────────────────────────
Unit tests for TranslateService.
All tests mock the HTTP call — no real API calls made.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from backend.services.translate_service import (
    TranslateService,
    SUPPORTED_LANGUAGES,
    get_translate_service,
)


@pytest.fixture
def service():
    with patch("backend.services.translate_service.settings") as mock_settings:
        mock_settings.google_api_key = "test-api-key"
        svc = TranslateService()
    return svc


@pytest.fixture
def service_no_key():
    with patch("backend.services.translate_service.settings") as mock_settings:
        mock_settings.google_api_key = ""
        svc = TranslateService()
    return svc


class TestTranslateService:

    def test_english_returns_unchanged(self, service: TranslateService) -> None:
        text = "How do I register to vote?"
        result = service.translate(text, "en")
        assert result == text

    def test_empty_text_returns_unchanged(self, service: TranslateService) -> None:
        result = service.translate("", "hi")
        assert result == ""

    def test_whitespace_text_returns_unchanged(self, service: TranslateService) -> None:
        result = service.translate("   ", "hi")
        assert result == "   "

    def test_no_api_key_returns_original(self, service_no_key: TranslateService) -> None:
        text = "Voter registration steps."
        result = service_no_key.translate(text, "hi")
        assert result == text

    @patch("backend.services.translate_service.requests.post")
    def test_successful_translation(self, mock_post, service: TranslateService) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"translations": [{"translatedText": "मतदाता पंजीकरण"}]}
        }
        mock_post.return_value = mock_resp
        result = service.translate("Voter registration", "hi")
        assert result == "मतदाता पंजीकरण"

    @patch("backend.services.translate_service.requests.post")
    def test_api_error_returns_original(self, mock_post, service: TranslateService) -> None:
        mock_post.side_effect = Exception("Network error")
        text = "Voter registration steps."
        result = service.translate(text, "hi")
        assert result == text

    @patch("backend.services.translate_service.requests.post")
    def test_translation_cached(self, mock_post, service: TranslateService) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"translations": [{"translatedText": "कैसे मतदान करें"}]}
        }
        mock_post.return_value = mock_resp

        text = "How to vote"
        service.translate(text, "hi")
        service.translate(text, "hi")
        # API should only be called once due to caching
        assert mock_post.call_count == 1

    def test_get_language_code_english(self, service: TranslateService) -> None:
        assert service.get_language_code("English") == "en"

    def test_get_language_code_hindi(self, service: TranslateService) -> None:
        assert service.get_language_code("Hindi") == "hi"

    def test_get_language_code_unknown_defaults_to_english(
        self, service: TranslateService
    ) -> None:
        assert service.get_language_code("Klingon") == "en"

    def test_is_available_with_key(self, service: TranslateService) -> None:
        assert service.is_available() is True

    def test_is_available_without_key(self, service_no_key: TranslateService) -> None:
        assert service_no_key.is_available() is False


class TestSupportedLanguages:

    def test_english_in_supported(self) -> None:
        assert "English" in SUPPORTED_LANGUAGES

    def test_hindi_in_supported(self) -> None:
        assert "Hindi" in SUPPORTED_LANGUAGES

    def test_all_codes_are_bcp47(self) -> None:
        for code in SUPPORTED_LANGUAGES.values():
            assert len(code) == 2
