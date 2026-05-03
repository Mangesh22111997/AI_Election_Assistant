"""
tests/unit/test_orchestrator.py
────────────────────────────────
Unit tests for the OrchestratorAgent pipeline.
Tests all pipeline stages using mocked agents.
"""

from __future__ import annotations

import pytest
import asyncio
from unittest.mock import MagicMock


# ── Fixtures ───────────────────────────────────────────────────────────────────

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
        "Visit nvsp.in to register. "
        "🤖 AI-generated educational content. "
        "Always verify with your local election office.",
        200,
    )
    return simplifier


@pytest.fixture
def mock_monitor():
    monitor = MagicMock()

    inbound_result = MagicMock()
    inbound_result.passed = True
    inbound_result.violation_type = None

    outbound_result = MagicMock()
    outbound_result.passed = True
    outbound_result.output = (
        "Visit nvsp.in to register. "
        "🤖 AI-generated educational content. "
        "Always verify with your local election office."
    )
    outbound_result.violation_type = None

    monitor.validate_input.return_value = inbound_result
    monitor.validate.return_value = outbound_result
    return monitor


@pytest.fixture
def orchestrator(mock_guide, mock_simplifier, mock_monitor):
    from backend.agents.orchestrator import OrchestratorAgent
    return OrchestratorAgent(mock_guide, mock_simplifier, mock_monitor)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestOrchestratorProcess:

    @pytest.mark.unit
    def test_process_returns_dict(self, orchestrator) -> None:
        """process() must return a dict with required keys."""
        result = asyncio.run(orchestrator.process("How do I register to vote?"))
        assert isinstance(result, dict)
        assert "response" in result
        assert "sources" in result
        assert "intent" in result
        assert "latency_ms" in result
        assert "safety_blocked" in result

    @pytest.mark.unit
    def test_process_safety_passed_on_clean_query(self, orchestrator) -> None:
        """Safe queries must pass both inbound and outbound safety checks."""
        result = asyncio.run(orchestrator.process("How do I register to vote?"))
        assert result["safety_blocked"] is False

    @pytest.mark.unit
    def test_process_returns_sources(self, orchestrator) -> None:
        """Approved queries must include source citations."""
        result = asyncio.run(orchestrator.process("How do I register to vote?"))
        assert len(result["sources"]) > 0

    @pytest.mark.unit
    def test_process_returns_intent(self, orchestrator) -> None:
        """Intent must be correctly propagated from GuideAgent."""
        result = asyncio.run(orchestrator.process("How do I register to vote?"))
        assert result["intent"] == "registration_inquiry"

    @pytest.mark.unit
    def test_process_latency_is_non_negative(self, orchestrator) -> None:
        """Latency must always be a non-negative integer."""
        result = asyncio.run(orchestrator.process("How do I register to vote?"))
        assert result["latency_ms"] >= 0

    @pytest.mark.unit
    def test_process_inbound_blocked(
        self, mock_guide, mock_simplifier, mock_monitor
    ) -> None:
        """Queries blocked inbound must not reach GuideAgent."""
        from backend.agents.orchestrator import OrchestratorAgent

        blocked_result = MagicMock()
        blocked_result.passed = False
        blocked_result.violation_type = "endorsement"
        mock_monitor.validate_input.return_value = blocked_result

        orch = OrchestratorAgent(mock_guide, mock_simplifier, mock_monitor)
        result = asyncio.run(orch.process("Vote for candidate X"))

        assert result["safety_blocked"] is True
        assert result["violation_type"] == "endorsement"
        assert "election" in result["response"].lower()
        mock_guide.process_query.assert_not_called()

    @pytest.mark.unit
    def test_process_outbound_blocked_clears_sources(
        self, mock_guide, mock_simplifier, mock_monitor
    ) -> None:
        """Responses blocked outbound must return empty sources."""
        from backend.agents.orchestrator import OrchestratorAgent

        outbound_blocked = MagicMock()
        outbound_blocked.passed = False
        outbound_blocked.output = "Fallback message"
        outbound_blocked.violation_type = "bias"
        mock_monitor.validate.return_value = outbound_blocked

        orch = OrchestratorAgent(mock_guide, mock_simplifier, mock_monitor)
        result = asyncio.run(orch.process("How do I vote?"))

        assert result["safety_blocked"] is True
        assert result["sources"] == []

    @pytest.mark.unit
    def test_process_language_propagated(self, orchestrator) -> None:
        """Target language must be included in the result."""
        result = asyncio.run(orchestrator.process("How do I vote?", language="hi"))
        assert result.get("language") == "hi"


class TestOrchestratorInit:

    @pytest.mark.unit
    def test_init_sets_agents(self, mock_guide, mock_simplifier, mock_monitor) -> None:
        """Constructor must correctly assign all three agents."""
        from backend.agents.orchestrator import OrchestratorAgent
        orch = OrchestratorAgent(mock_guide, mock_simplifier, mock_monitor)
        assert orch.guide_agent is mock_guide
        assert orch.simplifier_agent is mock_simplifier
        assert orch.safety_monitor is mock_monitor

    @pytest.mark.unit
    def test_init_state_is_initialized(
        self, mock_guide, mock_simplifier, mock_monitor
    ) -> None:
        """Initial state must be INITIALIZED."""
        from backend.agents.orchestrator import OrchestratorAgent, AgentState
        orch = OrchestratorAgent(mock_guide, mock_simplifier, mock_monitor)
        assert orch.state == AgentState.INITIALIZED
