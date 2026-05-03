"""
tests/test_orchestrator.py
────────────────────────────
Unit tests for the Orchestrator agent pipeline.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_guide():
    guide = MagicMock()
    guide.process_query.return_value = {
        "answer": (
            "To register, visit nvsp.in. [Source 1: ECI Guide]\n\n"
            "🤖 AI-generated educational content. "
            "Always verify with your local election office."
        ),
        "sources": ["ECI Guide"],
        "intent": "registration_inquiry",
        "latency_ms": 500,
    }
    return guide


@pytest.fixture
def mock_simplifier():
    simplifier = MagicMock()
    simplifier.simplify.return_value = (
        "Visit nvsp.in to register. 🤖 AI-generated educational content. "
        "Always verify with your local election office.",
        200,
    )
    return simplifier


@pytest.fixture
def mock_monitor():
    monitor = MagicMock()

    # Inbound: passes
    inbound_result = MagicMock()
    inbound_result.passed = True

    # Outbound: passes
    outbound_result = MagicMock()
    outbound_result.passed = True
    outbound_result.output = (
        "Visit nvsp.in to register. 🤖 AI-generated educational content. "
        "Always verify with your local election office."
    )
    outbound_result.violation_type = None

    monitor.validate_input.return_value = inbound_result
    monitor.validate.return_value = outbound_result
    return monitor


@pytest.fixture
def orchestrator(mock_guide, mock_simplifier, mock_monitor):
    from backend.agents.orchestrator import Orchestrator
    return Orchestrator(mock_guide, mock_simplifier, mock_monitor)


class TestOrchestratorRun:

    def test_run_returns_result_object(self, orchestrator) -> None:
        from backend.agents.orchestrator import OrchestratorResult
        result = orchestrator.run("How do I register to vote?")
        assert isinstance(result, OrchestratorResult)

    def test_run_safety_passed_on_clean_query(self, orchestrator) -> None:
        result = orchestrator.run("How do I register to vote?")
        assert result.safety_passed is True

    def test_run_returns_sources(self, orchestrator) -> None:
        result = orchestrator.run("How do I register to vote?")
        assert len(result.sources) > 0

    def test_run_returns_intent(self, orchestrator) -> None:
        result = orchestrator.run("How do I register to vote?")
        assert result.intent == "registration_inquiry"

    def test_run_latency_fields_positive(self, orchestrator) -> None:
        result = orchestrator.run("How do I register to vote?")
        assert result.total_latency_ms >= 0
        assert result.guide_latency_ms >= 0
        assert result.simplify_latency_ms >= 0

    def test_run_inbound_blocked(
        self, mock_guide, mock_simplifier, mock_monitor
    ) -> None:
        from backend.agents.orchestrator import Orchestrator

        blocked_result = MagicMock()
        blocked_result.passed = False
        blocked_result.violation_type = "endorsement"
        mock_monitor.validate_input.return_value = blocked_result

        orchestrator = Orchestrator(mock_guide, mock_simplifier, mock_monitor)
        result = orchestrator.run("Vote for candidate X")

        assert result.safety_passed is False
        assert result.violation_type == "endorsement"
        assert "1950" in result.answer or "election" in result.answer.lower()
        mock_guide.process_query.assert_not_called()

    def test_run_outbound_blocked_clears_sources(
        self, mock_guide, mock_simplifier, mock_monitor
    ) -> None:
        from backend.agents.orchestrator import Orchestrator

        outbound_blocked = MagicMock()
        outbound_blocked.passed = False
        outbound_blocked.output = "Fallback"
        outbound_blocked.violation_type = "bias"
        mock_monitor.validate.return_value = outbound_blocked

        orchestrator = Orchestrator(mock_guide, mock_simplifier, mock_monitor)
        result = orchestrator.run("How do I vote?")

        assert result.safety_passed is False
        assert result.sources == []


class TestOrchestratorInit:

    def test_init_sets_agents(self, mock_guide, mock_simplifier, mock_monitor) -> None:
        from backend.agents.orchestrator import Orchestrator
        orch = Orchestrator(mock_guide, mock_simplifier, mock_monitor)
        assert orch._guide is mock_guide
        assert orch._simplifier is mock_simplifier
        assert orch._monitor is mock_monitor
