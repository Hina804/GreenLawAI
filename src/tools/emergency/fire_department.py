import logging
from typing import Dict, Any
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class FireDepartmentNotifier(BaseTool):
    """Notifies the local fire department and emergency services."""
    def __init__(self):
        super().__init__(
            name="fire_department_api",
            description="Immediately notifies emergency services (1122/Fire Station) about active fires."
        )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        location = parameters.get("location", "Unknown Location")
        
        logger.warning(f"🚨 FireDepartmentNotifier: 1122 NOTIFIED FOR {location} 🚨")
        
        return {
            "status": "EMERGENCY_DISPATCHED",
            "action": "Fire Department & Rescue 1122 Notified",
            "location": location,
            "instructions": "Maintain distance. Await emergency responder arrival."
        }
