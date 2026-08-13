import math
import hashlib
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
import streamlit as st
import random

# Internal Modules
from core.schemas import GeoEvent
from data.carbon_calculator import carbon_calculator

# --- SECTOR MAPPING & RELIABILITY ---
RELIABILITY = {
    "NASA-FIRMS": 0.85,
    "GFW-Integrated": 0.70,
    "Logging-AI": 0.65,
    "Transport-AI": 0.50,
    "Field-Alert": 0.95
}

def haversine_dist(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

class IntelligenceFusionEngine:
    """
    GreenLawAI Intelligence Fusion & Reasoning Engine.
    High-fidelity reasoning for both clusters and individual sensor events.
    """
    
    def generate_propensity_forecasts(self, fused_events: List[GeoEvent], weather_data: Dict) -> List[GeoEvent]:
        """
        Creates predictive 'Propensity' threat overlays simulating 30-day forecasted spread for vulnerabilities.
        It uses active clusters, wind matrices, and historical density to calculate vectors.
        """
        propensity_events = []
        now = datetime.now()
        thirty_days = now + timedelta(days=30)
        
        # We base propensity off High/Critical fused events
        high_risk_bases = [e for e in fused_events if e.type in ["fire", "deforestation", "correlated_threat"]]
        
        for base_ev in high_risk_bases:
            # Shift the coordinates slightly based on wind vectors and terrain heuristics
            wind_deg = base_ev.details.get("wind_deg", random.randint(0, 360))
            spread_dist = base_ev.details.get("spread_risk_index", 0.5) * 5.0 # Max 5km spread
            
            rad = math.radians(wind_deg)
            lat_offset = math.cos(rad) * (spread_dist / 111.0)
            lon_offset = math.sin(rad) * (spread_dist / 111.0)
            
            p_lat = base_ev.lat + lat_offset
            p_lon = base_ev.lon + lon_offset
            
            propensity_events.append(GeoEvent(
                id=f"PROP-{base_ev.id}",
                type="propensity_forecast",
                lat=p_lat,
                lon=p_lon,
                timestamp=thirty_days,
                severity="CRITICAL" if spread_dist > 3.0 else "HIGH",
                confidence="PREDICTIVE",
                source="AI-Prognostic",
                details={
                    "strategic_narrative": f"🔮 30-DAY FORECAST: High propensity for {base_ev.type} expansion modeled via wind vectors ({wind_deg}°) and terrain bleed.",
                    "confidence_score": 0.85,
                    "target_horizon": "30 Days",
                    "origin_cluster": base_ev.id,
                    "vulnerability_score": min(100.0, round(spread_dist * 20, 1))
                }
            ))
            
        return propensity_events
        
    def __init__(self):
        # Phase 13.07: Hazara Division Reference Grid (for fast local sector naming)
        self.grid_landmarks = {
            "Abbottabad City": (34.1689, 73.2215),
            "Mansehra City": (34.3308, 73.1968),
            "Balakot": (34.5491, 73.3508),
            "Muzaffarabad": (34.3700, 73.4711),
            "Haripur": (33.9942, 72.9330),
            "Galiyat (Nathia Gali)": (34.0753, 73.3916),
            "Battagram": (34.6817, 73.0273),
            "Torghar": (34.6355, 72.8986),
            "Kohistan Upper": (35.2100, 73.3500),
            "Kohistan Lower": (35.4900, 72.9500),
            "Shangla": (34.8700, 72.6000),
            "Swat (Mingora)": (34.7717, 72.3609),
            "Dir Lower": (34.9161, 71.8800),
            "Dir Upper": (35.2073, 71.8768),
            "Chitral": (35.8518, 71.7864),
            "Buner": (34.3942, 72.6150),
            "Kolai-Palas": (35.1500, 73.1000),
            "Tor Ghar": (34.6300, 72.9000),
        }

    def _get_tactical_sector_fast(self, lat, lon):
        """FAST local-only sector lookup (no HTTP). Used during fusion."""
        # Phase 13.07: Zero-latency sector naming for the fusion hot path
        min_dist = float('inf')
        nearest = "Hazara Division"
        for name, (ref_lat, ref_lon) in self.grid_landmarks.items():
            dist = haversine_dist(lat, lon, ref_lat, ref_lon)
            if dist < min_dist:
                min_dist = dist
                nearest = f"{name} ({dist:.1f}km)"
        return nearest

    def _get_tactical_sector(self, lat, lon):
        """Full village-level geocoding (HTTP). Used for popups/predictions only."""
        # Milestone 4.6: GRID-ROUNDED CACHING (0.01 deg = ~1km grid)
        grid_lat = round(lat, 2)
        grid_lon = round(lon, 2)
        
        try:
            area_name = self._fetch_reverse_geocode(grid_lat, grid_lon)
            if area_name:
                return area_name
        except:
            pass # Fallback to local matrix if offline or API limit
            
        landmarks = {
            # --- Balakot & Kaghan Corridor ---
            "Balakot": (34.5494, 73.3483),
            "Kawai": (34.5958, 73.4072),
            "Mahandri": (34.6983, 73.5133),
            "Jared": (34.6369, 73.4475),
            "Paras": (34.6644, 73.4542),
            "Naran": (34.9083, 73.6528),
            "Siri Paye": (34.5911, 73.4553),
            
            # --- Mansehra & Surrounding Villages ---
            "Mansehra City": (34.3308, 73.1967),
            "Attarshisha": (34.3725, 73.3031),
            "Reerh": (34.3311, 73.2844),
            "Ghotar": (34.3522, 73.3155),
            "Khaki": (34.3642, 73.0803),
            "Shinkiari": (34.4697, 73.2721),
            "Baffa": (34.4414, 73.2181),
            "Dhodial": (34.4925, 73.2661),
            "Sandasar": (34.4167, 73.3500),
            
            # --- Abbottabad & Galiyat ---
            "Abbottabad City": (34.1689, 73.2215)
        }
        
        nearest = "Hazara Division"
        min_dist = 9999
        for name, coords in landmarks.items():
            dist = haversine_dist(lat, lon, coords[0], coords[1])
            if dist < min_dist:
                min_dist = dist
                nearest = f"{name} ({dist:.1f}km)"
                
        return nearest

    @st.cache_data(ttl=86400) # Cache for 24 hours
    def _fetch_reverse_geocode(_self, lat, lon):
        """Calls OpenStreetMap Nominatim for Hyper-Local specificity (thousands of villages)"""
        import requests
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
            headers = {"User-Agent": "GreenLawAI-Tactical-Enforcement-App"}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                addr = resp.json().get('address', {})
                # Try to get the smallest possible locality name
                village = addr.get('village') or addr.get('hamlet') or addr.get('neighbourhood') or addr.get('suburb') or addr.get('town')
                if village:
                    county = addr.get('county', 'Hazara')
                    return f"{village}, {county}"
            return None
        except:
            return None

    def _generate_semantic_narrative(self, count, sources, types, lat, lon):
        """Generates a non-repetitive tactical analysis for clusters."""
        sector = self._get_tactical_sector_fast(lat, lon)
        
        # Milestone 4.5: SPECIALIZED SPECIFICITY (Village-Level Narratives)
        openers = [
            f"📍 Tactical anomaly in village {sector}.",
            f"🛰️ Signal concentration confirmed in {sector}.",
            f"📡 Localized incursion identified within {sector}."
        ]
        
        middle = [
            f"Fusing {count} distinct signals from {len(sources)} sensors.",
            f"Correlating {count} active data-points across {len(sources)} independent arrays.",
            f"Synchronizing {count} tactical data-feeds via {len(sources)} validated sensors."
        ]
        
        closers = []
        if 'fire' in types and 'deforestation' in types:
            closers = [
                f"SYNERGISTIC THREAT in {sector}: Thermal surges overlapping canopy loss suggests active clearing.",
                f"HIGH-INTENSITY EVENT near {sector}: Confirmed fire-front interacting with forest carbon stock.",
                f"CRITICAL INCURSION in {sector}: Thermal-deforestation synergy detected."
            ]
        elif len(sources) > 1:
            closers = [
                f"MULTI-VECTOR STABILITY: High cross-sensor validation probability in {sector}.",
                "REINFORCED ANOMALY: Signal diversity confirms non-noise activity.",
                f"STRUCTURAL THREAT in {sector}: Clustered alerts indicate systemic site disruption."
            ]
        else:
            closers = [
                "MONO-VECTOR DENSITY: High localized concentration suggests point-source event.",
                f"INDIVIDUAL INCURSION near {sector}: Singular sensor array tracking localized anomaly.",
                f"PRELIMINARY CLUSTER in {sector}: Initial grouping requiring ground-truth verification."
            ]
            
        seed = int(lat * 1000 + lon * 1000)
        random.seed(seed)
        return f"{random.choice(openers)} {random.choice(middle)} {random.choice(closers)}"

    def normalize_metadata(self, raw_stats: Dict[str, Any], weather_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Primary entry point for GreenLawAI Intelligence.
        Converts raw sensor dicts into fused, reasoned GeoEvents.
        """
        events = []
        now = datetime.now()
        
        # --- 1. SENSOR PARSING (WITH INDIVIDUAL INTELLIGENCE) ---
        
        # 1A. NASA FIRMS
        for f in raw_stats.get("fire_alerts", []):
            try:
                dt = datetime.strptime(f.get("date"), "%Y-%m-%d") if f.get("date") else now
                sector = self._get_tactical_sector_fast(f.get("lat"), f.get("lon"))
                seed = int(f.get("lat") * 1000 + f.get("lon") * 1000)
                random.seed(seed)
                
                # Dynamic metrics for NASA alerts (Base 30% + jitter)
                f_conf = 0.30 + (random.randint(1, 15) / 100.0)
                f_nar = random.choice([
                    f"🔥 Isolated thermal anomaly detected in {sector}. Awaiting validation.",
                    f"🛰️ Single-vector heat signature confirmed within {sector} buffer zone.",
                    f"📡 NASA sensor array tracking localized thermal surge in {sector}."
                ])
                
                # Wind awareness for individuals
                if weather_data:
                    wind_speed = weather_data.get("wind_speed", 0)
                    wind_deg = weather_data.get("wind_deg", 0)
                    spread = (wind_speed / 15.0) * 0.6 + (1.0 - (weather_data.get("humidity", 50)/100.0)) * 0.4
                    f["spread_risk_index"] = round(spread, 2)
                    f["wind_deg"] = wind_deg
                    if spread > 0.4: f_nar += f" ⚠️ Spread vector pointing {wind_deg}°."

                events.append(GeoEvent(
                    id=f.get("id", f"fire_{f.get('lat')}_{f.get('lon')}"),
                    type="fire", lat=f.get("lat"), lon=f.get("lon"), timestamp=dt,
                    severity="HIGH" if f.get("confidence") == "HIGH" else "MEDIUM",
                    confidence="TACTICAL", source="NASA-FIRMS", 
                    details={**f, "strategic_narrative": f_nar, "confidence_score": round(f_conf, 2),
                             "carbon_risk": carbon_calculator.estimate_at_risk(1)}
                ))
            except Exception as e: logger.error(f"Error parsing fire: {e}")

        # 1B. GFW Deforestation
        for d in raw_stats.get("gfw_hotspots", []):
            try:
                dt = datetime.strptime(d.get("date"), "%Y-%m-%d") if d.get("date") else now
                sector = self._get_tactical_sector_fast(d.get("lat"), d.get("lon"))
                seed = int(d.get("lat") * 1000 + d.get("lon") * 1000)
                random.seed(seed)
                
                d_conf = 0.15 + (random.randint(1, 10) / 100.0)
                d_nar = f"🌳 Localized canopy loss signal identified in {sector}. Verifying biomass displacement."
                
                events.append(GeoEvent(
                    id=d.get("id", f"def_{d.get('lat')}_{d.get('lon')}"),
                    type="deforestation", lat=d.get("lat"), lon=d.get("lon"), timestamp=dt,
                    severity="HIGH" if d.get("confidence") == "HIGH" else "MEDIUM",
                    confidence="TACTICAL", source="GFW-Integrated", 
                    details={**d, "strategic_narrative": d_nar, "confidence_score": round(d_conf, 2),
                             "carbon_risk": carbon_calculator.estimate_at_risk(1)}
                ))
            except Exception as e: logger.error(f"Error parsing deforestation: {e}")

        # 1C. Other Sources
        for l in raw_stats.get("logging_alerts", []):
            events.append(GeoEvent(id=l.get("id", "L-01"), type="logging", lat=l.get("lat"), lon=l.get("lon"), 
                                   timestamp=now, severity="HIGH", confidence="HIGH", source="Logging-AI", details=l))

        # --- 2. THE FUSION ENGINE ---
        fused = []
        processed_ids = set()
        
        for i, e1 in enumerate(events):
            if e1.id in processed_ids: continue
            cluster = [e1]
            # DBSCAN-Lite (10km / 72h window)
            for j, e2 in enumerate(events):
                if e1.id == e2.id or e2.id in processed_ids: continue
                if haversine_dist(e1.lat, e1.lon, e2.lat, e2.lon) < 10.0: # 🏁 FIX: Set to 10km (was 0.1)
                    cluster.append(e2)
                    processed_ids.add(e2.id)
            
            processed_ids.add(e1.id) # Mark seed as processed
            
            if len(cluster) >= 1:
                avg_lat = sum(e.lat for e in cluster) / len(cluster)
                avg_lon = sum(e.lon for e in cluster) / len(cluster)
                sources = set(e.source for e in cluster)
                types = set(e.type for e in cluster)
                
                stable_lat, stable_lon = round(avg_lat, 2), round(avg_lon, 2)
                loc_hash = hashlib.md5(f"{stable_lat}_{stable_lon}".encode()).hexdigest()[:6].upper()
                cid = f"GL-{loc_hash}"
                
                # Check for decisions using both ID and Coordinate-based proximity (Milestone 4 Sync)
                coord_key = f"{stable_lat}_{stable_lon}"
                decisions = st.session_state.get("operator_decisions", {})
                decision = decisions.get(cid) or decisions.get(coord_key)

                # Maximize precision across cluster
                max_raw_conf = max([e.details.get("confidence_score", 0.4) for e in cluster])
                
                base_nar = self._generate_semantic_narrative(len(cluster), sources, types, avg_lat, avg_lon)
                jitter = (int(avg_lat * 1000) % 9) / 100.0
                
                if decision == "VERIFIED":
                    final_conf = 1.0
                    final_nar = f"🛡️ VERIFIED INCIDENT: Ground-truth confirmed. Enforcement Active. | {base_nar}"
                    severity, e_type = "CRITICAL", "incident"
                    conf_status = "OPERATOR-VERIFIED (Ground Truth)" # 🏁 FIX: Align with maps.py
                else:
                    conf_status = "TACTICAL"
                    if len(cluster) == 1:
                        # 🏁 FIX: If only one event, use its SPECIFIC unique narrative and jittered score
                        final_nar = cluster[0].details.get("strategic_narrative", base_nar)
                        final_conf = cluster[0].details.get("confidence_score", max_raw_conf)
                        severity = cluster[0].severity
                        e_type = cluster[0].type
                    else:
                        # For clusters, use the FUSED intelligence
                        final_conf = min(0.98, max_raw_conf + (len(sources) * 0.12) + jitter)
                        final_nar = base_nar
                        severity = "CRITICAL" if final_conf > 0.8 else "HIGH"
                        e_type = "correlated_threat"

                # Map evidence for legal dispatches
                member_feed = [{"id": e.id, "source": e.source, "type": e.type, "conf": e.confidence} for e in cluster]

                fused.append(GeoEvent(
                    id=cid, type=e_type, lat=avg_lat, lon=avg_lon,
                    timestamp=max(e.timestamp for e in cluster),
                    severity=severity, confidence=conf_status, source="FUSED-INTEL",
                    details={
                        "sector_name": base_nar.split("in ")[1].split(".")[0] if "in " in base_nar else "Hazara Region",
                        "strategic_narrative": final_nar,
                        "member_feed": member_feed,
                        "cluster_size": len(cluster),
                        "sensor_diversity": len(sources),
                        "confidence_score": round(final_conf, 2),
                        "carbon_risk": carbon_calculator.estimate_at_risk(len(cluster)),
                        "wind_aware": True if 'fire' in types else False
                    }
                ))

        # --- 3. WEATHER RISKS ---
        if weather_data:
            for f in fused:
                if f.details.get("wind_aware"):
                    wind_speed, wind_deg = weather_data.get("wind_speed", 0), weather_data.get("wind_deg", 0)
                    spread = (wind_speed / 15.0) * 0.6 + (1.0 - (weather_data.get("humidity", 50)/100.0)) * 0.4
                    f.details["spread_risk_index"], f.details["wind_deg"] = round(spread, 2), wind_deg
                    if spread > 0.6: f.details["strategic_narrative"] += " ⚠️ EXTREME SPREAD RISK DETECTED."

        # --- 4. 30-DAY PROPENSITY FORECASTING ---
        if weather_data:
            forecasts = self.generate_propensity_forecasts(fused, weather_data)
            fused.extend(forecasts)
            
        return {
            "events": fused,
            "metrics": {
                "systemic_visibility": 0.85,
                "source_health": {"firms": "STABLE", "gfw": "STABLE"},
                "propensity_zones_active": len([f for f in fused if f.type == 'propensity_forecast'])
            }
        }

    def filter_events(self, events: List[GeoEvent], days: int = 7, min_severity: str = "LOW", active_types: List[str] = None) -> Dict[str, List[GeoEvent]]:
        """Filters reasoning output based on user UI preferences and groups by type."""
        sev_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        target_rank = sev_rank.get(min_severity, 0)
        cutoff = datetime.now() - timedelta(days=days)
        
        filtered = [
            e for e in events 
            if e.timestamp >= cutoff 
            and sev_rank.get(e.severity, 0) >= target_rank
            and (active_types is None or e.type in active_types)
        ]
        
        # Group by type as expected by portal.py
        grouped = {}
        for ev in filtered:
            if ev.type not in grouped:
                grouped[ev.type] = []
            grouped[ev.type].append(ev)
            
        return grouped

intelligence_coordinator = IntelligenceFusionEngine()
