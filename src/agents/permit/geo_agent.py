import asyncio
import logging
import json
import os
from typing import Dict
from shapely.geometry import shape, Point

logger = logging.getLogger(__name__)

class GeoValidationAgent:
    """
    Validates location against forest boundaries and protected areas using GeoJSON
    """
    def __init__(self, geojson_path: str = "src/data/hazara_boundary.geojson"):
        self.boundary = None
        self.geojson_path = os.path.join(os.getcwd(), geojson_path)
        self._load_boundary()
        
    def _load_boundary(self):
        if not os.path.exists(self.geojson_path):
            logger.error(f"GeoJSON boundary file not found: {self.geojson_path}")
            return
            
        try:
            with open(self.geojson_path, "r") as f:
                data = json.load(f)
                # Assume first feature is the boundary
                self.boundary = shape(data['features'][0]['geometry'])
                logger.info("Hazara boundary GeoJSON loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load GeoJSON boundary: {e}")

    def is_in_hazara_bounds(self, lat, lon):
        if lat is None or lon is None or self.boundary is None:
            return False
            
        try:
            p = Point(float(lon), float(lat)) # Note: Point(lon, lat)
            return self.boundary.contains(p)
        except Exception as e:
            logger.error(f"Error in boundary check: {e}")
            return False

    async def check_protected_area(self, lat, lon):
        # In a production system, this would check against a 'protected_areas.geojson'
        # For this version, we implement a 'restricted zone' around known sensitive landmarks
        # e.g., Nathiagali, Thandiani (mocked for professional logic)
        restricted_zones = [
            {"name": "Nathiagali Global Protected", "lat": 34.07, "lon": 73.39, "radius": 0.02},
            {"name": "Thandiani Reserved Unit", "lat": 34.25, "lon": 73.35, "radius": 0.015}
        ]
        
        for zone in restricted_zones:
            dist = ((lat - zone['lat'])**2 + (lon - zone['lon'])**2)**0.5
            if dist < zone['radius']:
                return {"flag": True, "zone": zone['name']}
        
        return {"flag": False}

    async def get_forest_classification(self, lat, lon):
        # Professional logic: Reserved forests are usually at higher altitudes or specific blocks
        # Here we mock a lat-based classification for Hazara
        if lat > 34.5:
            return "Reserved" # Higher Alpine zones
        return "Guzara" # Lower communal zones
        
    async def verify_khasra(self, khasra, lat, lon):
        # Professional logic: Khasra numbers must follow a specific format
        # In future, this would query a PostGIS land record database
        if not khasra:
            return False
        import re
        return bool(re.match(r'^\d+/\d+$', str(khasra))) or bool(re.match(r'^\d+$', str(khasra)))

    def generate_reasoning(self, checks):
        reasons = []
        if not checks.get('in_hazara'):
            reasons.append("Coordinates are outside the authorized Hazara Division operational box.")
        if checks.get('protected_area', {}).get('flag'):
            reasons.append(f"Location falls within a strictly protected area: {checks['protected_area']['zone']}.")
        if not checks.get('valid_khasra'):
            reasons.append("Khasra number format is invalid or could not be verified against digital records.")
        if checks.get('forest_classification') == 'Reserved':
            reasons.append("Location is within a Reserved Forest; extraction is subject to Section 26 restrictions.")
        
        if not reasons:
            return "Geographic validation successful. Location situated within authorized Guzara forest bounds."
        return " ".join(reasons)

    async def validate(self, coordinates: Dict, location: Dict) -> Dict:
        """
        Check:
        1. Within Hazara/KPK region bounds (via GeoJSON)
        2. Not in prohibited/protected area
        3. Valid forest classification
        """
        lat, lon = coordinates.get('lat'), coordinates.get('lon')
        
        # Ensure we have floats
        try:
            lat = float(lat)
            lon = float(lon)
        except:
            return {
                "agent": "geo",
                "score": 0,
                "status": "FAIL",
                "reasoning": "Invalid or missing coordinates."
            }
        
        checks = {
            "in_hazara": self.is_in_hazara_bounds(lat, lon),
            "protected_area": await self.check_protected_area(lat, lon),
            "forest_classification": await self.get_forest_classification(lat, lon),
            "valid_khasra": await self.verify_khasra(location.get('khasra_number'), lat, lon)
        }
        
        # Calculate score
        score = 100
        if not checks['in_hazara']:
            score -= 100 # Critical fail
        if checks['protected_area']['flag']:
            score -= 60
        if not checks['valid_khasra']:
            score -= 30
        if checks['forest_classification'] == 'Reserved':
            score -= 20 # Not a fail, but reduces score to 'conditional'
            
        return {
            "agent": "geo",
            "score": max(0, score),
            "checks": checks,
            "status": "PASS" if score >= 60 else "FAIL",
            "reasoning": self.generate_reasoning(checks)
        }
