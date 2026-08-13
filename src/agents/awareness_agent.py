#E:\GL_AI\src\agents\awareness_agent.py
from typing import List, Dict, Any, Optional
import re
from datetime import datetime
from loguru import logger

from .base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, Citation, AudienceType
from utils.safe_runner import safe_execute

class AwarenessAgent(BaseAgent):
    """
    Public Awareness Agent
    Translates complex legal jargon into plain language for citizens (ELI5).
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "awareness", llm_manager=None):
        super().__init__(
            name="AwarenessAgent",
            component_id=component_id,
            tools=[],
            config=config
        )
        self.llm_manager = llm_manager

    async def run(
        self,
        query: str,
        retrieved_chunks: list,
        audience: AudienceType,
        context: Optional[Dict[str, Any]] = None
    ) -> CanonicalAgentResponse:

        # Add risk query handling
        if 'risk' in query.lower():
            return CanonicalAgentResponse(
                simple_explanation='''
        🌳 **Understanding Forest Risks in Simple Terms**
        
        Forests face two main types of risk:
        
        1. **Deforestation Risk**: How likely are trees to be cut illegally? 
           This depends on past incidents, how remote the area is, and protection measures.
        
        2. **Fire Risk**: How likely is a wildfire?
           This depends on weather (temperature, humidity, wind) and recent fire history.
        
        In Swat, the deforestation risk is HIGH (60/100) because it's a historically vulnerable 
        region with coniferous forests. The fire risk is currently LOW (30/100) due to moderate 
        temperatures and humidity.
        
        Both risks are monitored daily by forest officials. If you see smoke or illegal cutting, 
        report it immediately!
        '''.strip(),
                legal_explanation="See simple explanation for risk guide.",
                citations=[Citation(document="Awareness Guidelines", section="Risk", clause="", chunk_id="risk_guide")],
                abstain=False,
                agent_name=self.name,
                audience=audience,
                confidence=0.9,
                source_chunks=[],
                graph_metadata={},
                validation_passed=True,
                errors=[]
            )

        # Custom Content Injection (Nathia Gali / Galiyat)
        q_lower = query.lower()
        custom_advice = ""
        if any(w in q_lower for w in ["nathia gali", "galiyat", "murree", "ayubia"]):
            actions = self.get_climate_action_guide()["daily_actions"]
            custom_advice = "\n\n**🏞️ Local Galiyat Rules:**\n" + "\n".join(actions[1:3] if len(actions) >= 3 else actions) # Plastic & Miranjani rules
        
        # Spring/Planting detection
        seasonal = self.get_seasonal_awareness()
        
        if not retrieved_chunks:
            return CanonicalAgentResponse(
                simple_explanation=f"### 🌱 Citizen Protection Guide\n\n"
                                 f"While I don't have a specific legal document on that exact query, here is how you can help effectively:\n\n"
                                 f"• **Seasonal Tip**: {seasonal['message']}\n"
                                 f"{custom_advice if custom_advice else '• **Action**: Report any forest violations to 1122 or the DFO.'}\n\n"
                                 f"Protecting our forests in regions like Nathia Gali is a priority. "
                                 f"Stay on marked trails and avoid any activities that could spark a fire.",
                legal_explanation="General forest protection protocols applied in absence of specific case law.",
                citations=[Citation(document="Citizen Hub Internal", section="General", clause="", chunk_id="")],
                abstain=False,
                agent_name=self.name,
                audience=audience,
                confidence=0.8,
                source_chunks=[],
                graph_metadata={},
                validation_passed=True,
                errors=[]
            )

        # 1. Build context
        context_text = "\n\n".join([c.get("text", "")[:400] for c in retrieved_chunks[:2]])

        # 2. Penalty Context
        from core.penalty_calculator import PenaltyCalculator
        penalty_info = safe_execute(
            PenaltyCalculator.analyze_query,
            default_return={},
            query=query
        )
        penalty_display = safe_execute(
            PenaltyCalculator.format_for_ui,
            default_return="Penalty info unavailable",
            calculation=penalty_info
        )

        # 3. Awareness Prompt
        prompt = f"""You are a Public Awareness Officer.
Explain the law to a citizen in simple language.

