"""
Phase 3 - Pillar 3: Proactive Scheduler
Orchestrates the proactive agents to run at specified intervals or continuously
in the background.
"""

from loguru import logger
import threading
import time
from datetime import datetime

# Import Pillar 3 Agents
from agents.patrol_recommender import PatrolRecommenderAgent
from agents.violation_detector import ViolationDetectorAgent
from agents.seasonal_awareness import SeasonalAwarenessAgent

class ProactiveScheduler:
    """
    Manages the execution of proactive agents.
    In a full production environment, this would use Celery or APScheduler.
    For this implementation, it provides a unified interface to run them and
    holds their latest state for the UI.
    """
    def __init__(self):
        self.patrol_recommender = PatrolRecommenderAgent()
        self.violation_detector = ViolationDetectorAgent()
        self.seasonal_awareness = SeasonalAwarenessAgent()
        
        self.latest_reports = {
            "patrol": None,
            "violation": None,
            "awareness": None,
            "last_updated": None
        }

    def run_all_agents(self):
        """Runs all proactive agents and saves their reports."""
        logger.info("[Scheduler] Running proactive agent suite...")
        
        try:
            patrol_report = self.patrol_recommender.generate_daily_schedule()
        except Exception as e:
            logger.error(f"[Scheduler] Patrol Recommender failed: {e}")
            patrol_report = {"status": "error"}
            
        try:
            violation_report = self.violation_detector.detect_patterns()
        except Exception as e:
            logger.error(f"[Scheduler] Violation Detector failed: {e}")
            violation_report = {"status": "error"}
            
        try:
            awareness_report = self.seasonal_awareness.generate_bulletin()
        except Exception as e:
            logger.error(f"[Scheduler] Seasonal Awareness failed: {e}")
            awareness_report = {"status": "error"}
            
        self.latest_reports = {
            "patrol": patrol_report,
            "violation": violation_report,
            "awareness": awareness_report,
            "last_updated": datetime.now().isoformat()
        }
        
        logger.info("[Scheduler] Proactive agent suite execution complete.")
        return self.latest_reports

    def get_latest_reports(self):
        """Returns the most recently generated reports."""
        if not self.latest_reports["last_updated"]:
            self.run_all_agents()
        return self.latest_reports

# Singleton instance for the UI to interact with
proactive_scheduler = ProactiveScheduler()
