import logging
from typing import Dict, Any
from tools.base_tool import BaseTool
from agents.awareness_agent import AwarenessAgent
from core.schemas import AudienceType

logger = logging.getLogger(__name__)

class AwarenessAgentWrapper(BaseTool):
    """
    Wraps the Phase 2 AwarenessAgent as a tool for the Agentic AI.
    Translates complex legal and ecological data into citizen-friendly language.
    """
    def __init__(self):
        super().__init__(
            name="citizen_awareness",
            description="Consults the Public Awareness Officer for plain-language (ELI5) explanations of forest laws, conservation tips, and citizen actions."
        )
        self.agent = AwarenessAgent(config={})

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parameters:
        - query: The question to translate into awareness content.
        """
        query = parameters.get("query")
        if not query:
            return {"error": "No query provided for citizen_awareness."}

        logger.info(f"AwarenessAgentWrapper: Consulting AwarenessAgent for query: {query}")
        
        try:
            # AwarenessAgent.run expects: query, retrieved_chunks, audience, context
            response = await self.agent.run(
                query=query,
                retrieved_chunks=[], # AwarenessAgent handles its own logic/retrieval
                audience=AudienceType.CITIZEN,
                context=parameters.get("context")
            )
            
            return {
                "answer": response.simple_explanation,
                "confidence": response.confidence
            }
        except Exception as e:
            logger.error(f"Error in AwarenessAgentWrapper: {e}")
            return {"error": str(e)}
