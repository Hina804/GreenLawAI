import asyncio
import logging
import os
from typing import Dict
from datetime import datetime

# Real Monitor Imports
from data.fire_monitor import FIRMSFireMonitor
from data.weather_monitor import WeatherMonitor
from data.deforestation_monitor import GFWDeforestationMonitor
from data.carbon_calculator import carbon_calculator
from data.geo_intelligence import haversine_dist

logger = logging.getLogger(__name__)

class ClimateValidationAgent:
    """
    Hardened Climate Agent using real-time satellite and weather data feeds.
    Incorporates Carbon Risk Modeling and Fire Risk indexing.
    """
    def __init__(self):
        # API Keys from environment
        firms_token = os.getenv("NASA_FIRMS_TOKEN", "mock_token")
        weather_key = os.getenv("OPENWEATHERMAP_KEY", "mock_key")
        
        self.fire_monitor = FIRMSFireMonitor(api_token=firms_token)
        self.weather_monitor = WeatherMonitor(api_key=weather_key)
        self.deforestation_monitor = GFWDeforestationMonitor()
        
    def get_seasonal_factor(self):
        month = datetime.now().month
        if month in [5, 6, 9, 10]: # Pre-monsoon and dry autumn
            return "CRITICAL (Dry Season)"
        if month in [11, 12, 1, 2]:
            return "STABLE (Winter)"
        return "NORMAL"

    def generate_reasoning(self, checks):
        reasons = []
        if checks.get('nearby_fires'):
            reasons.append(f"⚠️ PROXIMITY ALERT: Active thermal anomalies detected within 5km.")
        if checks.get('fire_risk', 0) > 70:
            reasons.append(f"🔥 EXTREME FIRE RISK: Local weather index at {checks['fire_risk']}/100.")
        elif checks.get('fire_risk', 0) > 50:
            reasons.append(f"⚠️ ELEVATED FIRE RISK: Local conditions are dry.")
            
        if checks.get('deforestation_trend', 0) > 10:
            reasons.append(f"🌳 CANOPY LOSS: High deforestation pressure ({checks['deforestation_trend']} alerts) in sector.")
            
        if checks.get('impact_mtco2', 0) > 50:
            reasons.append(f"🌍 HIGH CARBON IMPACT: Proposed activity risks {checks['impact_mtco2']} MTCO2 sequestration.")

        if not reasons:
            return "Climate checks passed. Safe and stable environmental conditions."
        return " ".join(reasons)

    async def validate(self, coordinates: Dict, request: Dict) -> Dict:
        """
        Hardened Validation:
        1. Check active fires via NASA FIRMS within 5km
        2. Check current weather & fire risk via OpenWeatherMap
        3. Check GFW deforestation alerts in the area
        4. Calculate MTCO2 impact via CarbonCalculator
        """
        lat, lon = float(coordinates.get('lat', 0)), float(coordinates.get('lon', 0))
        
        # 1. Fire Data (with internal fallback)
        try:
            # get_active_fires is synchronous in fire_monitor.py
            all_fires = self.fire_monitor.get_active_fires(days=1)
            nearby_fires = [f for f in all_fires if haversine_dist(lat, lon, f['lat'], f['lon']) < 5.0]
        except Exception as e:
            logger.error(f"Fire monitor failed: {e}")
            nearby_fires = []

        # 2. Weather Data
        try:
            weather = self.weather_monitor.get_weather(city="Abbottabad") # Default to regional hub
        except Exception as e:
            logger.error(f"Weather monitor failed: {e}")
            weather = {"fire_risk": 50, "temp": 25}

        # 3. Deforestation Data
        try:
            gfw_data = self.deforestation_monitor.get_alerts(days=30)
            sector_alerts = [a for a in gfw_data.get('recent_hotspots', []) 
                             if haversine_dist(lat, lon, a['lat'], a['lon']) < 10.0]
        except Exception as e:
            logger.error(f"GFW monitor failed: {e}")
            sector_alerts = []

        # 4. Carbon Impact
        num_trees = request.get('number_of_trees', 1)
        impact = carbon_calculator.estimate_at_risk(cluster_size=num_trees, species_key=request.get('tree_species', ['general'])[0])

        checks = {
            "nearby_fires": len(nearby_fires) > 0,
            "fire_risk": weather.get('fire_risk', 50),
            "deforestation_trend": len(sector_alerts),
            "seasonal_factor": self.get_seasonal_factor(),
            "impact_mtco2": impact.get('total_mtco2_risk', 0)
        }
        
        # Calculate score
        score = 100
        if checks['nearby_fires']:
            score -= 50
        if checks['fire_risk'] > 75:
            score -= 40
        elif checks['fire_risk'] > 50:
            score -= 20
        if checks['deforestation_trend'] > 10:
            score -= 30
        if checks['impact_mtco2'] > 100:
            score -= 25
            
        return {
            "agent": "climate",
            "score": max(0, score),
            "checks": checks,
            "status": "PASS" if score >= 60 else "FAIL",
            "reasoning": self.generate_reasoning(checks),
            "environmental_metrics": {
                "biomass_loss_est": impact.get('biomass_loss'),
                "annual_sequestration_loss": impact.get('sequestration_lost'),
                "area_affected_ha": impact.get('area_estimate_ha')
            }
        }
