"""
tests/test_api.py
──────────────────
Integration tests for the FastAPI endpoints.
Uses TestClient with all external services mocked.
Target coverage: 90%+
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create a TestClient with all external services mocked."""
    with patch("backend.agents.guide_agent.get_gemini_service"), \
         patch("backend.agents.guide_agent.get_grounding_tool"), \
         patch("backend.agents.simplifier_agent.get_gemini_service"), \
         patch("backend.services.firebase_service._init_firebase"), \
         patch("backend.main._get_agents") as mock_agents:

        mock_guide = MagicMock()
        mock_guide.process_query.return_value = {
            "answer": "According to the official guide [Source 1: faq_dataset.json], register at vote.gov.\n🤖 AI-generated educational content. Always verify with your local election office.",
            "sources": ["faq_dataset.json"],
            "intent": "registration_inquiry",
            "latency_ms": 100,
        }

        mock_simplifier = MagicMock()
        mock_simplifier.simplify.return_value = (
            "Here's how to register:\n📌 Visit vote.gov\n📌 Fill out the form\n\n"
            "🤖 AI-generated educational content. Always verify with your local election office.",
            80,
        )

        mock_safety = MagicMock()
        mock_safety.validate_input.return_value = MagicMock(passed=True, violation_type=None)
        mock_safety.validate.return_value = MagicMock(
            passed=True,
            violation_type=None,
            output=(
                "Here's how to register:\n📌 Visit vote.gov\n📌 Fill out the form\n\n"
                "🤖 AI-generated educational content. Always verify with your local election office."
            ),
        )

        mock_agents.return_value = (mock_guide, mock_simplifier, mock_safety)

        from backend.main import app
        return TestClient(app, raise_server_exceptions=True)


# ── Health Check ──────────────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_schema(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "environment" in data
        assert "gemini_model" in data

    def test_health_version_correct(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert data["version"] == "2.0.0"


# ── Chat Endpoint ─────────────────────────────────────────────────────────────

class TestChatEndpoint:

    def test_chat_valid_query_returns_200(self, client: TestClient) -> None:
        response = client.post(
            "/api/chat",
            json={"query": "How do I register to vote?"},
        )
        assert response.status_code == 200

    def test_chat_response_schema(self, client: TestClient) -> None:
        data = client.post(
            "/api/chat",
            json={"query": "How do I register to vote?"},
        ).json()
        assert "conversation_id" in data
        assert "message" in data
        assert "answer" in data["message"]
        assert "simplified" in data["message"]
        assert "sources" in data["message"]
        assert "disclaimer" in data["message"]

    def test_chat_disclaimer_present(self, client: TestClient) -> None:
        data = client.post(
            "/api/chat",
            json={"query": "When is the registration deadline?"},
        ).json()
        disclaimer = data["message"]["disclaimer"]
        assert "AI-generated educational content" in disclaimer

    def test_chat_empty_query_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/chat", json={"query": ""})
        assert response.status_code in (400, 422)

    def test_chat_too_short_query_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/chat", json={"query": "hi"})
        assert response.status_code in (400, 422)

    def test_chat_too_long_query_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/chat", json={"query": "a" * 1_001})
        assert response.status_code in (400, 422)

    def test_chat_conversation_id_returned(self, client: TestClient) -> None:
        data = client.post(
            "/api/chat",
            json={"query": "How do I vote by mail?"},
        ).json()
        assert len(data["conversation_id"]) > 0

    def test_chat_existing_conversation_id_preserved(self, client: TestClient) -> None:
        conv_id = "test-conversation-123"
        data = client.post(
            "/api/chat",
            json={"query": "How do I vote?", "conversation_id": conv_id},
        ).json()
        assert data["conversation_id"] == conv_id


# ── Feedback Endpoint ─────────────────────────────────────────────────────────

class TestFeedbackEndpoint:

    def test_feedback_returns_200(self, client: TestClient) -> None:
        response = client.post(
            "/api/feedback",
            json={
                "conversation_id": "test-conv-id",
                "message_index": 0,
                "feedback": "helpful",
            },
        )
        assert response.status_code == 200

    def test_feedback_response_has_status(self, client: TestClient) -> None:
        data = client.post(
            "/api/feedback",
            json={
                "conversation_id": "test-conv-id",
                "message_index": 0,
                "feedback": "not_helpful",
                "comment": "The answer was unclear.",
            },
        ).json()
        assert "status" in data


# ── Security Headers ──────────────────────────────────────────────────────────

class TestSecurityHeaders:

    def test_xss_protection_header(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_content_type_nosniff(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_frame_options_deny(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_process_time_header_present(self, client: TestClient) -> None:
        response = client.get("/health")
        assert "X-Process-Time-Ms" in response.headers
