"""
tests/test_firebase_service.py
──────────────────────────────
Unit tests for the Firebase Service.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from backend.services.firebase_service import FirebaseService


@pytest.fixture
def offline_firebase() -> FirebaseService:
    # Ensure it starts with offline config
    service = FirebaseService()
    import backend.services.firebase_service as mod
    mod._firestore_client = None
    mod._firebase_app = None
    return service


class TestFirebaseOffline:

    def test_save_conversation_offline_returns_false(self, offline_firebase: FirebaseService) -> None:
        result = offline_firebase.save_conversation("test_id", {"data": "test"})
        assert result is False

    def test_get_conversation_offline_returns_none(self, offline_firebase: FirebaseService) -> None:
        result = offline_firebase.get_conversation("test_id")
        assert result is None

    def test_log_feedback_offline_returns_false(self, offline_firebase: FirebaseService) -> None:
        result = offline_firebase.log_feedback("test_id", 0, "helpful", None)
        assert result is False

    def test_verify_token_offline_returns_none(self, offline_firebase: FirebaseService) -> None:
        result = offline_firebase.verify_token("fake_token")
        assert result is None
