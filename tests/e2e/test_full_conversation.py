"""
tests/e2e/test_full_conversation.py
────────────────────────────────────
End-to-end test of the full agent pipeline.
Uses FastAPI TestClient to verify the journey from user query to simplified response.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.main import app

client = TestClient(app)

@pytest.fixture
def mock_all(mock_gemini_service, mock_firebase_service):
    """Fixture to mock all external services for E2E testing."""
    return {
        "gemini": mock_gemini_service,
        "firebase": mock_firebase_service,
    }

def test_full_voter_journey(mock_all) -> None:
    """Verify a complete education request lifecycle."""
    # 1. Setup mock responses
    # Guide Agent response
    mock_all["gemini"].generate.side_effect = [
        "To register to vote in India, you must be 18+ and fill Form 6.", # Guide Agent
        "- Must be 18 years old\n- Fill Form 6\n📌 AI-generated educational content." # Simplifier Agent
    ]
    
    # 2. Send request
    response = client.post(
        "/api/chat",
        json={"query": "How do I register to vote?", "language": "en"}
    )
    
    # 3. Assertions
    assert response.status_code == 200
    data = response.json()
    
    assert data["conversation_id"] is not None
    assert "Form 6" in data["message"]["simplified"]
    assert data["message"]["intent"] == "registration_inquiry"
    assert data["message"]["safety_passed"] is True
    
    # Verify persistence
    assert mock_all["firebase"].save_conversation.called

def test_safety_blocked_journey(mock_all) -> None:
    """Verify that unsafe queries are blocked without hitting the full pipeline."""
    # 1. Send request with candidate mention
    response = client.post(
        "/api/chat",
        json={"query": "Who should I vote for? Candidate X is better.", "language": "en"}
    )
    
    # 2. Assertions
    assert response.status_code == 200
    data = response.json()
    
    assert data["message"]["safety_passed"] is False
    assert "cannot provide opinions" in data["message"]["simplified"]
    
    # Pipeline should have stopped before Gemini or Search
    assert mock_all["gemini"].generate.call_count == 0
