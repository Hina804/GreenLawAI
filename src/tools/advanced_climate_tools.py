import json
import os
from typing import Dict, Any, Optional
from loguru import logger
from tools.base_tool import BaseTool

class AdvancedClimateKnowledgeTool(BaseTool):
    """
    Advanced climate intelligence tool using FAO-compliant reference data.
    Provides species-specific ecological metrics and social carbon equivalencies.
    """
    def __init__(self, data_path: str = "e:/GL_AI/data/climate/fao_reference.json"):
        super().__init__(
            name="advanced_climate_knowledge",
            description="Scientific ecological impact analyzer using FAO reference data."
        )
        self.data_path = data_path
        self.reference_data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.data_path):
            logger.warning(f"FAO Reference data not found at {self.data_path}. Using fallback defaults.")
            return {}
        try:
            with open(self.data_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load FAO data: {e}")
            return {}

    def get_species_metrics(self, species_key: str) -> Optional[Dict[str, Any]]:
        """Retrieves scientific metrics for a specific tree species."""
        species_key = species_key.lower().replace(" ", "_")
        return self.reference_data.get("species", {}).get(species_key)

    def calculate_social_equivalents(self, co2_kg: float) -> Dict[str, float]:
        """Translates CO2 mass into relatable human activities."""
        eqs = self.reference_data.get("social_equivalents", {
            "co2_kg_per_km_car": 0.25,
            "co2_kg_per_flight_hour": 90.0
        })
        
        return {
            "driving_km": round(co2_kg / eqs["co2_kg_per_km_car"], 1),
            "flight_hours": round(co2_kg / eqs["co2_kg_per_flight_hour"], 1)
        }

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a scientific ecological impact analysis.
        Parameters:
            - species: Name of the species (e.g., 'Deodar')
            - co2_mt: Total CO2 loss in Metric Tonnes (optional)
            - area_ha: Total area affected in hectares (optional)
        """
        species_name = parameters.get("species", "general")
        metrics = self.get_species_metrics(species_name) or self.get_species_metrics("scrub") or {}
        
        results = {
            "species_info": metrics,
            "status": "success" if metrics else "fallback"
        }
        
        # Calculate social impact if CO2 is provided
        co2_mt = parameters.get("co2_mt")
        if co2_mt:
            co2_kg = co2_mt * 1000
            results["social_impact"] = self.calculate_social_equivalents(co2_kg)
            
        return results
