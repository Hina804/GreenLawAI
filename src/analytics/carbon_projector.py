"""
Phase 3 - Pillar 1: Carbon Loss Projector
Projects future carbon loss based on current deforestation trends.
Uses Phase 2's SPECIES_CARBON_MAP for species-specific data.
Runs entirely locally — no LLM or API dependency.
"""

from datetime import datetime
from loguru import logger

# Import species carbon data from Phase 2 ClimateAgent
SPECIES_CARBON_MAP = {
    "deodar": {"co2": 150.0, "oxygen": 120.0, "biomass": 450.0},
    "chir_pine": {"co2": 95.0, "oxygen": 80.0, "biomass": 280.0},
    "blue_pine": {"co2": 95.0, "oxygen": 80.0, "biomass": 280.0},
    "spruce": {"co2": 110.0, "oxygen": 90.0, "biomass": 320.0},
    "fir": {"co2": 110.0, "oxygen": 90.0, "biomass": 320.0},
    "general": {"co2": 80.0, "oxygen": 65.0, "biomass": 200.0}
}

# Estimated annual tree loss rates per division (trees/year)
DIVISION_LOSS_RATES = {
    "swat": 850,
    "shangla": 320,
    "abbottabad": 180,
    "mansehra": 450,
    "kaghan": 280,
    "dir": 520,
    "chitral": 150,
    "malakand": 200,
    "kpk_total": 2950
}


