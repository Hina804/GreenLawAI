import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path
from loguru import logger
import math

class PredictiveEngine:
    """
    Intelligence Predictive Engine for Deep Forecasting.
    Analyzes historical clusters and climate trends to identify future risk zones.
    """
    def __init__(self, audit_path=None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.audit_path = audit_path or base_dir / "data" / "intelligence_audit.json"
        
    def generate_risk_nodes(self, current_events: List[Any], weather_forecast: List[Dict]) -> List[Dict]:
        """
        Main entry point for deep forecasting.
        Returns a list of high-propensity risk nodes for the next 30 days.
        """
        historical_decisions = self._load_historical_clusters()
        
        # 1. Hot-Zone Density Calculation (Spatial Recurrence)
        risk_nodes = []
        
        # Grid-based clustering of historical VERIFIED incidents
        grid = {} # (lat_bin, lon_bin) -> count
        for d in historical_decisions:
            if d['action'] == 'VERIFIED':
                lat, lon = d['meta'].get('lat'), d['meta'].get('lon')
                if lat and lon:
                    bin = (round(lat, 1), round(lon, 1)) # ~10km grid
                    grid[bin] = grid.get(bin, 0) + 1
                    
        # 2. Climate-Risk Synthesis
        # Calculate max fire risk from 7-day forecast
        max_climate_risk = 0
        if weather_forecast:
            max_climate_risk = max([f.get('fire_risk', 0) for f in weather_forecast])
            
        # 3. Propensity Modeling
        from data.geo_intelligence import IntelligenceFusionEngine
        gic = IntelligenceFusionEngine()
        
        for (lat, lon), count in grid.items():
            # Base propensity from recurrence
            propensity = min(1.0, (count * 0.2)) 
            
            # Climate booster (High climate risk in a historically active zone = Dangerous Window)
            climate_mult = 1.0 + (max_climate_risk / 100.0)
            
            final_risk = min(1.0, propensity * climate_mult)
            
            if final_risk > 0.3: # Lowered threshold for earlier identification
                village = gic._get_tactical_sector(lat, lon)
                risk_nodes.append({
                    "lat": lat,
                    "lon": lon,
                    "village": village,
                    "risk_score": round(final_risk, 2),
                    "confidence": "STOCHASTIC (Trend Analysis)",
                    "prediction_window": "30 Days",
                    "rationale": f"High propensity in {village}: {count} historical incidents. Climate surge factor: {max_climate_risk/100:.2f}."
                })
                
        return sorted(risk_nodes, key=lambda x: x['risk_score'], reverse=True)

    def _load_historical_clusters(self) -> List[Dict]:
        try:
            if not self.audit_path.exists():
                return []
            with open(self.audit_path, 'r') as f:
                data = json.load(f)
                return data.get('decisions', [])
        except Exception as e:
            logger.error(f"Predictive Engine: Audit load failed: {e}")
            return []

predictive_engine = PredictiveEngine()
