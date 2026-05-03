"""
tests/test_gemini_service.py
─────────────────────────────
Unit tests for GeminiService.
All tests mock the underlying Gemini SDK — no real API calls.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


@pytest.fixture
def mock_model():
    """A mock of genai.GenerativeModel."""
    model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        "To register, visit nvsp.in. "
        "[Source 1: ECI Voter Guide]\n\n"
        "🤖 AI-generated educational content. "
        "Always verify with your local election office."
    )
    model.generate_content.return_value = mock_response
    return model


@pytest.fixture
def gemini_service(mock_model):
    """GeminiService with all external calls mocked."""
    with (
        patch("backend.services.gemini_service.genai.configure"),
        patch("backend.services.gemini_service.genai.GenerativeModel", return_value=mock_model),
        patch("backend.services.gemini_service.genai.GenerationConfig"),
    ):
        # Reset the singleton
        import backend.services.gemini_service as mod
        mod._gemini_service = None
        from backend.services.gemini_service import GeminiService
        svc = GeminiService()
        svc._model = mock_model
        return svc


class TestGeminiServiceGenerate:

    def test_generate_returns_string(self, gemini_service, mock_model) -> None:
        result = gemini_service.generate(prompt="How do I vote?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_calls_model(self, gemini_service, mock_model) -> None:
        gemini_service.generate(prompt="How do I register?")
        mock_model.generate_content.assert_called_once()

    def test_generate_with_system_instruction(self, gemini_service, mock_model) -> None:
        gemini_service.generate(
            prompt="What is Form 6?",
            system_instruction="You are an election expert.",
        )
        call_args = mock_model.generate_content.call_args[0][0]
        assert "You are an election expert." in call_args
        assert "What is Form 6?" in call_args

    def test_generate_increments_usage(self, gemini_service) -> None:
        before = gemini_service.usage["requests"]
        gemini_service.generate(prompt="How do I vote?")
        after = gemini_service.usage["requests"]
        assert after == before + 1

    def test_generate_blocked_response_fallback(self, gemini_service, mock_model) -> None:
        """If response.text raises ValueError (blocked), returns a safe fallback."""
        mock_blocked = MagicMock()
        type(mock_blocked).text = PropertyMock(side_effect=ValueError("Blocked"))
        mock_model.generate_content.return_value = mock_blocked

        result = gemini_service.generate(prompt="Some query")
        assert "election office" in result.lower()


class TestGeminiServiceBuildPrompt:

    def test_no_system_instruction(self, gemini_service) -> None:
        result = gemini_service._build_prompt("Test prompt", None)
        assert result == "Test prompt"

    def test_with_system_instruction(self, gemini_service) -> None:
        result = gemini_service._build_prompt("User message", "System context")
        assert "System context" in result
        assert "User message" in result
        assert "---" in result


class TestGeminiServiceExtractText:

    def test_extract_from_valid_response(self, gemini_service) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "Hello voter"
        assert gemini_service._extract_text(mock_resp) == "Hello voter"

    def test_extract_attribute_error_returns_fallback(self, gemini_service) -> None:
        mock_resp = MagicMock(spec=[])  # No attributes
        result = gemini_service._extract_text(mock_resp)
        assert "election office" in result.lower()

    def test_extract_value_error_returns_fallback(self, gemini_service) -> None:
        mock_resp = MagicMock()
        type(mock_resp).text = PropertyMock(side_effect=ValueError("blocked"))
        result = gemini_service._extract_text(mock_resp)
        assert "election office" in result.lower()


class TestGeminiServiceUsage:

    def test_usage_returns_dict(self, gemini_service) -> None:
        usage = gemini_service.usage
        assert isinstance(usage, dict)
        assert "requests" in usage
        assert "tokens" in usage

    def test_usage_returns_copy(self, gemini_service) -> None:
        """Modifying the returned dict should not affect internal state."""
        usage = gemini_service.usage
        usage["requests"] = 9999
        assert gemini_service.usage["requests"] != 9999


class TestGeminiServiceChat:

    def test_chat_calls_model(self, gemini_service, mock_model) -> None:
        mock_session = MagicMock()
        mock_session.send_message.return_value = MagicMock(text="Chat response")
        mock_model.start_chat.return_value = mock_session

        result = gemini_service.chat(
            history=[{"role": "user", "parts": "Hello"}],
            new_message="How do I vote?",
        )
        assert isinstance(result, str)
        mock_session.send_message.assert_called_once_with("How do I vote?")

    def test_chat_exception_propagates(self, gemini_service, mock_model) -> None:
        mock_session = MagicMock()
        mock_session.send_message.side_effect = Exception("API error")
        mock_model.start_chat.return_value = mock_session

        with pytest.raises(Exception, match="API error"):
            gemini_service.chat(history=[], new_message="Hello")
