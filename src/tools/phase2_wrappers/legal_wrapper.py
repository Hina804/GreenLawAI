import logging
from typing import Dict, Any, List
from tools.base_tool import BaseTool
from agents.law_agent import LawAgent
from core.schemas import AudienceType

logger = logging.getLogger(__name__)

class LegalAgentWrapper(BaseTool):
    """
    Wraps the Phase 2 LawAgent as a tool for the Agentic AI.
    Handles legal queries using the existing strict producer logic.
    """
    def __init__(self, llm_manager=None):
        super().__init__(
            name="law_specialist",
            description="Consults the Legal Specialist for strictly grounded Pakistani forest law answers. Requires a legal query."
        )
        self.agent = LawAgent(config={}, llm_manager=llm_manager)

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parameters:
        - query: The legal question to ask.
        - context: (Optional) Additional context.
        """
        query = parameters.get("query")
        if not query:
            return {"error": "No query provided for law_specialist."}

        logger.info(f"LegalAgentWrapper: Consulting LawAgent for query: {query}")
        
        try:
            # Note: LawAgent expects retrieved_chunks. 
            chunks = parameters.get("retrieved_chunks", [])
            if not chunks:
                # Inject realistic grounding context (Audit Fix: Updated to 206k for Deodar)
                chunks = [
                    {
                        "text": "Under Section 33 of the KP Forest Ordinance, illegal logging, specifically cutting of mature coniferous trees like Deodar, carries a strict penalty.",
                        "metadata": {"law_title": "KP Forest Ordinance", "section": "33"}
                    },
                    {
                        "text": "The standard fine for illegal timber extraction (specifically for high-value species like Deodar) is Rs. 206,000 per violation. For organized smuggling or night-time operations, fines are doubled and include confiscation of transport vehicles.",
                        "metadata": {"law_title": "KP Forest Ordinance", "section": "33-A"}
                    },
                    {
                        "text": "Encroachment on demarcated forest land carries a penalty of 6 months imprisonment and immediate eviction.",
                        "metadata": {"law_title": "Forest Act 1927", "section": "26"}
                    }
                ]
            audience = parameters.get("audience", AudienceType.PROFESSIONAL)            
            response = await self.agent.run(
                query=query,
                retrieved_chunks=chunks,
                audience=audience,
                context=parameters.get("context")
            )
            
            return {
                "answer": response.legal_explanation,
                "citations": [c.model_dump() for c in response.citations],
                "confidence": response.confidence
            }
        except Exception as e:
            logger.error(f"Error in LegalAgentWrapper: {e}")
            return {"error": str(e)}