class CarbonProjector:
    """
    Projects carbon sequestration loss under different scenarios:
    1. Best-case: 50% reduction in deforestation (strong enforcement)
    2. Current-trend: Same rate continues
    3. Worst-case: 30% increase (weakened enforcement / climate pressure)
    """

    def __init__(self):
        self.carbon_map = SPECIES_CARBON_MAP
        self.loss_rates = DIVISION_LOSS_RATES

    def project_loss(self, years: int = 5, division: str = "kpk_total", 
                     species_mix: dict = None) -> dict:
        """
        Project carbon loss over N years under 3 scenarios.
        
        Args:
            years: Number of years to project (default 5)
            division: Forest division or 'kpk_total' for all KPK
            species_mix: Optional dict of species proportions 
                         e.g. {'deodar': 0.4, 'chir_pine': 0.3, 'spruce': 0.3}
        
        Returns:
            {
                'division': str,
                'years': int,
                'annual_tree_loss': int,
                'species_mix': dict,
                'scenarios': {
                    'best_case': [...],
                    'current_trend': [...],
                    'worst_case': [...]
                },
                'totals': {
                    'best_case': {...},
                    'current_trend': {...},
                    'worst_case': {...}
                },
                'recommendations': list[str]
            }
        """
        # Get annual tree loss rate for division
        base_loss = self.loss_rates.get(division.lower(), self.loss_rates['kpk_total'])
        
        # Default species mix for KPK forests
        if not species_mix:
            species_mix = {
                'deodar': 0.35,
                'chir_pine': 0.25,
                'spruce': 0.15,
                'fir': 0.10,
                'blue_pine': 0.10,
                'general': 0.05
            }
        
        # Calculate weighted average CO2 per tree
        avg_co2_per_tree = sum(
            self.carbon_map.get(sp, self.carbon_map['general'])['co2'] * proportion
            for sp, proportion in species_mix.items()
        )
        avg_o2_per_tree = sum(
            self.carbon_map.get(sp, self.carbon_map['general'])['oxygen'] * proportion
            for sp, proportion in species_mix.items()
        )
        
        # Scenario multipliers
        scenarios = {
            'best_case': {'multiplier': 0.5, 'label': 'Strong Enforcement (50% reduction)'},
            'current_trend': {'multiplier': 1.0, 'label': 'Current Trend (no change)'},
            'worst_case': {'multiplier': 1.3, 'label': 'Weakened Enforcement (+30%)'}
        }
        
        result_scenarios = {}
        result_totals = {}
        
        for scenario_name, scenario_info in scenarios.items():
            yearly_data = []
            cumulative_co2 = 0
            cumulative_o2 = 0
            cumulative_trees = 0
            
            for year in range(1, years + 1):
                # Apply scenario multiplier
                trees_lost = int(base_loss * scenario_info['multiplier'])
                co2_loss = round(trees_lost * avg_co2_per_tree, 1)
                o2_loss = round(trees_lost * avg_o2_per_tree, 1)
                
                # Driving equivalent (avg car: 0.25 kg CO2/km)
                car_km = int(co2_loss / 0.25)
                
                cumulative_co2 += co2_loss
                cumulative_o2 += o2_loss
                cumulative_trees += trees_lost
                
                yearly_data.append({
                    'year': year,
                    'calendar_year': datetime.now().year + year,
                    'trees_lost': trees_lost,
                    'co2_loss_kg': co2_loss,
                    'co2_loss_tonnes': round(co2_loss / 1000, 2),
                    'o2_loss_kg': o2_loss,
                    'car_km_equivalent': car_km,
                    'cumulative_co2_tonnes': round(cumulative_co2 / 1000, 2),
                    'cumulative_trees': cumulative_trees
                })
            
            result_scenarios[scenario_name] = yearly_data
            result_totals[scenario_name] = {
                'label': scenario_info['label'],
                'total_trees_lost': cumulative_trees,
                'total_co2_kg': round(cumulative_co2, 1),
                'total_co2_tonnes': round(cumulative_co2 / 1000, 2),
                'total_o2_kg': round(cumulative_o2, 1),
                'total_car_km': int(cumulative_co2 / 0.25),
                'forest_area_lost_ha': round(cumulative_trees / 400, 1)  # ~400 trees/ha
            }
        
        # Recommendations based on current trend severity
        current_total = result_totals['current_trend']['total_co2_tonnes']
        best_total = result_totals['best_case']['total_co2_tonnes']
        savings = round(current_total - best_total, 2)
        
        recommendations = [
            f"🎯 Strong enforcement could save {savings} tonnes CO2 over {years} years",
            f"🌱 Replanting {int(result_totals['current_trend']['total_trees_lost'] * 1.5):,} trees needed to offset current losses",
            f"🚗 Current trend = {result_totals['current_trend']['total_car_km']:,} km of car emissions equivalent",
        ]
        
        if current_total > 500:
            recommendations.append("⚠️ Critical: Carbon losses exceeding 500 tonnes — emergency measures needed")
        
        return {
            'division': division,
            'years': years,
            'annual_tree_loss': base_loss,
            'avg_co2_per_tree_kg': round(avg_co2_per_tree, 1),
            'species_mix': species_mix,
            'scenarios': result_scenarios,
            'totals': result_totals,
            'recommendations': recommendations,
            'generated_at': datetime.now().isoformat()
        }

    def project_single_species(self, species: str, trees_cut: int = 1) -> dict:
        """
        Quick projection for a single species (used by other agents).
        
        Returns immediate impact + 5-year projection if felling continues.
        """
        sp_key = species.lower().replace(' ', '_')
        sp_data = self.carbon_map.get(sp_key, self.carbon_map['general'])
        
        immediate = {
            'species': species,
            'trees_cut': trees_cut,
            'co2_loss_kg': round(sp_data['co2'] * trees_cut, 1),
            'o2_loss_kg': round(sp_data['oxygen'] * trees_cut, 1),
            'biomass_loss_kg': round(sp_data['biomass'] * trees_cut, 1),
            'car_km_equivalent': int((sp_data['co2'] * trees_cut) / 0.25),
            'trees_to_offset': max(1, int((sp_data['co2'] * trees_cut) / 22))
        }
        
        return immediate

    def format_for_ui(self, projection: dict) -> str:
        """Format projection data for Streamlit display."""
        totals = projection['totals']
        current = totals['current_trend']
        best = totals['best_case']
        worst = totals['worst_case']
        
        output = f"## 📈 {projection['years']}-Year Carbon Projection ({projection['division'].title()})\n\n"
        output += "| Scenario | Trees Lost | CO2 (tonnes) | Car-km Equivalent |\n"
        output += "|----------|-----------|-------------|------------------|\n"
        output += f"| 🟢 {best['label']} | {best['total_trees_lost']:,} | {best['total_co2_tonnes']} | {best['total_car_km']:,} |\n"
        output += f"| 🟡 {current['label']} | {current['total_trees_lost']:,} | {current['total_co2_tonnes']} | {current['total_car_km']:,} |\n"
        output += f"| 🔴 {worst['label']} | {worst['total_trees_lost']:,} | {worst['total_co2_tonnes']} | {worst['total_car_km']:,} |\n\n"
        
        output += "**Recommendations:**\n"
        for rec in projection['recommendations']:
            output += f"  {rec}\n"
        
        return output
