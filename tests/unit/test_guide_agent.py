"""
tests/test_guide_agent.py
──────────────────────────
Unit tests for the Guide Agent.
Mocks Gemini and GroundingTool to avoid API calls.
Target coverage: 95%+
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.agents.guide_agent import GuideAgent, INTENT_KEYWORDS


# ── Intent Classification ─────────────────────────────────────────────────────

class TestIntentClassification:
    """Tests for classify_intent() – no external calls needed."""

    @pytest.fixture
    def agent(self) -> GuideAgent:
        with patch("backend.agents.guide_agent.get_gemini_service"), \
             patch("backend.agents.guide_agent.get_grounding_tool"):
            return GuideAgent()

    @pytest.mark.parametrize("query,expected_intent", [
        ("When is the voter registration deadline?", "deadline_inquiry"),
        ("How do I register to vote?", "registration_inquiry"),
        ("Where is my polling place?", "polling_location"),
        ("What ID do I need to vote?", "id_requirements"),
        ("Can I vote by mail?", "mail_in_voting"),
        ("How do I cast my ballot?", "voting_procedure"),
        ("When are election results announced?", "result_timeline"),
        ("What is a general election?", "general_election"),
        ("How is the weather today?", "other"),
    ])
    def test_classify_intent(self, agent: GuideAgent, query: str, expected_intent: str) -> None:
        result = agent.classify_intent(query)
        assert result == expected_intent, f"Query '{query}' → expected {expected_intent}, got {result}"


# ── process_query ─────────────────────────────────────────────────────────────

class TestProcessQuery:

    @pytest.fixture
    def agent_with_mocks(self) -> GuideAgent:
        with patch("backend.agents.guide_agent.get_gemini_service") as mock_gemini_factory, \
             patch("backend.agents.guide_agent.get_grounding_tool") as mock_grounding_factory:

            mock_gemini = MagicMock()
            mock_gemini.generate.return_value = (
                "To register to vote, follow these steps: [Source 1: faq_dataset.json]\n"
                "🤖 AI-generated educational content. Always verify with your local election office."
            )
            mock_gemini_factory.return_value = mock_gemini

            mock_grounding = MagicMock()
            mock_grounding.retrieve.return_value = [
                {"content": "Register online at vote.gov", "source": "faq_dataset.json", "score": "0.9"}
            ]
            mock_grounding.live_search.return_value = []
            mock_grounding.format_context.return_value = "[Source 1: faq_dataset.json]\nRegister online at vote.gov"
            mock_grounding_factory.return_value = mock_grounding

            agent = GuideAgent()
            agent._gemini = mock_gemini
            agent._grounding = mock_grounding
            return agent

    def test_process_query_returns_all_keys(self, agent_with_mocks: GuideAgent) -> None:
        result = agent_with_mocks.process_query("How do I register to vote?")
        assert "answer" in result
        assert "sources" in result
        assert "intent" in result
        assert "latency_ms" in result

    def test_process_query_intent_correct(self, agent_with_mocks: GuideAgent) -> None:
        result = agent_with_mocks.process_query("How do I register to vote?")
        assert result["intent"] == "registration_inquiry"

    def test_process_query_sources_populated(self, agent_with_mocks: GuideAgent) -> None:
        result = agent_with_mocks.process_query("How do I register to vote?")
        assert len(result["sources"]) > 0

    def test_process_query_latency_positive(self, agent_with_mocks: GuideAgent) -> None:
        result = agent_with_mocks.process_query("How do I register to vote?")
        assert result["latency_ms"] >= 0

    def test_process_query_handles_gemini_failure(self) -> None:
        with patch("backend.agents.guide_agent.get_gemini_service") as mock_gemini_factory, \
             patch("backend.agents.guide_agent.get_grounding_tool") as mock_grounding_factory:

            mock_gemini = MagicMock()
            mock_gemini.generate.side_effect = RuntimeError("API error")
            mock_gemini_factory.return_value = mock_gemini

            mock_grounding = MagicMock()
            mock_grounding.retrieve.return_value = []
            mock_grounding.live_search.return_value = []
            mock_grounding.format_context.return_value = ""
            mock_grounding_factory.return_value = mock_grounding

            agent = GuideAgent()
            agent._gemini = mock_gemini
            agent._grounding = mock_grounding

            result = agent.process_query("How do I vote?")
            assert "election office" in result["answer"].lower()

    def test_deadline_query_calls_live_search(self, agent_with_mocks: GuideAgent) -> None:
        agent_with_mocks.process_query("When is the registration deadline?")
        agent_with_mocks._grounding.live_search.assert_called_once()

    def test_non_deadline_query_skips_live_search(self, agent_with_mocks: GuideAgent) -> None:
        agent_with_mocks._grounding.live_search.reset_mock()
        agent_with_mocks.process_query("How do I register to vote?")
        agent_with_mocks._grounding.live_search.assert_not_called()
