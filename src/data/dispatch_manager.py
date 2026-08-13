import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
from pathlib import Path

class DispatchManager:
    """
    Autonomous Dispatch Strategy Engine (Phase 11).
    Determines when and where to send tactical alerts to Hazara authorities.
    """
    def __init__(self):
        # District-to-DFO Contact Matrix (Hazara Division)
        self.DFO_CONTACTS = {
            "abbottabad": "dfo.abbottabad@greenlaw.gov.pk",
            "mansehra": "dfo.mansehra@greenlaw.gov.pk",
            "haripur": "dfo.haripur@greenlaw.gov.pk",
            "battagram": "dfo.battagram@greenlaw.gov.pk",
            "upper kohistan": "dfo.ukohistan@greenlaw.gov.pk",
            "lower kohistan": "dfo.lkohistan@greenlaw.gov.pk",
            "torghar": "dfo.torghar@greenlaw.gov.pk",
            "hazara_general": "divisional.forest.officer.hazara@greenlaw.gov.pk"
        }
        
        # Alert Cooldown (Prevent fatiguing authorities)
        self.dispatch_history = {} # cluster_id -> last_dispatch_time
        self.COOLDOWN_HOURS = 1 

    def get_sector_reliability(self) -> Dict[str, float]:
        """
        Calculates the reliability of AI alerts per sector (Abbottabad, Mansehra, etc.)
        based on historical Ranger feedback from the audit trail.
        """
        try:
            from data.intelligence_audit import audit_trail
            with open(audit_trail.log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            sector_stats = {} # district -> [correct, total]
            
            for entry in data.get("decisions", []):
                if "field_reality" in entry:
                    # Determine district from cluster details or lat/lon
                    meta = entry.get("meta", {})
                    lat = meta.get("lat")
                    lon = meta.get("lon")
                    
                    if lat and lon:
                        from data.geo_intelligence import IntelligenceFusionEngine
                        ife = IntelligenceFusionEngine()
                        district = ife._get_tactical_sector_fast(lat, lon)
                        # Normalize to district name (e.g. "Abbottabad City (0.5km)" -> "abbottabad")
                        if district: district = district.split(" ")[0].lower()
                        else: district = "hazara_general"
                        
                        if district not in sector_stats:
                            sector_stats[district] = [0, 0]
                        
                        sector_stats[district][1] += 1
                        if entry["field_reality"]["rating"] == "CORRECT":
                            sector_stats[district][0] += 1
                            
            # Calculate percentages
            reliability = {}
            for district, (correct, total) in sector_stats.items():
                reliability[district] = correct / total
                
            return reliability
        except Exception as e:
            logger.error(f"Failed to calculate sector reliability: {e}")
            return {}

    def get_dispatch_targets(self, event: Any) -> List[str]:
        """Determine official recipients based on event coordinates."""
        # Simple coordinate-to-district routing (approximate for Hazara region)
        lat, lon = event.lat, event.lon
        
        # Haripur (South Hazara (~34.0, 72.9))
        if lat < 34.1 and lon < 73.0: return [self.DFO_CONTACTS["haripur"]]
        # Abbottabad (~34.1, 73.2)
        if 34.1 <= lat < 34.3 and 73.1 <= lon < 73.4: return [self.DFO_CONTACTS["abbottabad"]]
        # Mansehra (~34.3, 73.2)
        if 34.3 <= lat < 34.6: return [self.DFO_CONTACTS["mansehra"]]
        # Kohistan (North Hazara (> 35.0))
        if lat >= 35.0: return [self.DFO_CONTACTS["hazara_general"]]
        
        return [self.DFO_CONTACTS["hazara_general"]]

    def should_dispatch(self, event: Any, autonomous_enabled: bool = False, threshold: float = 0.9) -> bool:
        """Rule-based trigger decision for autonomous alerting."""
        if not autonomous_enabled:
            return False
            
        # 1. Check Cooldown
        last_dispatch = self.dispatch_history.get(event.id)
        if last_dispatch and (datetime.now() - last_dispatch) < timedelta(hours=self.COOLDOWN_HOURS):
            return False
            
        # 2. Trigger Rules (High Integrity Alerts Only)
        is_verified = "VERIFIED" in getattr(event, 'confidence', '')
        # Milestone 11.5: OPERATOR-CONTROLLED THRESHOLD
        is_high_threat = event.severity == "CRITICAL" and float(event.details.get("confidence_score", 0)) >= threshold
        
        if is_verified or is_high_threat:
            self.dispatch_history[event.id] = datetime.now()
            return True
            
        return False

    async def execute_dispatch(self, event: Any, reason: str = "Autonomous Trigger"):
        """Multi-channel tactical alert execution (Slack + Email)."""
        recipients = self.get_dispatch_targets(event)
        full_msg = (f"🚨 GREENLAW AI: TACTICAL FIELD ALERT\n"
                   f"Event ID: {event.id}\n"
                   f"Type: {event.type.upper()}\n"
                   f"Coordinates: {event.lat}, {event.lon}\n"
                   f"Severity: {event.severity}\n"
                   f"Analysis: {event.details.get('strategic_narrative', 'N/A')}\n\n"
                   f"Reason for Dispatch: {reason}")
                   
        # 1. Slack (Real-time Team Awareness)
        from tools.communication.slack_notifier import SlackNotifier
        sn = SlackNotifier()
        await sn.execute({"message": full_msg})
        
        # 2. Email (Official Record to DFO)
        from tools.communication.email_sender import EmailSender
        es = EmailSender()
        for email in recipients:
            await es.execute({
                "subject": f"URGENT: {event.type.upper()} INCIDENT AT {event.lat}, {event.lon}",
                "message": full_msg,
                "recipient": email # Note: Assuming EmailSender supports recipient parameter
            })
            
        # 3. WhatsApp (Immediate Pocket Tactical Alert)
        try:
            from tools.communication.whatsapp_messenger import WhatsAppMessenger
            wm = WhatsAppMessenger()
            await wm.execute({"message": f"*URGENT TACTICAL ALERT*\n\n{full_msg}"})
            logger.info("WhatsApp Dispatch Executed.")
        except Exception as e:
            logger.error(f"WhatsApp dispatch initialization failed: {e}")
            
        logger.info(f"Autonomous Dispatch Executed for {event.id} to {recipients}")
        return True

dispatch_manager = DispatchManager()
