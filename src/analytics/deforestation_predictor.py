"""
Phase 3 - Pillar 1: Deforestation Risk Predictor
Uses historical incident data + GFW data to predict deforestation risk by region.
Runs entirely locally with scikit-learn (no Colab/LLM dependency).
"""

import json
import os
import math
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from loguru import logger

# Attempt sklearn import - graceful fallback if not installed
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("[DeforestationPredictor] scikit-learn not installed, using rule-based fallback")


# KPK Forest Division coordinates and metadata
KPK_DIVISIONS = {
    "swat": {"lat": 35.22, "lon": 72.35, "area_ha": 45000, "type": "coniferous", "base_risk": 75},
    "shangla": {"lat": 34.87, "lon": 72.60, "area_ha": 12000, "type": "coniferous", "base_risk": 65},
    "abbottabad": {"lat": 34.15, "lon": 73.22, "area_ha": 22000, "type": "mixed", "base_risk": 50},
    "mansehra": {"lat": 34.33, "lon": 73.20, "area_ha": 35000, "type": "coniferous", "base_risk": 60},
    "kaghan": {"lat": 34.83, "lon": 73.50, "area_ha": 28000, "type": "alpine", "base_risk": 55},
    "dir": {"lat": 35.20, "lon": 71.88, "area_ha": 18000, "type": "coniferous", "base_risk": 70},
    "chitral": {"lat": 35.85, "lon": 71.79, "area_ha": 40000, "type": "dry_temperate", "base_risk": 40},
    "malakand": {"lat": 34.57, "lon": 71.93, "area_ha": 15000, "type": "scrub", "base_risk": 45},
}

# Seasonal risk multipliers (Pakistan forestry calendar)
SEASONAL_RISK = {
    1: 0.7, 2: 0.8, 3: 1.0, 4: 1.1, 5: 1.3, 6: 1.4,  # Jan-Jun (fire season peaks May-Jun)
    7: 0.9, 8: 0.8, 9: 0.9, 10: 1.2, 11: 1.3, 12: 0.9  # Jul-Dec (felling peaks Oct-Nov)
}


