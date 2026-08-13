from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent

class ProcedureGuideAgent(BaseAgent):
    """
    Agent that provides detailed legal procedural guidance 
    based on the Forest Act 1927 and Cr.P.C.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, component_id: str = "procedure_guide", llm_manager = None, **kwargs):
        super().__init__(name="ProcedureGuideAgent", component_id=component_id, config=config)
        self.legal_milestones = [
            {
                "stage": "Detection & FIR",
                "action": "Immediate registration of FIR under Section 154 CrPC and relevant Forest Act sections (e.g., 26, 33).",
                "timeline": "Day 0"
            },
            {
                "stage": "Arrest & Remand",
                "action": "Accused must be produced before a Magistrate within 24 hours. Physical remand can be sought for recovery of contraband (timber).",
                "timeline": "Day 1-2"
            },
            {
                "stage": "Investigation / Challan",
                "action": "Forest officer completes investigation and submits Challan (Report under Sec 173 CrPC).",
                "timeline": "Week 1-3"
            },
            {
                "stage": "Bail Hearing",
                "action": "Arguments on Post-Arrest Bail. Forest department must present 'Bond/Weight' of tree cutting to oppose bail if damage is high.",
                "timeline": "Week 1-2"
            },
            {
                "stage": "Trial & Evidence",
                "action": "Summoning of witnesses (Rangers, Satellite analysts). Cross-examination.",
                "timeline": "Month 1-6"
            },
            {
                "stage": "Judgment",
                "action": "Final arguments and verdict. Sentencing as per Forest Act 1927 schedules.",
                "timeline": "Final"
            }
        ]

    def get_timeline(self, offense_type: str) -> List[Dict[str, str]]:
        """Returns the procedural timeline for a specific offense."""
        # Custom logic can be added here to vary the timeline based on offense_type
        return self.legal_milestones

    def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Provides procedural guidance based on the query."""
        offense_type = context.get("offense_type", "General") if context else "General"
        timeline = self.get_timeline(offense_type)
        
        return {
            "status": "success",
            "offense": offense_type,
            "procedural_timeline": timeline,
            "law_context": "Forest Act 1927 / Pakistan Penal Code"
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent": "ProcedureGuideAgent",
            "milestones_configured": len(self.legal_milestones)
        }
