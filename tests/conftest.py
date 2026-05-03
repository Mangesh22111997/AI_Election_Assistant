"""
tests/conftest.py
──────────────────
Shared pytest fixtures for the Election Guide Assistant test suite.

Provides:
  - Mock Gemini service (avoids real API calls in tests)
  - Mock Firebase service (avoids Firestore writes)
  - Pre-configured agent instances
  - FastAPI TestClient with all agents mocked
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient


# ── Mock Services ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def mock_gemini_service():
    """
    Mock Gemini service that returns deterministic responses.
    Avoids real API calls — safe for CI with no API key.
    """
    service = MagicMock()
    service.generate.return_value = (
        "To register to vote, visit nvsp.in and complete Form 6. "
        "[Source 1: ECI Voter Guide]\n\n"
        "🤖 AI-generated educational content. "
        "Always verify with your local election office."
    )
    service.usage = {"total_requests": 0, "total_tokens": 0}
    return service


@pytest.fixture(scope="session")
def mock_firebase_service():
    """
    Mock Firebase service that silently drops all writes.
    Returns False (offline mode) for all persistence calls.
    """
    service = MagicMock()
    service.save_conversation.return_value = False
    service.get_conversation.return_value = None
    service.log_feedback.return_value = False
    service.verify_token.return_value = None
    return service


@pytest.fixture(scope="session")
def mock_grounding_tool():
    """
    Mock grounding tool that returns fixed election FAQ results.
    """
    tool = MagicMock()
    tool.retrieve.return_value = [
        {
            "content": "Voter registration can be done online at nvsp.in or at the BLO office.",
            "source": "ECI Voter Guide",
            "score": "0.95",
        }
    ]
    tool.live_search.return_value = []
    tool.format_context.return_value = (
        "[Source 1: ECI Voter Guide]\n"
        "Voter registration can be done online at nvsp.in or at the BLO office."
    )
    return tool


# ── Agent Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def safety_monitor():
    """Safety Monitor without Gemini — Layer 5 skipped (fast, deterministic)."""
    from backend.agents.safety_monitor import SafetyMonitor
    return SafetyMonitor()


@pytest.fixture(scope="session")
def guide_agent(mock_gemini_service, mock_grounding_tool):
    """Guide Agent with mocked Gemini and grounding tool."""
    from backend.agents.guide_agent import GuideAgent
    with (
        pytest.MonkeyPatch().context() as mp
    ):
        mp.setattr(
            "backend.agents.guide_agent.get_gemini_service",
            lambda: mock_gemini_service,
        )
        mp.setattr(
            "backend.agents.guide_agent.get_grounding_tool",
            lambda: mock_grounding_tool,
        )
        return GuideAgent()


@pytest.fixture(scope="session")
def simplifier_agent(mock_gemini_service):
    """Simplifier Agent with mocked Gemini."""
    from backend.agents.simplifier_agent import SimplifierAgent
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "backend.agents.simplifier_agent.get_gemini_service",
            lambda: mock_gemini_service,
        )
        return SimplifierAgent()


# ── FastAPI Client ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client(mock_gemini_service, mock_firebase_service, mock_grounding_tool):
    """
    FastAPI TestClient with all external dependencies mocked.
    Suitable for integration tests — no real API calls.
    """
    from unittest.mock import patch
    from backend.main import app

    with (
        patch("backend.main.get_firebase_service", return_value=mock_firebase_service),
        patch("backend.agents.guide_agent.get_gemini_service", return_value=mock_gemini_service),
        patch(
            "backend.agents.guide_agent.get_grounding_tool",
            return_value=mock_grounding_tool,
        ),
    ):
        with TestClient(app) as c:
            yield c
