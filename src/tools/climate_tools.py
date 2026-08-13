from typing import Dict, Any, List
from loguru import logger
from dataclasses import dataclass


from tools.base_tool import BaseTool

class ClimateKnowledgeTool(BaseTool):
    """
    Climate intelligence data tool.
    Scaffolding implementation — governance layer to follow.
    """
    def __init__(self):
        super().__init__(
            name="climate_knowledge",
            description="Intelligence overlay for environmental and climate-related query analysis."
        )

    def calculate_village_risk(self, temp: float, wind_speed: float, humidity: float, distance_km: float) -> Dict[str, Any]:
        """
        Tactical Fire Spread Heuristic (Phase 4.5).
        Calculates spread risk and arrival time based on environmental triggers.
        """
        # Spread Factor: Heuristic weightings (Wind is the primary driver)
        spread_factor = (wind_speed * 1.5) + (temp * 0.5) - (humidity * 0.3)
        
        # Arrival Time: Distance / (Effective Spread Velocity)
        # Velocity estimate: 50% of wind speed as effective spread rate
        effective_velocity = wind_speed * 0.5
        time_to_reach = distance_km / effective_velocity if effective_velocity > 0 else float('inf')
        
        return {
            "spread_risk_index": round(min(100, max(0, spread_factor)), 1),
            "estimated_arrival_hours": round(time_to_reach, 1) if time_to_reach != float('inf') else "N/A",
            "risk_level": "CRITICAL" if spread_factor > 70 else "HIGH" if spread_factor > 40 else "MODERATE" if spread_factor > 20 else "LOW"
        }

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve climate-related metrics for the given query.
        """
        query = parameters.get("query", "").lower()
        temp = parameters.get("temperature", 25.0)
        wind = parameters.get("wind_speed", 10.0)
        humidity = parameters.get("humidity", 40.0)
        dist = parameters.get("distance_km")
        
        logger.info(f"[ClimateKnowledgeTool] Executing for: {query}")
        
        results = {
            "tool": self.name,
            "query": query,
            "status": "success",
            "environmental_context": {
                "temp": temp,
                "wind_speed": wind,
                "humidity": humidity
            }
        }

        # If distance and spread factors are present, calculate tactical risk
        if dist is not None or any(kw in query for kw in ["reach", "village", "spread", "arrival"]):
            # Use provided distance or default to tactical 5km if not specified but village mentioned
            actual_dist = dist if dist is not None else 5.0
            risk_analysis = self.calculate_village_risk(temp, wind, humidity, actual_dist)
            results["tactical_fire_analysis"] = risk_analysis
            results["summary"] = (f"Wildfire at {actual_dist}km has a spread risk of {risk_analysis['spread_risk_index']}%. "
                                 f"Estimated arrival at village: {risk_analysis['estimated_arrival_hours']} hours.")
        
        return results
