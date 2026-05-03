"""
feedback_service.py
──────────────────
Collects and stores user feedback for continuous improvement.
"""
from typing import Dict, Optional, Any
from datetime import datetime
from backend.services.firebase_service import get_firebase_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class FeedbackService:
    """Collects and stores user feedback for continuous improvement"""
    
    def __init__(self):
        self.firebase = get_firebase_service()
    
    async def store_feedback(
        self, 
        conversation_id: str, 
        message_index: int,
        rating: str,  # "helpful" | "not_helpful" | "inaccurate"
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store user feedback in Firestore with enhanced metadata"""
        feedback_data = {
            "conversation_id": conversation_id,
            "message_index": message_index,
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.utcnow().isoformat(),
            "processed": False,
            "source": "voter_assistant_v2"
        }
        
        success = self.firebase.log_feedback(
            conversation_id=conversation_id,
            message_index=message_index,
            feedback=rating,
            comment=comment
        )
        
        if success:
            logger.info("Feedback stored successfully", conversation_id=conversation_id)
            return {"status": "stored", "timestamp": feedback_data["timestamp"]}
        else:
            logger.error("Failed to store feedback in Firebase", conversation_id=conversation_id)
            return {"status": "failed", "reason": "database_error"}

def get_feedback_service():
    return FeedbackService()
