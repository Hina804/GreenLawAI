"""
Phase 3 - PredictionAgent
Wraps all predictive analytics into a BaseAgent-compatible format
for seamless integration with the Phase 2 coordinator pipeline.
"""

from typing import Dict, Any
from loguru import logger
from datetime import datetime

from .base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, Citation, AudienceType

from analytics.deforestation_predictor import DeforestationPredictor
from analytics.fire_predictor import FireRiskForecaster
from analytics.carbon_projector import CarbonProjector


class PredictionAgent(BaseAgent):
    """
    Phase 3 Intelligence Agent - Predictive Analytics
    Generates deforestation risk predictions, fire forecasts, and carbon projections.
    Runs entirely locally (scikit-learn + rule-based), no LLM dependency.
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "prediction", llm_manager=None):
        super().__init__(
            name="PredictionAgent",
            component_id=component_id,
            tools=[],
            config=config
        )
        self.llm_manager = llm_manager  # Not used, but kept for registry compatibility
        
        # Initialize predictive models
        try:
            self.deforestation = DeforestationPredictor()
            logger.info("[PredictionAgent] DeforestationPredictor initialized")
        except Exception as e:
            logger.error(f"[PredictionAgent] DeforestationPredictor init failed: {e}")
            self.deforestation = None
        
        try:
            self.fire = FireRiskForecaster()
            logger.info("[PredictionAgent] FireRiskForecaster initialized")
        except Exception as e:
            logger.error(f"[PredictionAgent] FireRiskForecaster init failed: {e}")
            self.fire = None
        
        try:
            self.carbon = CarbonProjector()
            logger.info("[PredictionAgent] CarbonProjector initialized")
        except Exception as e:
            logger.error(f"[PredictionAgent] CarbonProjector init failed: {e}")
            self.carbon = None

    def _extract_location(self, query: str) -> str:
        """Extract location from query for targeted predictions."""
        q = query.lower()
        locations = ['swat', 'shangla', 'abbottabad', 'mansehra', 'kaghan', 
                     'dir', 'chitral', 'malakand', 'kalam', 'naran']
        for loc in locations:
            if loc in q:
                return loc.title()
        return "KPK Region"

    def _extract_species(self, query: str) -> str:
        """Extract species from query for carbon projections."""
        q = query.lower()
        species_map = {
            'deodar': 'Deodar', 'cedar': 'Deodar',
            'chir': 'Chir Pine', 'pine': 'Chir Pine',
            'spruce': 'Spruce', 'fir': 'Fir',
            'blue pine': 'Blue Pine'
        }
        for key, name in species_map.items():
            if key in q:
                return name
        return "Deodar"  # Default for KPK

    async def run(
        self,
        query: str,
        retrieved_chunks: list,
        audience: AudienceType = AudienceType.DUAL,
        context: Dict[str, Any] = None
    ) -> CanonicalAgentResponse:
        logger.info(f"[PredictionAgent] Generating predictions for: {query}")
        
        location = self._extract_location(query)
        species = self._extract_species(query)
        
        # --- 1. Deforestation Risk Prediction ---
        deforestation_data = {}
        heatmap_data = {}
        if self.deforestation:
            try:
                deforestation_data = self.deforestation.predict_risk(location)
                heatmap_data = self.deforestation.generate_heatmap_data()
            except Exception as e:
                logger.error(f"[PredictionAgent] Deforestation prediction failed: {e}")
        
        # --- 2. Fire Risk Forecast ---
        fire_forecast = {}
        if self.fire:
            try:
                fire_forecast = self.fire.forecast_risk(days_ahead=7)
            except Exception as e:
                logger.error(f"[PredictionAgent] Fire forecast failed: {e}")
        
        # --- 3. Carbon Projection ---
        carbon_projection = {}
        carbon_immediate = {}
        if self.carbon:
            try:
                carbon_projection = self.carbon.project_loss(years=5)
                carbon_immediate = self.carbon.project_single_species(species, trees_cut=1)
            except Exception as e:
                logger.error(f"[PredictionAgent] Carbon projection failed: {e}")
        
        # --- Build formatted response ---
        prediction_text = self._format_predictions(
            location, species, deforestation_data, fire_forecast, carbon_projection, carbon_immediate
        )
        
        simple_text = (
            f"Predictive Analytics for {location}: "
            f"Deforestation risk {deforestation_data.get('risk_level', 'N/A')}, "
            f"Fire risk {'trending ' + fire_forecast.get('trend', 'stable') if fire_forecast else 'N/A'}"
        )
        
        return CanonicalAgentResponse(
            simple_explanation=simple_text,
            legal_explanation=prediction_text,
            citations=[
                Citation(document="Phase 3 Analytics", section="Predictive Models", clause="scikit-learn + Rule-based", chunk_id="prediction")
            ],
            abstain=False,
            agent_name=self.name,
            audience=audience,
            confidence=0.85,
            source_chunks=[],
            graph_metadata={
                "predictions": {
                    "deforestation": deforestation_data,
                    "fire_forecast": fire_forecast,
                    "carbon_projection": carbon_projection,
                    "carbon_immediate": carbon_immediate,
                    "heatmap": heatmap_data
                }
            },
            validation_passed=True,
            errors=[]
        )

    def _format_predictions(self, location, species, deforestation, fire, carbon, carbon_imm):
        """Format all prediction data into readable markdown."""
        sections = []
        
        # --- Deforestation Risk ---
        if deforestation:
            risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(
                deforestation.get('risk_level', ''), '⚪'
            )
            sections.append(
                f"## 📊 Deforestation Risk: {location}\n\n"
                f"| Metric | Value |\n"
                f"|--------|-------|\n"
                f"| Risk Score | **{deforestation.get('risk_score', 'N/A')}/100** {risk_emoji} |\n"
                f"| Risk Level | **{deforestation.get('risk_level', 'N/A')}** |\n"
                f"| Confidence | {deforestation.get('confidence', 'N/A')} |\n"
                f"| Historical Incidents | {deforestation.get('historical_incidents', 0)} |\n"
                f"| Season Factor | ×{deforestation.get('seasonal_multiplier', 1.0)} |\n"
                f"| Model | {deforestation.get('model_type', 'N/A')} |\n\n"
                f"**Risk Factors:**\n" +
                "\n".join(f"• {f}" for f in deforestation.get('factors', [])) + "\n"
            )
        
        # --- Fire Forecast ---
        if fire:
            forecast_rows = ""
            for day in fire.get('daily_forecast', [])[:5]:  # Show 5 days
                level_emoji = {"LOW": "🟢", "MODERATE": "🟡", "HIGH": "🟠", "EXTREME": "🔴"}.get(day['level'], '⚪')
                forecast_rows += f"| {day['day_name'][:3]} {day['date']} | {day['risk']}/100 {level_emoji} | {day['level']} |\n"
            
            sections.append(
                f"## 🔥 Fire Risk Forecast (7-Day)\n\n"
                f"**Current Risk:** {fire.get('current_risk', 'N/A')}/100 | "
                f"**Active Fires:** {fire.get('current_fires', 0)} | "
                f"**Trend:** {fire.get('trend', 'stable').title()}\n\n"
                f"| Day | Risk | Level |\n"
                f"|-----|------|-------|\n"
                f"{forecast_rows}\n"
                f"**{fire.get('advisory', '')}**\n"
            )
        
        # --- Carbon Projection ---
        if carbon:
            totals = carbon.get('totals', {})
            current = totals.get('current_trend', {})
            best = totals.get('best_case', {})
            worst = totals.get('worst_case', {})
            
            sections.append(
                f"## 📈 5-Year Carbon Loss Projection\n\n"
                f"| Scenario | Trees Lost | CO₂ (tonnes) | Car-km |\n"
                f"|----------|-----------|-------------|--------|\n"
                f"| 🟢 Best Case | {best.get('total_trees_lost', 0):,} | {best.get('total_co2_tonnes', 0)} | {best.get('total_car_km', 0):,} |\n"
                f"| 🟡 Current | {current.get('total_trees_lost', 0):,} | {current.get('total_co2_tonnes', 0)} | {current.get('total_car_km', 0):,} |\n"
                f"| 🔴 Worst Case | {worst.get('total_trees_lost', 0):,} | {worst.get('total_co2_tonnes', 0)} | {worst.get('total_car_km', 0):,} |\n\n"
            )
            
            recs = carbon.get('recommendations', [])
            if recs:
                sections.append("**Recommendations:**\n" + "\n".join(f"  {r}" for r in recs) + "\n")
        
        # --- Immediate Impact (single tree) ---
        if carbon_imm:
            sections.append(
                f"\n**Immediate Impact (1 {species} tree):** "
                f"{carbon_imm.get('co2_loss_kg', 0)} kg CO₂/year lost "
                f"(≈ {carbon_imm.get('car_km_equivalent', 0)} km driving)\n"
            )
        
        return "\n".join(sections) if sections else "Predictive analytics data currently unavailable."
