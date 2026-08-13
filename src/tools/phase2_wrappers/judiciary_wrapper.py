import logging
from typing import Dict, Any, Optional
from tools.base_tool import BaseTool
from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent
from agents.judiciary.judgment_prediction_agent import JudgmentPredictionAgent
from agents.judiciary.bail_analyzer_agent import BailAnalyzerAgent
from agents.judiciary.evidence_analyzer_agent import EvidenceAnalyzerAgent
from core.schemas import AudienceType

logger = logging.getLogger(__name__)

class JudiciarySpecialist(BaseTool):
    """
    Unified wrapper for specialized Judicial intelligence.
    Can predict outcomes, analyze bail, and retrieve exact precedents.
    """
    def __init__(self, llm_manager=None):
        super().__init__(
            name="judiciary_specialist",
            description="Specialized legal expert for predicting court outcomes, analyzing bail eligibility, and finding binding precedents."
        )
        self.llm = llm_manager
        # Lazy initialization of agents to save memory
        self._retriever = None
        self._predictor = None
        self._bail_agent = None
        self._evidence_agent = None

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parameters:
        - action: 'retrieve', 'predict', 'bail', 'evidence'
        - query: The specific question/case details.
        """
        action = parameters.get("action", "retrieve")
        query = parameters.get("query")
        context = parameters.get("context", {})

        if not query:
            return {"error": "No query provided for judiciary_specialist."}

        try:
            if action == "retrieve":
                if not self._retriever: self._retriever = CaseRetrievalAgent()
                resp = await self._retriever.run(query, [], AudienceType.JUDICIAL, context)
                return {"answer": resp.response, "type": "precedents"}

            elif action == "predict":
                if not self._predictor: self._predictor = JudgmentPredictionAgent(self.llm)
                resp = await self._predictor.run(query, [], AudienceType.JUDICIAL, context)
                return {"answer": resp.response, "type": "prediction"}

            elif action == "bail":
                if not self._bail_agent: self._bail_agent = BailAnalyzerAgent(self.llm)
                resp = await self._bail_agent.run(query, [], AudienceType.JUDICIAL, context)
                return {"answer": resp.response, "type": "bail_analysis"}

            elif action == "evidence":
                if not self._evidence_agent: self._evidence_agent = EvidenceAnalyzerAgent(self.llm)
                resp = await self._evidence_agent.run(query, [], AudienceType.JUDICIAL, context)
                return {"answer": resp.response, "type": "forensic_analysis"}

            else:
                return {"error": f"Unknown judicial action: {action}"}

        except Exception as e:
            logger.error(f"JudiciarySpecialist Error: {e}")
            return {"error": str(e)}
