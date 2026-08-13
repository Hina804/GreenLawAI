import logging
import os
from typing import Dict, Any
from tools.base_tool import BaseTool
from agents.climate_agent import ClimateAgent
from core.schemas import AudienceType

logger = logging.getLogger(__name__)

class ClimateAgentWrapper(BaseTool):
    """
    Wraps the Phase 2 ClimateAgent as a tool for the Agentic AI.
    Handles climate analysis, fire risk, and 7-day forecasting.
    """
    def __init__(self):
        super().__init__(
            name="climate_oracle",
            description="Consults the Hazara Climate Oracle for real-time weather, wildfire risk (NASA FIRMS), and 7-day forecasts. Ideal for climate/weather queries."
        )
        self.agent = ClimateAgent(config={})

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parameters:
        - query: The climate/weather question to ask.
        """
        query = parameters.get("query")
        if not query:
            return {"error": "No query provided for climate_oracle."}

        logger.info(f"ClimateAgentWrapper: Consulting ClimateAgent for query: {query}")
        
        try:
            # ClimateAgent.run expects: query, retrieved_chunks, audience, context
            response = await self.agent.run(
                query=query,
                retrieved_chunks=[], # ClimateAgent handles its own live data fetching
                audience=AudienceType.DUAL,
                context=parameters.get("context")
            )
            
            return {
                "answer": response.legal_explanation, # This contains the synthesized report
                "metrics": response.graph_metadata.get("metrics", {}),
                "fire_stats": response.graph_metadata.get("fire_stats", {}),
                "forecast": response.graph_metadata.get("forecast", []),
                "weather": response.graph_metadata.get("weather", {}),
                "confidence": response.confidence
            }
        except Exception as e:
            logger.error(f"Error in ClimateAgentWrapper: {e}")
            return {"error": str(e)}
