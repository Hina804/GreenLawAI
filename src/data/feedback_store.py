import json
import os
import uuid
from datetime import datetime
from loguru import logger

class FeedbackStore:
    """
    Persists user feedback ratings to JSON file for Phase 3 adaptive learning.
    """
    def __init__(self, data_dir="data"):
        self.data_dir = os.path.join(os.path.dirname(__file__), '..', '..', data_dir)
        self.feedback_file = os.path.join(self.data_dir, 'feedback.json')
        os.makedirs(self.data_dir, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.feedback_file):
            with open(self.feedback_file, 'w') as f:
                json.dump([], f)

    def record_feedback(self, query: str, response: dict, rating: int, comment: str = "") -> str:
        """
        Record a user rating (1-5) and comment for a specific query/response.
        """
        feedback_id = str(uuid.uuid4())[:8]
        entry = {
            "id": feedback_id,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "rating": rating,
            "comment": comment,
            # We don't store the full response to save space, just metadata
            "confidence": getattr(response, "confidence", 0.0) if hasattr(response, "confidence") else response.get("confidence", 0.0) if isinstance(response, dict) else 0.0
        }

        try:
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            
            data.append(entry)
            
            with open(self.feedback_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"[FeedbackStore] Recorded feedback {feedback_id}: Rating {rating}/5")
        except Exception as e:
            logger.error(f"[FeedbackStore] Failed to record feedback: {e}")
            
        return feedback_id

    def get_low_confidence_queries(self, rating_threshold=3) -> list:
        """Get queries that received low ratings."""
        try:
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            return [d for d in data if d.get("rating", 5) < rating_threshold]
        except Exception:
            return []

    def get_satisfaction_rate(self) -> float:
        """Calculate overall user satisfaction % (ratings >= 4)."""
        try:
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            if not data:
                return 0.0
            satisfied = sum(1 for d in data if d.get("rating", 0) >= 4)
            return (satisfied / len(data)) * 100.0
        except Exception:
            return 0.0

# Singleton instance
feedback_store = FeedbackStore()
