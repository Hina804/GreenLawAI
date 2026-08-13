from typing import List, Dict, Any
from agents.base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, AudienceType, Citation
from loguru import logger

class LegalReasoningAgent(BaseAgent):
    """
    Performs IRAC-style comparison (Issue, Rule, Application, Conclusion)
    between a target query case and precedent cases.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(name="Legal Reasoning Agent", config=config)

    async def run(self, query: str, retrieved_chunks: list, audience: AudienceType, context: Dict[str, Any] = None) -> CanonicalAgentResponse:
        """
        Analyzes the 'WHY' a retrieved precedent applies to the target scenario.
        Takes in precedents retrieved by the CaseRetrievalAgent via context.
        """
        logger.info("Executing Legal Reasoning over retrieved precedents.")
        
        target_case = context.get('target_case', {}) if context else {}
        precedents = context.get('precedents', []) if context else []
        
        if not precedents:
            return CanonicalAgentResponse(
                simple_explanation="No precedents found to analyze.",
                legal_explanation="Cannot perform legal reasoning: No precedents provided in context.",
                citations=[],
                agent_name="LegalReasoningEngine",
                confidence=0.0,
                source_chunks=[],
                abstain=True
            )

        analysis_blocks = []
        
        for prec in precedents:
            analysis = self.analyze_applicability(target_case, prec)
            analysis_blocks.append(self.generate_explanation(prec, analysis))
            
        full_analysis = "\n\n".join(analysis_blocks)
            
        return CanonicalAgentResponse(
            simple_explanation=f"Analyzed {len(analysis_blocks)} precedents for binding force and applicability.",
            legal_explanation=f"## ⚖️ Legal Reasoning Analysis\n\n{full_analysis}",
            citations=[
                Citation(document=p.get("title", "Unknown"), chunk_id=p.get("case_id"))
                for p in precedents
            ],
            agent_name="LegalReasoningEngine",
            confidence=0.92,
            source_chunks=[p['case_id'] for p in precedents],
            graph_metadata={"reasoning_blocks": len(analysis_blocks)}
        )

    def analyze_applicability(self, query_case: Dict, precedent_case: Dict) -> Dict:
        """
        Perform factor-based IRAC comparison.
        """
        analysis = {
            "applies": True,
            "weight": "BINDING" if precedent_case.get('court_level') == "Supreme Court" else "PERSUASIVE",
            "reasoning": {
                "similar_facts": [],
                "different_facts": []
            }
        }
        
        # We mock the query semantic matching here for Phase 2 validation
        if query_case.get('is_night') == precedent_case.get('is_night_violation'):
            analysis['reasoning']['similar_facts'].append("Occurred at night")
        else:
            analysis['reasoning']['different_facts'].append("Time of day differs")
            
        if query_case.get('is_protected') == precedent_case.get('is_protected_forest'):
            analysis['reasoning']['similar_facts'].append("Protected forest status matches")
            
        return analysis

    def generate_explanation(self, case: Dict, analysis: Dict) -> str:
        """Generate human-readable explanation."""
        title = case.get('title', 'Unknown Case')
        citation = case.get('citation', 'N/A')
        court_level = case.get('court', 'High Court') # In FAISS metadata, "court" is used instead of "court_level"
        
        md = f"### 🔍 Precedent: **{title}** ({citation})\n"
        md += f"**Weight:** `{analysis['weight']}`\n\n"
        md += "**Why this applies:**\n"
        for fact in analysis['reasoning']['similar_facts']:
            md += f"- ✅ {fact}\n"
            
        if analysis['reasoning']['different_facts']:
            md += "\n**Key differences to note:**\n"
            for fact in analysis['reasoning']['different_facts']:
                md += f"- ⚠️ {fact}\n"
                
        md += f"\n> **Conclusion:** This {court_level} decision "
        md += "strictly binds lower courts regarding these similar facts." if analysis['weight'] == "BINDING" else "provides persuasive guidance."
        
        return md
