from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
import os
import asyncio
from datetime import datetime

from data.deforestation_monitor import GFWDeforestationMonitor
from data.fire_monitor import FIRMSFireMonitor
from tools.communication.slack_notifier import SlackNotifier
from tools.forestry.evidence_engine import EvidenceEngine

class ForestWatchdog:
    """
    GreenLawAI Autonomous Watchdog Service.
    Runs 24/7 background scans for illegal logging and wildfires.
    """
    
    def __init__(self, api_keys: dict = None):
        self.scheduler = AsyncIOScheduler()
        self.api_keys = api_keys or {}
        self.gfw = GFWDeforestationMonitor()
        self.firms = FIRMSFireMonitor(self.api_keys.get("NASA_FIRMS_TOKEN", "DEMO_TOKEN"))
        self.slack = SlackNotifier()
        
        # In-memory alert cache to prevent duplicate alerts
        self._alert_history = set()

    def setup_jobs(self):
        """Configure autonomous background tasks."""
        # 1. Scan for illegal logging every 6 hours
        self.scheduler.add_job(
            self.scan_for_illegal_logging,
            'interval', hours=6,
            id='logging_scan',
            misfire_grace_time=3600
        )
        
        # 2. Scan for fires every 2 hours
        self.scheduler.add_job(
            self.scan_for_fires,
            'interval', hours=2,
            id='fire_scan',
            misfire_grace_time=1800
        )
        
        logger.info("[Watchdog] Autonomous jobs configured: Logging (6h), Fires (2h)")

    async def start(self):
        """Start the background scheduler."""
        if not self.scheduler.running:
            self.setup_jobs()
            self.scheduler.start()
            logger.info("[Watchdog] Autonomous surveillance active.")

    async def scan_for_illegal_logging(self):
        """Autonomous illegal logging detection with professional evidence generation."""
        logger.info("[Watchdog] Starting autonomous surveillance scan (GFW + EvidenceEngine)...")
        try:
            alerts = self.gfw.get_alerts(country="PAK", days=1)
            
            if alerts.get('high_confidence_alerts', 0) > 0:
                # 1. Generate Evidence Package
                main_hotspot = alerts['recent_hotspots'][0]
                package = EvidenceEngine.create_package(
                    location="Hazara Forest Range (Autonomous Detection)",
                    coordinates={"lat": main_hotspot["lat"], "lon": main_hotspot["lon"]},
                    detection_type="SATELLITE_GLAD_ALERT",
                    source="Global Forest Watch",
                    loss_estimate=alerts.get('estimated_loss_ha', 0)
                )
                
                # 2. Format for Officer Dispatch
                officer_brief = EvidenceEngine.format_for_officer(package)
                
                # 3. Dispatch to Slack
                # 3. Dispatch to Slack
                await self.slack.execute({"message": officer_brief})
                logger.info(f"[Watchdog] Autonomous evidence report {package['incident_id']} dispatched.")
                
                # Prevent flood by adding to history
                self._alert_history.add(package['incident_id'])
        except Exception as e:
            logger.error(f"[Watchdog] Logging scan failed: {e}")

    async def scan_for_fires(self):
        """Autonomous fire detection."""
        logger.info("[Watchdog] Starting fire detection scan...")
        try:
            fire_stats = self.firms.get_fire_stats(country="PAK")
            
            if fire_stats['high_confidence'] > 0:
                msg = (
                    f"🔥 *FIRE WATCH*: {fire_stats['high_confidence']} high-intensity hotspots found!\n"
                    f"• Avg Intensity: {round(fire_stats['avg_brightness'], 2)} K\n"
                    f"• Action: Monitoring agents alerted for Hazara protection."
                )
                await self.slack.execute({"message": msg})
                logger.info("[Watchdog] Fire alert dispatched to Slack.")
        except Exception as e:
            logger.error(f"[Watchdog] Fire scan failed: {e}")

# singleton instance for application wide use
watchdog = ForestWatchdog()
