"""
feedback_service.py
──────────────────
Collects and stores user feedback for continuous improvement.
"""
from typing import Any, Dict, Final, Optional
from datetime import datetime
from backend.services.firebase_service import get_firebase_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_RATINGS: Final[set[str]] = {"helpful", "not_helpful", "inaccurate"}


class FeedbackService:
    """Collects and stores user feedback for continuous improvement."""

    def __init__(self) -> None:
        self.firebase = get_firebase_service()
    
    async def store_feedback(
        self, 
        conversation_id: str, 
        message_index: int,
        rating: str,  # "helpful" | "not_helpful" | "inaccurate"
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store user feedback in Firestore with enhanced metadata."""
        if not isinstance(rating, str):
            logger.warning("Rejected non-string feedback rating", rating_type=type(rating).__name__)
            return {"status": "failed", "reason": "invalid_rating"}

        normalized_rating = rating.strip().lower()
        if normalized_rating not in ALLOWED_RATINGS:
            logger.warning("Rejected invalid feedback rating", rating=rating)
            return {"status": "failed", "reason": "invalid_rating"}

        feedback_data = {
            "conversation_id": conversation_id,
            "message_index": message_index,
            "rating": normalized_rating,
            "comment": comment,
            "timestamp": datetime.utcnow().isoformat(),
            "processed": False,
            "source": "voter_assistant_v2"
        }
        
        if self.firebase is None:
            logger.error("Firebase service unavailable while storing feedback")
            return {"status": "failed", "reason": "service_unavailable"}

        success = self.firebase.log_feedback(
            conversation_id=conversation_id,
            message_index=message_index,
            feedback=normalized_rating,
            comment=comment
        )
        
        if success:
            logger.info("Feedback stored successfully", conversation_id=conversation_id)
            return {"status": "stored", "timestamp": feedback_data["timestamp"]}
        else:
            logger.error("Failed to store feedback in Firebase", conversation_id=conversation_id)
            return {"status": "failed", "reason": "database_error"}

def get_feedback_service() -> FeedbackService:
    return FeedbackService()