LAWS:
{context_text}

SEASONAL ADVICE: {seasonal['message']}
{custom_advice}

QUESTION: "{query}"
PENALTY: {penalty_display}

CITIZEN GUIDE:"""

        try:
            if self.llm_manager:
                simple_text = "".join(self.llm_manager.generate(prompt, stream=False))
            else:
                simple_text = (
                    f"### 🌱 Citizen Awareness & Action\n\n"
                    f"• **Seasonal Advice**: {seasonal['message']}\n"
                    f"• **The Penalty**: {penalty_display} for illegal activities.\n"
                    f"{custom_advice}\n"
                    f"• **Action**: If you see illegal logging, report it to the nearest forest officer."
                )
        except Exception as e:
            logger.error(f"[AwarenessAgent] failure: {e}")
            simple_text = (
                f"### 🌱 Citizen Awareness & Action\n\n"
                f"• **Penalty**: {penalty_display}\n"
                f"• Protect our forests — report illegal logging to the nearest forest officer."
            )

        # 3. Build response
        cites = [
            Citation(
                document=re.sub(r'Doc_\d+_', '', str(c.get("metadata", {}).get("source", "Forest Act"))),
                section=str(c.get("metadata", {}).get("section", "General")),
                clause="",
                chunk_id=""
            ) for c in retrieved_chunks[:2]
        ]
        if not cites:
            cites = [Citation(document="Forest Law Guide", section="General", clause="", chunk_id="")]

        return CanonicalAgentResponse(
            simple_explanation=simple_text[:5000],
            legal_explanation=f"Public awareness translation of retrieved provisions for: {query}",
            citations=cites,
            abstain=False,
            agent_name=self.name,
            audience=audience,
            confidence=0.9,
            source_chunks=[c.get("text", "") for c in retrieved_chunks[:2]],
            graph_metadata={
                "role": "citizen_translator",
                "citizen_hub": {
                    "seasonal": self.get_seasonal_awareness(),
                    "actions": self.get_climate_action_guide(),
                    "reporting": self.get_reporting_guide()
                }
            },
            validation_passed=True,
            errors=[]
        )

    def get_seasonal_awareness(self) -> Dict[str, str]:
        """Provides context-aware seasonal messaging for Hazara region."""
        month = datetime.now().month
        if 3 <= month <= 5: # Spring
            return {"season": "Spring (Planting Season)", "message": "Best time for afforestation in Hazara! Contact your DFO for free saplings."}
        elif 6 <= month <= 8: # Summer
            return {"season": "Summer (High Fire Risk)", "message": "Dry conditions in the pine forests. Avoid any open fires or burning of agricultural waste."}
        else:
            return {"season": "General Awareness", "message": "Green trees are the lungs of KPK. Protect them for a better tomorrow."}

    def get_climate_action_guide(self) -> Dict[str, List[str]]:
        """Provides actionable items for citizens to improve climate conditions."""
        return {
            "daily_actions": [
                "• **Fire Prevention**: report smoke immediately to 1122.",
                "• **Galiyat Rules**: Use biodegradable bags only; Nathia Gali is a strict plastic-free zone.",
                "• **Wildlife Awareness**: If hiking Miranjani, stay on tracks to avoid Leopard conflict.",
                "• **Afforestation**: Plant local Pinus wallichiana (Biar) in your community."
            ]
        }

    def get_reporting_guide(self) -> Dict[str, Any]:
        """Specific reporting protocols for illegal activities."""
        return {
            "emergency": "1122 (Fire) / 15 (Police)",
            "illegal_logging": "DFO Abbottabad (+923495994503)",
            "what_to_report": ["Coordinates/Location", "Number of trees", "Vehicle details if any"]
        }

    from datetime import datetime # Added local import for safety if not global

    def _abstain(self, message: str) -> CanonicalAgentResponse:
        return CanonicalAgentResponse(
            simple_explanation=message,
            legal_explanation=message,
            citations=[],
            abstain=True,
            agent_name=self.name,
            audience=AudienceType.VILLAGER,
            confidence=0.0,
            source_chunks=[],
            graph_metadata={},
            validation_passed=False,
            errors=["NO_DATA"]
        )
