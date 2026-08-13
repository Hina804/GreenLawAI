"""
Phase 3 - Pillar 3: Violation Detector
Proactively monitors incident databases to detect patterns,
repeat offenders, and systemic vulnerabilities.
"""

from loguru import logger
from datetime import datetime, timedelta
import json
import os
from collections import Counter

class ViolationDetectorAgent:
    def __init__(self):
        self.incidents_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'incidents.json')

    def detect_patterns(self, days_back=30):
        """Scans incident history to find anomalies or spikes."""
        logger.info(f"[ViolationDetector] Scanning incidents over past {days_back} days...")
        
        try:
            if not os.path.exists(self.incidents_path):
                return {"status": "error", "message": "Incidents database not found."}
                
            with open(self.incidents_path, 'r') as f:
                incidents = json.load(f)
                
            cutoff = datetime.now() - timedelta(days=days_back)
            
            recent = []
            for inc in incidents:
                try:
                    inc_date = datetime.strptime(inc.get('date', '2000-01-01'), '%Y-%m-%d')
                    if inc_date >= cutoff:
                        recent.append(inc)
                except Exception:
                    continue
                    
            if not recent:
                return {"status": "clear", "patterns_found": 0}
                
            # Detect location clusters
            locations = [inc.get('location', 'Unknown') for inc in recent]
            location_counts = Counter(locations)
            
            hotspots = [{"location": loc, "count": count} for loc, count in location_counts.items() if count >= 3]
            
            # Detect night operation spikes
            night_ops = sum(1 for inc in recent if inc.get('night_incident', False))
            night_ratio = night_ops / len(recent) if recent else 0
            
            alerts = []
            if hotspots:
                loc_names = ", ".join([h['location'] for h in hotspots])
                alerts.append(f"Organized syndicate activity suspected in: {loc_names}")
                
            if night_ratio > 0.4:
                alerts.append(f"High frequency of night incidents ({night_ratio*100:.0f}%). Review night checkpoint staffing.")
                
            return {
                "status": "alert" if alerts else "normal",
                "recent_incidents": len(recent),
                "hotspots": hotspots,
                "night_ratio": round(night_ratio, 2),
                "systemic_alerts": alerts
            }
            
        except Exception as e:
            logger.error(f"[ViolationDetector] Error scanning incidents: {e}")
            return {"status": "error"}
