"""
backend/services/fcm_service.py
──────────────────────────────────
Firebase Cloud Messaging (FCM) service wrapper.
Used for sending session alerts and voter deadline notifications.
"""

from __future__ import annotations

import firebase_admin
from firebase_admin import messaging
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class FCMService:
    """
    Handles sending push notifications to voters via Firebase.
    """
    def __init__(self) -> None:
        logger.info("FCMService initialised")

    def send_notification(self, token: str, title: str, body: str, data: dict | None = None) -> bool:
        """
        Send a notification to a specific device token.
        """
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data,
            token=token,
        )
        try:
            response = messaging.send(message)
            logger.info("FCM notification sent", response=response)
            return True
        except Exception as exc:
            logger.error("FCM send failed", error=str(exc))
            return False

_fcm_service: FCMService | None = None

def get_fcm_service() -> FCMService:
    """Singleton FCM service."""
    global _fcm_service
    if _fcm_service is None:
        _fcm_service = FCMService()
    return _fcm_service
