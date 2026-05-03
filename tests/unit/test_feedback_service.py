from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from backend.services.feedback_service import FeedbackService


def test_store_feedback_rejects_invalid_rating() -> None:
    service = FeedbackService()
    service.firebase = MagicMock()

    result = asyncio.run(
        service.store_feedback(
            conversation_id="conv-1",
            message_index=0,
            rating="excellent",
        )
    )

    assert result == {"status": "failed", "reason": "invalid_rating"}
    service.firebase.log_feedback.assert_not_called()


def test_store_feedback_handles_missing_firebase_service() -> None:
    service = FeedbackService()
    service.firebase = None

    result = asyncio.run(
        service.store_feedback(
            conversation_id="conv-1",
            message_index=0,
            rating="helpful",
        )
    )

    assert result == {"status": "failed", "reason": "service_unavailable"}


def test_store_feedback_normalizes_rating_before_persisting() -> None:
    service = FeedbackService()
    service.firebase = MagicMock()
    service.firebase.log_feedback.return_value = True

    result = asyncio.run(
        service.store_feedback(
            conversation_id="conv-1",
            message_index=1,
            rating=" Helpful ",
            comment="nice",
        )
    )

    assert result["status"] == "stored"
    service.firebase.log_feedback.assert_called_once_with(
        conversation_id="conv-1",
        message_index=1,
        feedback="helpful",
        comment="nice",
    )


def test_store_feedback_rejects_non_string_rating() -> None:
    service = FeedbackService()
    service.firebase = MagicMock()

    result = asyncio.run(
        service.store_feedback(
            conversation_id="conv-1",
            message_index=0,
            rating=None,  # type: ignore[arg-type]
        )
    )

    assert result == {"status": "failed", "reason": "invalid_rating"}
    service.firebase.log_feedback.assert_not_called()