class DeforestationPredictor:
    """
    Predicts deforestation risk per region using:
    1. Historical incident frequency from incidents.json
    2. Seasonal patterns
    3. Species vulnerability
    4. Regional base risk from GFW data
    
    Uses RandomForestClassifier when sklearn available, 
    falls back to weighted heuristics otherwise.
    """

    def __init__(self):
        self.incidents = self._load_historical()
        self.model = None
        self.label_encoders = {}
        self._regional_stats = self._compute_regional_stats()
        
        if HAS_SKLEARN and len(self.incidents) >= 3:
            self._train_model()

    def _load_historical(self):
        """Load from incidents.json (Phase 2 data)"""
        incidents_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'incidents.json')
        try:
            if os.path.exists(incidents_path):
                with open(incidents_path, 'r') as f:
                    data = json.load(f)
                logger.info(f"[DeforestationPredictor] Loaded {len(data)} historical incidents")
                return data
        except Exception as e:
            logger.error(f"[DeforestationPredictor] Failed to load incidents: {e}")
        
        # Fallback: generate realistic training data
        return self._generate_training_data()

    def _generate_training_data(self):
        """Generate realistic synthetic incidents for model training"""
        import random
        random.seed(42)
        
        species = ['Deodar', 'Chir Pine', 'Blue Pine', 'Spruce', 'Fir']
        locations = list(KPK_DIVISIONS.keys())
        statuses = ['investigating', 'filed', 'court', 'resolved']
        
        data = []
        for i in range(50):
            loc = random.choice(locations)
            date = (datetime.now() - timedelta(days=random.randint(1, 365))).strftime('%Y-%m-%d')
            is_night = random.random() < 0.3
            data.append({
                'id': f'SYNTH-{i:04d}',
                'date': date,
                'location': f"{loc.title()}, Forest Zone",
                'species': random.choice(species),
                'violation': f"Illegal felling of {random.choice(species)}",
                'status': random.choice(statuses),
                'night_incident': is_night,
            })
        
        logger.info(f"[DeforestationPredictor] Generated {len(data)} synthetic training incidents")
        return data

    def _compute_regional_stats(self):
        """Compute per-region incident frequency and patterns"""
        stats = defaultdict(lambda: {'count': 0, 'species': Counter(), 'night_ratio': 0, 'months': Counter()})
        
        for inc in self.incidents:
            # Match location to division
            loc = inc.get('location', '').lower()
            matched_div = 'general'
            for div_name in KPK_DIVISIONS:
                if div_name in loc:
                    matched_div = div_name
                    break
            
            stats[matched_div]['count'] += 1
            stats[matched_div]['species'][inc.get('species', 'Unknown')] += 1
            
            if inc.get('night_incident'):
                stats[matched_div]['night_ratio'] += 1
            
            try:
                month = datetime.strptime(inc['date'], '%Y-%m-%d').month
                stats[matched_div]['months'][month] += 1
            except:
                pass
        
        # Normalize night ratio
        for div in stats:
            total = stats[div]['count']
            if total > 0:
                stats[div]['night_ratio'] = stats[div]['night_ratio'] / total
        
        return dict(stats)

    def _train_model(self):
        """Train RandomForest on incident patterns (if sklearn available)"""
        if not HAS_SKLEARN:
            return
        
        try:
            features = []
            labels = []
            
            for div_name, div_info in KPK_DIVISIONS.items():
                stats = self._regional_stats.get(div_name, {})
                incident_count = stats.get('count', 0) if isinstance(stats, dict) else 0
                night_ratio = stats.get('night_ratio', 0) if isinstance(stats, dict) else 0
                
                for month in range(1, 13):
                    month_incidents = stats.get('months', {}).get(month, 0) if isinstance(stats, dict) else 0
                    
                    feature = [
                        div_info['area_ha'],
                        div_info['base_risk'],
                        SEASONAL_RISK.get(month, 1.0),
                        incident_count,
                        night_ratio,
                        month_incidents,
                        month
                    ]
                    features.append(feature)
                    
                    # Risk label: 0=LOW, 1=MEDIUM, 2=HIGH
                    risk_score = div_info['base_risk'] * SEASONAL_RISK.get(month, 1.0) + incident_count * 2
                    if risk_score > 80:
                        labels.append(2)
                    elif risk_score > 50:
                        labels.append(1)
                    else:
                        labels.append(0)
            
            self.model = RandomForestClassifier(n_estimators=50, random_state=42, max_depth=5)
            self.model.fit(features, labels)
            logger.info("[DeforestationPredictor] RandomForest model trained successfully")
        except Exception as e:
            logger.error(f"[DeforestationPredictor] Model training failed: {e}")
            self.model = None

    def predict_risk(self, location: str, season: str = None) -> dict:
        """
        Predict deforestation risk for a location.
        
        Returns:
            {
                'location': str,
                'risk_score': float (0-100),
                'risk_level': str ('LOW' / 'MEDIUM' / 'HIGH' / 'CRITICAL'),
                'confidence': float (0-1),
                'factors': list[str],
                'historical_incidents': int,
                'seasonal_multiplier': float
            }
        """
        loc_lower = location.lower()
        matched_div = None
        div_info = None
        
        for div_name, info in KPK_DIVISIONS.items():
            if div_name in loc_lower:
                matched_div = div_name
                div_info = info
                break
        
        if not div_info:
            div_info = {"lat": 34.5, "lon": 72.5, "area_ha": 20000, "type": "mixed", "base_risk": 50}
            matched_div = "general"
        
        # Current month for seasonal adjustment
        month = datetime.now().month
        if season:
            season_map = {'winter': 1, 'spring': 4, 'summer': 6, 'monsoon': 7, 'autumn': 10, 'fall': 10}
            month = season_map.get(season.lower(), month)
        
        seasonal_mult = SEASONAL_RISK.get(month, 1.0)
        stats = self._regional_stats.get(matched_div, {'count': 0, 'night_ratio': 0})
        incident_count = stats.get('count', 0) if isinstance(stats, dict) else 0
        night_ratio = stats.get('night_ratio', 0) if isinstance(stats, dict) else 0
        
        # Use ML model if available, otherwise rule-based
        if self.model and HAS_SKLEARN:
            feature = [[
                div_info['area_ha'],
                div_info['base_risk'],
                seasonal_mult,
                incident_count,
                night_ratio,
                stats.get('months', {}).get(month, 0) if isinstance(stats, dict) else 0,
                month
            ]]
            risk_class = self.model.predict(feature)[0]
            risk_proba = self.model.predict_proba(feature)[0]
            confidence = float(max(risk_proba))
            risk_score = [30, 60, 85][risk_class]
        else:
            # Rule-based fallback
            risk_score = div_info['base_risk'] * seasonal_mult
            risk_score += incident_count * 3
            risk_score += night_ratio * 10
            risk_score = min(100, max(0, risk_score))
            confidence = 0.65
        
        # Build factors explanation
        factors = []
        if seasonal_mult > 1.1:
            factors.append(f"High-risk season (×{seasonal_mult})")
        if incident_count > 2:
            factors.append(f"{incident_count} recent incidents in this area")
        if night_ratio > 0.2:
            factors.append(f"{night_ratio:.0%} incidents occur at night")
        if div_info['base_risk'] > 60:
            factors.append(f"Historically vulnerable region ({div_info['type']} forest)")
        if not factors:
            factors.append("Baseline risk assessment")
        
        # Risk level classification
        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            'location': location,
            'division': matched_div,
            'risk_score': round(risk_score, 1),
            'risk_level': risk_level,
            'confidence': round(confidence, 2),
            'factors': factors,
            'historical_incidents': incident_count,
            'seasonal_multiplier': seasonal_mult,
            'coordinates': {'lat': div_info.get('lat', 34.5), 'lon': div_info.get('lon', 72.5)},
            'model_type': 'RandomForest' if self.model else 'rule-based'
        }

    def generate_heatmap_data(self):
        """
        Generate risk data for all KPK divisions for Folium heatmap.
        Returns list of [lat, lon, risk_score] for HeatMap layer.
        """
        heatmap_points = []
        division_details = []
        
        for div_name, div_info in KPK_DIVISIONS.items():
            prediction = self.predict_risk(div_name)
            heatmap_points.append([
                div_info['lat'],
                div_info['lon'],
                prediction['risk_score'] / 100.0  # Normalize to 0-1
            ])
            division_details.append({
                'name': div_name.title(),
                'lat': div_info['lat'],
                'lon': div_info['lon'],
                'risk_score': prediction['risk_score'],
                'risk_level': prediction['risk_level'],
                'incidents': prediction['historical_incidents'],
                'factors': prediction['factors']
            })
        
        return {
            'heatmap_points': heatmap_points,
            'divisions': division_details,
            'generated_at': datetime.now().isoformat()
        }
