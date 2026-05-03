"""
tests/test_firebase_service_errors.py
──────────────────────────────
Unit tests for the Firebase Service error paths.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from backend.services.firebase_service import FirebaseService


@pytest.fixture
def mock_firebase() -> FirebaseService:
    service = FirebaseService()
    import backend.services.firebase_service as mod
    mod._firestore_client = MagicMock()
    mod._firebase_app = MagicMock()
    return service


class TestFirebaseErrors:

    def test_save_conversation_error(self, mock_firebase: FirebaseService) -> None:
        import backend.services.firebase_service as mod
        mod._firestore_client.collection.side_effect = Exception("Test Error")
        result = mock_firebase.save_conversation("test_id", {"data": "test"})
        assert result is False

    def test_get_conversation_error(self, mock_firebase: FirebaseService) -> None:
        import backend.services.firebase_service as mod
        mod._firestore_client.collection.side_effect = Exception("Test Error")
        result = mock_firebase.get_conversation("test_id")
        assert result is None

    def test_log_feedback_error(self, mock_firebase: FirebaseService) -> None:
        import backend.services.firebase_service as mod
        mod._firestore_client.collection.side_effect = Exception("Test Error")
        result = mock_firebase.log_feedback("test_id", 0, "helpful", None)
        assert result is False

    @patch("firebase_admin.auth.verify_id_token")
    def test_verify_token_error(self, mock_verify, mock_firebase: FirebaseService) -> None:
        mock_verify.side_effect = Exception("Test Error")
        result = mock_firebase.verify_token("fake_token")
        assert result is None
