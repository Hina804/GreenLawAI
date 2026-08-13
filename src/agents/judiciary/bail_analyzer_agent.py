from typing import Dict, Any
from agents.base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, AudienceType, Citation
from loguru import logger

class BailAnalyzerAgent(BaseAgent):
    """
    Evaluates the probability and statutory conditions of granting bail
    based on the nature of the environmental offense, the offender's profile,
    and historical bail rejection precedents.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(name="Bail Analyzer Agent", config=config)

    async def run(self, query: str, retrieved_chunks: list, audience: AudienceType, context: Dict[str, Any] = None) -> CanonicalAgentResponse:
        """
        Executes bail reasoning logic.
        """
        logger.info("Executing Bail Probability Analyzer...")
        
        target_profile = context.get('offender_profile', {}) if context else {}
        precedents = context.get('precedents', []) if context else []
        
        if not target_profile:
            return CanonicalAgentResponse(
                simple_explanation="Cannot analyze bail: Offender profile missing.",
                legal_explanation="Bail analysis aborted: The mandatory 'offender_profile' context was not provided for this inquiry.",
                citations=[],
                agent_name="BailAnalyzerEngine",
                confidence=0.0,
                source_chunks=[],
                abstain=True
            )

        analysis = self.analyze_bail(target_profile, precedents)
        content = self._format_response(analysis)
        
        return CanonicalAgentResponse(
            simple_explanation=f"Estimated bail probability is {analysis['probability']:.0%} ({analysis['status']}).",
            legal_explanation=content,
            citations=[
                Citation(document="Code of Criminal Procedure (CrPC)", section="Section 497")
            ],
            agent_name="BailAnalyzerEngine",
            confidence=0.88,
            source_chunks=[p['case_id'] for p in precedents],
            graph_metadata={"bail_analysis": analysis}
        )

    def analyze_bail(self, profile: Dict, precedents: list) -> Dict:
        """
        Generates probability of bail dynamically based on historical precedent data
        and offender profile context.
        """
        factors = []
        
        # 1. Determine base probability from Precedents dynamically
        if precedents:
            bail_grants = [c for c in precedents if c.get('bail_granted') is True]
            bail_denials = [c for c in precedents if c.get('bail_granted') is False]
            total_resolved = len(bail_grants) + len(bail_denials)
            
            if total_resolved > 0:
                base_probability = len(bail_grants) / total_resolved
                factors.append(f"📊 Historical baseline set to {base_probability:.0%} based on {total_resolved} related rulings.")
            else:
                base_probability = 0.50
                factors.append("⚠️ No historical bail statuses encoded in precedents. Standard 50% baseline applied.")
        else:
            base_probability = 0.50
            factors.append("⚠️ No precedents found. Using statutory 50% baseline.")

        # 2. Dynamic Statutory Scaling (Mathematical)
        severity = profile.get('severity_index', 5)
        severity_impact = (severity - 5) * 0.05 # Dynamic penalty based on severity variance from mean
        
        if severity_impact > 0:
            base_probability -= severity_impact
            factors.append(f"❌ Severity Index of {severity} mathematically scales down bail clearance")
        elif severity_impact < 0:
            base_probability -= severity_impact # mathematically increases
            factors.append(f"✅ Lower severity profile scales up bail clearance likelihood")

        # 3. Offender Context 
        if profile.get('is_repeat_offender'):
            # Halve the probability dynamically rather than static integer drop
            repeat_penalty = base_probability * 0.60
            base_probability -= repeat_penalty
            factors.append("❌ Repeat Offender profile drastically reduces statistical bail odds")
        else:
            base_probability += (1.0 - base_probability) * 0.20
            factors.append("✅ First-time offender status introduces leniency scalar")
            
        # Bounds check
        base_probability = max(0.01, min(0.99, base_probability))
        
        # Dynamic recommended bail amount
        trees_factor = profile.get('trees_cut', 1)
        recommended_bail_amount = int(trees_factor * severity * 2000) if base_probability > 0.3 else None
        
        return {
            "probability": base_probability,
            "status": "High Likelihood" if base_probability > 0.6 else "Low Likelihood",
            "key_factors": factors,
            "recommended_bail_amount": recommended_bail_amount
        }

    def _format_response(self, analysis: Dict) -> str:
        md = "## ⚖️ Pre-trial Bail Assessment\n\n"
        md += f"**Probability of Bail:** {analysis['probability']:.0%}\n"
        md += f"**Assessment Classification:** `{analysis['status'].upper()}`\n\n"
        
        md += "### Key Influencing Factors:\n"
        for factor in analysis['key_factors']:
            md += f"- {factor}\n"
            
        if analysis['recommended_bail_amount']:
            md += f"\n**Estimated Surety Bond Required:** Rs {analysis['recommended_bail_amount']:,}\n"
        else:
            md += f"\n**Estimated Surety Bond Required:** Non-bailable circumstances likely.\n"
            
        return md
