"""
Phase 3 - Pillar 4: Webhook Manager
Sends HTTP pushes to registered external endpoints when critical events happen
(e.g., Extreme Fire Risk, Critical Deforestation Hotspot).
"""

import httpx
import asyncio
from loguru import logger
from datetime import datetime

class WebhookManager:
    """Manages integration with external alert systems (Slack, SMS gateways, etc)."""
    
    def __init__(self):
        # In production this would be loaded from a DB or Config
        self.subscribers = [
            {"name": "Department Slack", "url": "https://hooks.slack.com/services/mock/123", "events": ["critical_alert"]},
            {"name": "Mobile App Push", "url": "https://fcm.googleapis.com/mock/push", "events": ["critical_alert", "daily_patrol"]}
        ]

    async def broadcast_alert(self, event_type: str, title: str, message: str, meta: dict = None):
        """
        Send payload to all subscribers listening for this event_type.
        (Mocked for local execution but structured for production)
        """
        payload = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "title": title,
            "message": message,
            "meta": meta or {}
        }
        
        count = 0
        for sub in self.subscribers:
            if event_type in sub["events"]:
                try:
                    # Async HTTP POST to the subscriber URL
                    # In this mock, we just log it instead of making actual requests to dummy URLs
                    if "mock" not in sub["url"]:
                        async with httpx.AsyncClient() as client:
                            await client.post(sub["url"], json=payload, timeout=5.0)
                    
                    logger.info(f"[Webhook] Sent '{event_type}' to {sub['name']}")
                    count += 1
                except Exception as e:
                    logger.error(f"[Webhook] Failed to send to {sub['name']}: {e}")
                    
        return {"status": "success", "webhooks_triggered": count}

# Singleton instance
webhook_manager = WebhookManager()
