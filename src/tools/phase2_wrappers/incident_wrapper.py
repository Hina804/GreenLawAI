import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

INCIDENTS_FILE = "e:/GL_AI/src/data/incidents.json"

class IncidentAgent(BaseTool):
    """Investigates incidents like illegal logging or encroachments."""
    def __init__(self):
        super().__init__(
            name="incident_agent",
            description="Investigates recent incidents, gathers evidence on illegal logging, poaching, or encroachments."
        )

    def _load_incidents(self):
        """Load real incidents from incidents.json"""
        try:
            if os.path.exists(INCIDENTS_FILE):
                with open(INCIDENTS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"[IncidentWrapper] Failed to load incidents.json: {e}")
        return []

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        query = parameters.get("query", "")
        q_lower = query.lower()
        
        logger.info(f"IncidentAgent: Investigating '{query}'...")
        
        all_incidents = self._load_incidents()
        
        # === Dynamic Date Filtering ===
        days_filter = 90  # default
        if "30 days" in q_lower or "month" in q_lower: days_filter = 30
        elif "7 days" in q_lower or "week" in q_lower: days_filter = 7
        elif "14 days" in q_lower or "2 weeks" in q_lower: days_filter = 14
        
        cutoff = datetime.now() - timedelta(days=days_filter)
        
        # Filter by date
        time_filtered = []
        for inc in all_incidents:
            try:
                inc_date = datetime.strptime(inc['date'], '%Y-%m-%d')
                if inc_date >= cutoff:
                    time_filtered.append(inc)
            except:
                continue
        
        # === Location Filtering ===
        location_keywords = {
            "swat": ["swat", "kalam", "madyan", "mingora"],
            "abbottabad": ["abbottabad", "galiyat", "shimla"],
            "mansehra": ["mansehra", "balakot", "kaghan", "naran"],
            "shangla": ["shangla"],
            "dir": ["dir"],
            "hazara": ["abbottabad", "mansehra", "haripur", "hazara", "galiyat"]
        }
        
        target_loc = None
        for loc, terms in location_keywords.items():
            if loc in q_lower:
                target_loc = terms
                break
        
        if target_loc:
            location_filtered = [
                inc for inc in time_filtered
                if any(t in inc.get("location", "").lower() for t in target_loc)
            ]
        else:
            location_filtered = time_filtered
        
        incidents = location_filtered if location_filtered else time_filtered[:5]
        
        return {
            "status": "success",
            "found": len(incidents) > 0,
            "count": len(incidents),
            "incidents": incidents,
            "investigation_target": query,
            "date_filter": f"Last {days_filter} days (cutoff: {cutoff.strftime('%Y-%m-%d')})",
            "summary": f"Found {len(incidents)} incidents in last {days_filter} days",
            "evidence": [f"{i['date']} - {i.get('violation', i.get('type', 'Unknown'))}: {i.get('location', '')}" for i in incidents],
            "conclusion": f"Investigation complete. {len(incidents)} incidents found within the specified timeframe."
        }
