import statistics
from typing import List, Dict, Any
from agents.base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, AudienceType, Citation
from loguru import logger

class JudgmentPredictionAgent(BaseAgent):
    """
    Analyzes historical patterns from similar cases to forecast 
    the probable outcome (verdict, fines, imprisonment) for a new incident.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(name="Judgment Prediction Agent", config=config)

    async def run(self, query: str, retrieved_chunks: list, audience: AudienceType, context: Dict[str, Any] = None) -> CanonicalAgentResponse:
        """
        Executes prediction based on the precedents injected into context by the Retrieval Agent.
        """
        logger.info("Executing Judgment Prediction...")
        
        precedents = context.get('precedents', []) if context else []
        
        if not precedents:
            return CanonicalAgentResponse(
                simple_explanation="Cannot predict outcome: No similar precedents provided.",
                legal_explanation="Cannot predict outcome: No similar precedents provided to base statistics on.",
                citations=[],
                agent_name="JudgmentPredictionEngine",
                confidence=0.0,
                source_chunks=[],
                abstain=True
            )

        try:
            prediction = self.predict(precedents, context.get('offender_profile', {}))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            return CanonicalAgentResponse(
                simple_explanation=f"Crash Traceback: {tb}",
                legal_explanation=str(e),
                citations=[],
                agent_name="JudgmentPredictionEngine",
                confidence=0.0,
                source_chunks=[],
                abstain=True
            )
        content = self._format_response(prediction)
        
        return CanonicalAgentResponse(
            simple_explanation=f"Based on {prediction['sample_size']} similar cases, the predicted verdict is {prediction['predicted_verdict']}.",
            legal_explanation=content,
            citations=[
                Citation(document=r.get("title", "Unknown Case"), chunk_id=r.get("case_id"))
                for r in precedents[:3]
            ],
            agent_name="JudgmentPredictionEngine",
            confidence=prediction['confidence'],
            source_chunks=[p['case_id'] for p in precedents],
            graph_metadata={"prediction": prediction}
        )

    def predict(self, similar_cases: List[Dict], profile: Dict = None) -> Dict:
        """Calculate stat probabilities based on similar mock datasets."""
        profile = profile or {}
        
        guilty_cases = [c for c in similar_cases if c.get('verdict') == 'Guilty']
        guilty_rate = len(guilty_cases) / len(similar_cases) if similar_cases else 0.0
        
        fines = [c.get('penalty_amount_rs', 0) for c in guilty_cases if c.get('penalty_amount_rs', 0) > 0]
        months = [c.get('sentence_months', 0) for c in guilty_cases if c.get('sentence_months', 0) > 0]
        
        predicted_verdict = "Guilty" if guilty_rate > 0.5 else "Not Guilty"
        
        # Calculate dynamic bounds based ONLY on retrieved precedents
        min_fine = min(fines) if fines else 0
        max_fine = max(fines) if fines else 0
        mean_fine = statistics.mean(fines) if fines else 0
        
        # Adjust fine ranges dynamically if variance is 0, to afford context range
        if fines and min_fine == max_fine and min_fine > 0:
            std_adjustment = int(mean_fine * 0.15) # 15% dynamic buffer
            min_fine = max(0, min_fine - std_adjustment)
            max_fine = max_fine + std_adjustment

        min_months = min(months) if months else 0
        max_months = max(months) if months else 0
        mean_months = statistics.mean(months) if months else 0
        
        if min_months > 0 and min_months == max_months:
            dynamic_month_buffer = max(1, int(mean_months * 0.2)) # 20% variance buffer
            max_months += dynamic_month_buffer
            min_months = max(0, min_months - dynamic_month_buffer)
            
        # Dynamic Confidence based on sample size and standard deviation
        if len(similar_cases) > 1:
            try:
                fine_cv = statistics.stdev(fines) / mean_fine if mean_fine > 0 else 0
                month_cv = statistics.stdev(months) / mean_months if mean_months > 0 else 0
                avg_cv = (fine_cv + month_cv) / 2
                base_confidence = max(0.40, 1.0 - avg_cv)
            except statistics.StatisticsError:
                base_confidence = 0.50
        else:
            base_confidence = 0.40
            
        # Sample size scaling: Requires roughly 10 cases to hit theoretical max
        confidence = min(0.98, base_confidence + (len(similar_cases) * 0.04))
        
        # Margin of error shrinks as confidence grows
        margin_of_error = max(2, int((1.0 - confidence) * 60))
        
        return {
            "predicted_verdict": predicted_verdict,
            "confidence": confidence,
            "margin_of_error": margin_of_error,
            "probable_penalty": {
                "fine_range": [int(min_fine), int(max_fine)],
                "mean_fine": int(mean_fine),
                "imprisonment_range": [int(min_months), int(max_months)]
            },
            "sample_size": len(similar_cases)
        }

    def _format_response(self, prediction: Dict) -> str:
        md = "## 🎯 Predicted Legal Outcome\n\n"
        md += f"**Predicted Verdict:** {prediction['predicted_verdict']}\n"
        md += f"**Confidence:** {prediction['confidence']:.0%}\n\n"
        
        pen = prediction['probable_penalty']
        if prediction['predicted_verdict'] == "Guilty":
            md += f"- **Probable Fine:** Rs {pen['fine_range'][0]:,} to Rs {pen['fine_range'][1]:,} *(Average: Rs {pen['mean_fine']:,.0f})*\n"
            md += f"- **Probable Imprisonment:** {pen['imprisonment_range'][0]} to {pen['imprisonment_range'][1]} months\n"
            
        md += f"\n*Based on forensic statistical analysis of {prediction['sample_size']} highly similar court precedents.*"
        return md
