"""
Phase 3 - Pillar 3: Patrol Recommender
A proactive agent that generates daily patrol assignments based on
predictive risk scores from Pillar 1.
"""

from loguru import logger
from datetime import datetime
from analytics.deforestation_predictor import DeforestationPredictor
from analytics.fire_predictor import FireRiskForecaster

class PatrolRecommenderAgent:
    """
    Analyzes predictive models to recommend resource allocation
    for forest guards and rapid response units.
    """
    def __init__(self):
        self.deforestation = DeforestationPredictor()
        self.fire = FireRiskForecaster()

    def generate_daily_schedule(self):
        """Generates a schedule assigning personnel to high-risk areas."""
        logger.info("[PatrolRecommender] Generating daily patrol schedule...")
        
        # Get deforestation risks
        heatmap = self.deforestation.generate_heatmap_data()
        divisions = heatmap.get("divisions", [])
        
        # Sort by risk
        divisions.sort(key=lambda x: x['risk_score'], reverse=True)
        
        # Get fire risks
        try:
            fire_data = self.fire.forecast_risk(days_ahead=1)
            fire_risk = fire_data.get('current_risk', 0)
            fire_advisory = fire_data.get('advisory', '')
        except Exception:
            fire_risk = 0
            fire_advisory = "Normal operations"
        
        recommendations = []
        
        # Assign Critical Resources
        critical = [d for d in divisions if d['risk_level'] == 'CRITICAL']
        for d in critical:
            recommendations.append({
                "division": d['name'],
                "action": "Deploy 24/7 Rapid Response Team",
                "priority": "🔴 CRITICAL",
                "reason": f"ML Deforestation Risk {d['risk_score']:0.1f}/100"
            })
            
        # Assign High Resources
        high = [d for d in divisions if d['risk_level'] == 'HIGH']
        for d in high:
            recommendations.append({
                "division": d['name'],
                "action": "Double standard day/night patrols",
                "priority": "🟠 HIGH",
                "reason": f"ML Deforestation Risk {d['risk_score']:0.1f}/100"
            })
        
        # Assign Moderate Resources
        moderate = [d for d in divisions if d['risk_level'] not in ['CRITICAL', 'HIGH']]
        for d in moderate:
            recommendations.append({
                "division": d['name'],
                "action": "Maintain standard patrol schedule",
                "priority": "🟡 MODERATE",
                "reason": f"ML Deforestation Risk {d['risk_score']:0.1f}/100"
            })
            
        # Add Fire Risk Global Override
        if fire_risk >= 80:
            recommendations.insert(0, {
                "division": "ALL",
                "action": "Suspend all timber permits. Implement strict fire ban.",
                "priority": "🔥 EXTREME",
                "reason": fire_advisory
            })
            
        return {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "recommendations": recommendations,
            "total_critical_zones": len(critical),
            "total_high_zones": len(high),
            "total_moderate_zones": len(moderate),
            "total_zones": len(divisions)
        }
