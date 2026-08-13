"""
Phase 3 - Pillar 2: Active Learner
Identifies patterns in failed/low-rated queries from the feedback store
to generate knowledge gap reports.
"""

from loguru import logger
from data.feedback_store import feedback_store
from collections import Counter
import re

class ActiveLearner:
    def __init__(self):
        self.feedback = feedback_store

    def generate_knowledge_gap_report(self) -> dict:
        """
        Analyze low-rated queries to identify missing knowledge domains.
        """
        low_rated = self.feedback.get_low_confidence_queries()
        
        if not low_rated:
            return {
                "gaps_identified": 0,
                "common_themes": [],
                "recommendation": "System performing well. No immediate ingestion needed."
            }

        # Extract keywords/themes from failed queries
        words = []
        for entry in low_rated:
            q = entry.get("query", "").lower()
            # Clean up punctuation
            q = re.sub(r'[^\w\s]', '', q)
            words.extend([w for w in q.split() if len(w) > 4])
            
        # Simplistic topic modeling via word frequency
        themes = Counter(words).most_common(5)
        
        report = {
            "gaps_identified": len(low_rated),
            "common_themes": [theme[0] for theme in themes],
            "recommendation": f"Consider ingesting documents related to: {', '.join([theme[0] for theme in themes])}",
            "satisfaction_rate": f"{self.feedback.get_satisfaction_rate():.1f}%"
        }
        
        logger.info(f"[ActiveLearner] Knowledge Gap Report generated: {report['gaps_identified']} issues found.")
        return report
