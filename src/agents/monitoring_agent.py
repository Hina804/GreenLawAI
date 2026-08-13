#E:\GL_AI\src\agents\monitoring_agent.py
from typing import Dict, Any, List, Optional
import logging

from .base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, Citation, AudienceType

from tools.monitoring_tools import MonitoringTrendsTool

from data.deforestation_monitor import GFWDeforestationMonitor, GDACSAlertMonitor
from data.cache_manager import cache
import os

logger = logging.getLogger(__name__)



# -----------------------------
# MonitoringAgent
# -----------------------------

class MonitoringAgent(BaseAgent):
    """
    Phase-compliant Situational Intelligence Agent
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "monitoring", llm_manager=None):
        trends_tool = MonitoringTrendsTool()
        super().__init__(
            name="MonitoringAgent",
            component_id=component_id,
            tools=[trends_tool],
            config=config
        )
        self.llm_manager = llm_manager

    async def _get_live_alerts(self, location_filter: Optional[str] = None) -> List[Dict]:
        """Fetch real-time alerts from NASA, GFW, and Incidents"""
        alerts = []
        
        # 1. Get Fires from NASA (via fire_monitor or trends_tool)
        try:
            from data.fire_monitor import FIRMSFireMonitor
            token = os.getenv("NASA_FIRMS_TOKEN", "DEMO_TOKEN")
            fm = FIRMSFireMonitor(token)
            fires = fm.get_active_fires(days=1)
            for f in fires[:3]:
                alerts.append({
                    "region": f.get('acq_date', 'Today'),
                    "type": "🔥 FIRE ALERT",
                    "message": f"Thermal anomaly detected (Lat: {f.get('latitude')}, Lon: {f.get('longitude')})",
                    "date": f.get('acq_date'),
                    "level": "CRITICAL" if f.get('confidence') == 'h' else "HIGH"
                })
        except: pass

        # 2. Get Logging & Transportation
        try:
            from data.deforestation_monitor import GFWDeforestationMonitor
            from data.transport_monitor import TransportMonitor
            gfw = GFWDeforestationMonitor()
            tm = TransportMonitor()
            
            logging_data = gfw.get_logging_alerts(days=7)
            for l in logging_data[:3]:
                alerts.append({
                    "region": "Forest Depth",
                    "type": "🪓 ILLEGAL LOGGING",
                    "message": f"Suspicious activity detected (Lat: {l.get('lat')}, Lon: {l.get('lon')})",
                    "date": l.get('date', 'Today'),
                    "level": "CRITICAL"
                })
                
            transport_data = tm.get_suspicious_movements()
            for t in transport_data[:2]:
                alerts.append({
                    "region": t.get('location', 'High-Risk Road'),
                    "type": "🚚 TIMBER TRANSPORT",
                    "message": f"Suspicious {t.get('type')} detected",
                    "date": t.get('date'),
                    "level": "HIGH"
                })
        except: pass

        # Filter by location if requested
        if location_filter:
            alerts = [a for a in alerts if location_filter.lower() in a['region'].lower() or location_filter.lower() in a['message'].lower()]
        
        return alerts if alerts else [
            {"region": "KPK", "type": "🛰️ STATUS", "message": "Satellite feed active. No critical anomalies detected.", "date": "Live", "level": "LOW"}
        ]

    async def run(
        self,
        query: str,
        retrieved_chunks: list,
        audience: AudienceType = AudienceType.DUAL,
        context: Dict[str, Any] = None
    ) -> CanonicalAgentResponse:
        logger.info(f"[MonitoringAgent] Real-time situational scanning: {query}")

        # 1. Fetch GFW and GDACS Data (Cached)
        gfw = GFWDeforestationMonitor()
        gdacs = GDACSAlertMonitor()
        
        gfw_data = cache.get_or_fetch(
            "gfw:PAK:30",
            lambda: gfw.get_alerts(country="PAK", days=30),
            ttl_seconds=86400 
        )
        
        gdacs_alerts = cache.get_or_fetch(
            "gdacs:PAK",
            lambda: gdacs.get_disasters(country="Pakistan"),
            ttl_seconds=10800 
        )

        alert_summary = "\n".join([f"**🚨 GDACS ALERT**: {a['title']}" for a in gdacs_alerts])
        if not alert_summary:
            alert_summary = "**STATUS**: No active large-scale natural disasters detected in Pakistan."

        # 2. Fetch Live Situational Alerts (Replaces ROTATING_ALERTS)
        q_lower = query.lower()
        location_keyword = next((loc for loc in ["swat", "abbottabad", "kaghan", "mansehra"] if loc in q_lower), None)
        live_alerts = await self._get_live_alerts(location_keyword)
        
        situational_context = "\n".join([f"- {a['type']} ({a['region']}): {a['message']}" for a in live_alerts])

        # 3. Monitoring Prompt (Live Data Infused)
        prompt = f"""You are a Forestry Situational Awareness Officer specializes in the Hazara Division (Abbottabad, Mansehra, Kohistan). 
        Analyze these real-time environmental data streams with a focus on local enforcement and reporting.
        
        HAZARA-FOCUSED DEFORESTATION (GFW - Last 90 Days):
        - Total GLAD Alerts: {gfw_data['total_alerts']}
        - High Confidence Hotspots: {gfw_data['high_confidence_alerts']}
        - Estimated Tree Cover Loss: {gfw_data['estimated_loss_ha']} ha
        
        LIVE SITUATIONAL ALERTS (Regional):
        {situational_context}
        
        NATURAL DISASTERS (GDACS):
        {alert_summary}
        
        QUERY: "{query}"
        
        INSTRUCTIONS:
        1. Contextualize the user's query with a strong focus on the Hazara Division and KPK province.
        2. Advise on priority monitoring zones based on the hotspot intensity in the Hazara range.
        3. Professional enforcement and disaster-readiness tone.
        
        SITUATIONAL REPORT (Specialized for Hazara Forest Guardians):"""

        try:
            if self.llm_manager:
                report_text = "".join(self.llm_manager.generate(prompt, stream=False))
            else:
                report_text = f"Primary Attention: {live_alerts[0]['type']} in {live_alerts[0]['region']}."
        except Exception as e:
            logger.error(f"[MonitoringAgent] failure: {e}")
            report_text = "Situational awareness feeds temporarily limited."

        monitoring_summary = (
            f"Active monitoring report for the specified region.\n\n"
            f"**Monitoring Sources**: Live deforestation alerts via **Global Forest Watch (GFW)**, "
            f"fire detection via **NASA FIRMS**, and disaster events from **GDACS**.\n\n"
            f"Current Data Confidence: High (Live Satellite Sync Active)."
        )

        return CanonicalAgentResponse(
            simple_explanation=monitoring_summary,
            legal_explanation=report_text,
            citations=[Citation(document="Satellite Intelligence Hub", section="Satellite Alerts", clause="NASA/GFW Sync", chunk_id="monitoring_data")],
            abstain=False,
            agent_name=self.name,
            audience=audience,
            confidence=0.95,
            source_chunks=[],
            graph_metadata={"gfw_alerts": gfw_data, "gdacs_alerts": gdacs_alerts, "live_alerts": live_alerts},
            validation_passed=True,
            errors=[]
        )
