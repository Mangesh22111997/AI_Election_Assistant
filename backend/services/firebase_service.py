"""
backend/services/firebase_service.py
──────────────────────────────────────
Firebase Admin SDK wrapper for:
  - Firestore conversation persistence
  - Optional Firebase Auth token verification
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── Lazy Firebase Init ────────────────────────────────────────────────────────
_firebase_app = None
_firestore_client = None


def _init_firebase() -> None:
    """Initialise Firebase Admin SDK once."""
    global _firebase_app, _firestore_client
    if _firebase_app is not None:
        return

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        sdk_path = Path(settings.firebase_admin_sdk_path)
        if sdk_path.exists():
            cred = credentials.Certificate(str(sdk_path))
            _firebase_app = firebase_admin.initialize_app(
                cred,
                options={
                    "databaseURL": settings.firebase_database_url,
                    "storageBucket": settings.firebase_storage_bucket,
                },
            )
        else:
            # Use Application Default Credentials on GCP / Cloud Run
            _firebase_app = firebase_admin.initialize_app(
                options={
                    "databaseURL": settings.firebase_database_url,
                    "storageBucket": settings.firebase_storage_bucket,
                }
            )

        _firestore_client = firestore.client()
        logger.info("Firebase Admin SDK initialised", project=settings.firebase_project_id)

    except Exception as exc:
        logger.warning(
            "Firebase unavailable – running in offline mode",
            error=str(exc),
        )
        _firebase_app = None
        _firestore_client = None


class FirebaseService:
    """
    Service layer for Firestore operations.

    All methods degrade gracefully when Firebase is unavailable
    (e.g., missing service-account key during local development).
    """

    def __init__(self) -> None:
        _init_firebase()

    # ── Conversation CRUD ─────────────────────────────────────────────────────

    def save_conversation(self, conversation_id: str, data: dict[str, Any]) -> bool:
        """
        Upsert a conversation document in Firestore.

        Returns True on success, False if Firebase is unavailable.
        """
        if _firestore_client is None:
            logger.debug("Firebase offline – conversation not persisted", id=conversation_id)
            return False

        try:

            ref = _firestore_client.collection("conversations").document(conversation_id)
            ref.set(data, merge=True)
            logger.debug("Conversation saved", conversation_id=conversation_id)
            return True
        except Exception as exc:
            logger.error("Failed to save conversation", error=str(exc))
            return False

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """Retrieve a conversation document or None if not found."""
        if _firestore_client is None:
            return None

        try:
            ref = _firestore_client.collection("conversations").document(conversation_id)
            doc = ref.get()
            return doc.to_dict() if doc.exists else None
        except Exception as exc:
            logger.error("Failed to fetch conversation", error=str(exc))
            return None

    def log_feedback(
        self,
        conversation_id: str,
        message_index: int,
        feedback: str,
        comment: str | None,
    ) -> bool:
        """Append a feedback record to Firestore."""
        if _firestore_client is None:
            return False

        try:
            from firebase_admin import firestore

            _firestore_client.collection("feedback").add(
                {
                    "conversation_id": conversation_id,
                    "message_index": message_index,
                    "feedback": feedback,
                    "comment": comment,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                }
            )
            return True
        except Exception as exc:
            logger.error("Failed to log feedback", error=str(exc))
            return False

    # ── Auth ──────────────────────────────────────────────────────────────────

    def verify_token(self, id_token: str) -> dict[str, Any] | None:
        """
        Verify a Firebase ID token.

        Returns the decoded claims dict or None if invalid.
        """
        if _firebase_app is None:
            return None

        try:
            from firebase_admin import auth

            return auth.verify_id_token(id_token)
        except Exception as exc:
            logger.warning("Token verification failed", error=str(exc))
            return None


# ── Module-level singleton ────────────────────────────────────────────────────
_firebase_service: FirebaseService | None = None


def get_firebase_service() -> FirebaseService:
    global _firebase_service
    if _firebase_service is None:
        _firebase_service = FirebaseService()
    return _firebase_service
