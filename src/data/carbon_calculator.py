import math
import json
import os
from loguru import logger

class CarbonCalculator:
    """
    Scientific carbon sequestration modeling for Hazara Division. 
    Estimates MTCO2 (Metric Tonnes of CO2) at risk for forest threats.
    """
    def __init__(self, data_path: str = "e:/GL_AI/data/climate/fao_reference.json", tph=250):
        self.TREES_PER_HECTARE = tph
        self.data_path = data_path
        self.fao_data = self._load_fao_data()
        
    def _load_fao_data(self):
        if not os.path.exists(self.data_path):
            return {}
        try:
            with open(self.data_path, "r", encoding="utf-8-sig") as f:
                return json.load(f).get("species", {})
        except Exception as e:
            logger.error(f"Failed to load FAO data in calculator: {e}")
            return {}

    def estimate_at_risk(self, cluster_size, radius_km=10.0, species_key="general"):
        """
        Calculates MTCO2 at risk for a specific intelligence cluster.
        Area affected is assumed to be 5 hectares per individual signal.
        """
        # Minimum estimated fire/logging footprint per satellite signal
        hectares_per_signal = 5.0 
        total_affected_ha = cluster_size * hectares_per_signal
        
        # Pull scientific metrics from FAO reference
        species_info = self.fao_data.get(species_key.lower()) or self.fao_data.get("scrub", {})
        
        # MTCO2 storage per hectare (Biomass Factor * TPH / 1000)
        # 1 tree biomass kg -> MTCO2 conversion: (kg * 0.5 * 3.67 / 1000)
        # Using simplified MTCO2/ha for clarity but grounded in FAO factors
        biomass_mtco2_per_ha = (species_info.get("biomass_factor", 185) * self.TREES_PER_HECTARE * 0.5 * 3.67) / 1000
        
        # 1. Total Biomass Carbon (One-time loss)
        biomass_mtco2 = total_affected_ha * biomass_mtco2_per_ha
        
        # 2. Lost Sequestration (1-year horizon)
        # (kg_per_tree * trees_per_ha * area / 1000)
        annual_seq_kg = species_info.get("annual_sequestration_kg_co2", 12.5)
        sequestration_lost = (annual_seq_kg * self.TREES_PER_HECTARE * total_affected_ha) / 1000
        
        total_risk = biomass_mtco2 + sequestration_lost
        
        return {
            "total_mtco2_risk": round(total_risk, 2),
            "biomass_loss": round(biomass_mtco2, 2),
            "sequestration_lost": round(sequestration_lost, 2),
            "area_estimate_ha": total_affected_ha,
            "species": species_info.get("common_name", "Mixed Pine/Scrub"),
            "scientific_name": species_info.get("scientific_name", "Unclassified")
        }

carbon_calculator = CarbonCalculator()
