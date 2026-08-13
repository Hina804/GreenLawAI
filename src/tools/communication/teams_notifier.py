import logging
import os
import requests
from typing import Dict, Any
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class TeamsNotifier(BaseTool):
    """
    Sends alerts to Microsoft Teams channels using Webhooks.
    """
    def __init__(self):
        super().__init__(
            name="teams_notifier",
            description="Sends automated logs and team alerts to Microsoft Teams channels via Webhooks."
        )
        self.webhook_url = os.getenv("TEAMS_WEBHOOK_URL")

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        message = parameters.get("message", "GreenLawAI Log Entry")
        
        if not self.webhook_url:
            return {"status": "error", "message": "Microsoft Teams Webhook URL missing in environment."}

        try:
            # Teams Webhook (Message Card format)
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "0078D7",
                "summary": "GreenLawAI Alert",
                "sections": [{
                    "activityTitle": "🤖 GreenLawAI Autonomous Alert",
                    "activitySubtitle": "Environmental Intelligence System",
                    "text": message
                }]
            }
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            
            if response.status_code in [200, 201, 202]:
                return {"status": "success", "message": "Alert sent to Microsoft Teams."}
            else:
                return {"status": "error", "message": f"Teams Error: {response.status_code} - {response.text}"}
        except Exception as e:
            logger.error(f"[Teams] Error: {e}")
            return {"status": "error", "message": str(e)}
