"""
tests/test_simplifier_agent.py
────────────────────────────────
Unit tests for SimplifierAgent.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_gemini():
    svc = MagicMock()
    svc.generate.return_value = (
        "To register to vote, go to the website. "
        "Fill out the form. "
        "Submit it before the deadline.\n\n"
        "🤖 AI-generated educational content. "
        "Always verify with your local election office."
    )
    return svc


@pytest.fixture
def simplifier(mock_gemini):
    with patch("backend.agents.simplifier_agent.get_gemini_service", return_value=mock_gemini):
        from backend.agents.simplifier_agent import SimplifierAgent
        return SimplifierAgent()


class TestSimplifierAgent:

    def test_simplify_returns_tuple(self, simplifier) -> None:
        result = simplifier.simplify("Some election text here.")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_simplify_returns_string_and_latency(self, simplifier) -> None:
        text, latency = simplifier.simplify("How to register to vote as a new voter.")
        assert isinstance(text, str)
        assert isinstance(latency, int)
        assert latency >= 0

    def test_empty_input_returns_default(self, simplifier) -> None:
        text, latency = simplifier.simplify("")
        assert "No content" in text
        assert latency == 0

    def test_whitespace_only_returns_default(self, simplifier) -> None:
        text, latency = simplifier.simplify("   ")
        assert "No content" in text
        assert latency == 0

    def test_gemini_called_with_non_empty_text(self, simplifier, mock_gemini) -> None:
        simplifier.simplify("Voter registration procedure and deadline information.")
        mock_gemini.generate.assert_called_once()

    def test_gemini_failure_falls_back_to_original(self, simplifier, mock_gemini) -> None:
        mock_gemini.generate.side_effect = Exception("API error")
        original = "Original election text."
        text, _ = simplifier.simplify(original)
        assert text == original

    def test_long_text_truncated_in_prompt(self, simplifier, mock_gemini) -> None:
        long_text = "word " * 1000
        simplifier.simplify(long_text)
        call_args = mock_gemini.generate.call_args
        prompt_arg = call_args[1].get("prompt") or call_args[0][0]
        # The prompt should be constructed but the original 5000 chars trimmed
        assert len(prompt_arg) < len(long_text) + 500

    def test_disclaimer_in_response(self, simplifier) -> None:
        text, _ = simplifier.simplify("This is some election text to simplify.")
        assert "election office" in text.lower() or "AI-generated" in text


class TestSimplifierAgentInit:

    def test_creates_with_mock_gemini(self, mock_gemini) -> None:
        with patch(
            "backend.agents.simplifier_agent.get_gemini_service",
            return_value=mock_gemini,
        ):
            from backend.agents.simplifier_agent import SimplifierAgent
            agent = SimplifierAgent()
            assert agent is not None
