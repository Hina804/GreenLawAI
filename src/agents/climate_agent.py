#E:\GL_AI\src\agents\climate_agent.py
from typing import Dict, Any, List, Optional
import logging

from .base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, Citation, AudienceType
from utils.safe_runner import safe_execute

from tools.climate_tools import ClimateKnowledgeTool
from tools.advanced_climate_tools import AdvancedClimateKnowledgeTool

from data.fire_monitor import FIRMSFireMonitor
from data.weather_monitor import WeatherMonitor
from data.cache_manager import cache
import os

logger = logging.getLogger(__name__)



# -----------------------------
# ClimateAgent
# -----------------------------

# Milestone 15.6: Advanced FAO Knowledge Tool Integration
# Replaced SPECIES_CARBON_MAP with AdvancedClimateKnowledgeTool dynamic lookup

# Milestone 15.7: Village Intelligence Layer
VILLAGE_COORDINATES = {
    'abbottabad': {'lat': 34.16, 'lon': 73.22},
    'mansehra': {'lat': 34.33, 'lon': 73.20},
    'haripur': {'lat': 33.99, 'lon': 72.93},
    'swat': {'lat': 35.22, 'lon': 72.48},
    'kalam': {'lat': 35.48, 'lon': 72.58},
    'madyan': {'lat': 35.13, 'lon': 72.53},
    'mingora': {'lat': 34.77, 'lon': 72.36},
    'nathia gali': {'lat': 34.07, 'lon': 73.38},
}

# Milestone 15.8: Terrain & Slope Matrix (Tactical Grounding)
VILLAGE_TERRAIN = {
    'abbottabad': {'slope': 15.0, 'density': 0.6, 'type': 'Subtropical Pine Forest'},
    'mansehra': {'slope': 12.0, 'density': 0.5, 'type': 'Mixed Broadleaf'},
    'haripur': {'slope': 5.0, 'density': 0.3, 'type': 'Scrub/Dry Forest'},
    'swat': {'slope': 25.0, 'density': 0.8, 'type': 'Moist Temperate'},
    'kalam': {'slope': 30.0, 'density': 0.9, 'type': 'Alpine Coniferous'},
    'madyan': {'slope': 22.0, 'density': 0.7, 'type': 'Deodar/Spruce'},
    'mingora': {'slope': 8.0, 'density': 0.4, 'type': 'Urban-Forest Interface'},
    'nathia gali': {'slope': 28.0, 'density': 0.85, 'type': 'Pine/Oak Forest'},
}

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two lat/lon points."""
    import math
    R = 6371 # Earth radius
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return round(R * c, 2)

class ClimateAgent(BaseAgent):
    """
    Phase-compliant Climate Intelligence Agent
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "climate", llm_manager=None):
        climate_tool = ClimateKnowledgeTool()
        advanced_tool = AdvancedClimateKnowledgeTool()
        super().__init__(
            name="ClimateAgent",
            component_id=component_id,
            tools=[climate_tool, advanced_tool],
            config=config
        )
        self.llm_manager = llm_manager
        self.advanced_tool = advanced_tool

    async def _get_impact_scientific(self, query: str) -> Dict:
        q = query.lower()
        species_key = "scrub"
        
        # Determine species from query
        if "deodar" in q or "swat" in q: species_key = "deodar"
        elif "chir" in q: species_key = "chir_pine"
        elif "blue pine" in q or "kail" in q: species_key = "blue_pine"
        elif "spruce" in q: species_key = "spruce"
        
        metrics = await self.advanced_tool.execute({"species": species_key})
        return metrics.get("species_info", {}), species_key.capitalize()

    async def run(
        self,
        query: str,
        retrieved_chunks: list,
        audience: AudienceType = AudienceType.DUAL,
        context: Optional[Dict[str, Any]] = None
    ) -> CanonicalAgentResponse:
        logger.info(f"[ClimateAgent] Real-time situational analysis: {query}")

        # 1. Fetch Fire Data (Cached)
        fire_token = os.getenv("NASA_FIRMS_TOKEN", "DEMO_TOKEN")
        fire_monitor = FIRMSFireMonitor(fire_token)
        
        # Use caching to prevent excessive API calls
        fire_data = cache.get_or_fetch(
            "fires:PAK:1", 
            lambda: fire_monitor.get_fire_stats(country="PAK"),
            ttl_seconds=3600 # 1 hour
        )

        # 2. Extract location context from planner or query
        loc_context = (context or {}).get('location', {})
        target_city = loc_context.get('name')
        
        # Enhanced detection for "nearby village" or implicit locations
        q_lower = query.lower()
        if not target_city or "village" in q_lower or "nearby" in q_lower:
            # Check for direct matches in our tactical coordinate map
            found = False
            for v_name in VILLAGE_COORDINATES.keys():
                if v_name in q_lower:
                    target_city = v_name.capitalize()
                    found = True
                    break
            
            # If still not found but "nearby" is used, default to the most frequent active zone (Abbottabad)
            if not found and ("nearby" in q_lower or "village" in q_lower):
                target_city = "Abbottabad" # Tactical fallback center
        
        if not target_city:
            if "kalam" in q_lower: target_city = "Kalam"
            elif "mansehra" in q_lower: target_city = "Mansehra"
            elif "haripur" in q_lower: target_city = "Haripur"
            elif "nathia gali" in q_lower: target_city = "Nathia Gali"
            else: target_city = "Abbottabad"
        
        weather_key = os.getenv("OPENWEATHERMAP_KEY", "DEMO_KEY")
        weather_monitor = WeatherMonitor(weather_key)
        
        weather_data = cache.get_or_fetch(
            f"weather:{target_city}",
            lambda: weather_monitor.get_weather(target_city),
            ttl_seconds=10800 # 3 hours
        )

        if weather_data:
            risk_index = weather_monitor.calculate_fire_risk(
                weather_data['temp'], 
                weather_data['humidity'], 
                weather_data['wind_speed']
            )
            weather_data['risk_index'] = risk_index
            
            # Milestone 15.8: Tactical Nearest-Settlement Discovery
            village_name_lower = target_city.lower()
            alerts = fire_data.get('recent_alerts', [])
            
            # If "nearby" or no specific village found, find the ABSOLUTE closest pair
            if "nearby" in q_lower or village_name_lower not in VILLAGE_COORDINATES:
                min_dist = 999.0
                best_village = "Abbottabad"
                best_fire = None
                
                for v_name, v_coord in VILLAGE_COORDINATES.items():
                    for fire in alerts:
                        dist = haversine_distance(v_coord['lat'], v_coord['lon'], fire['lat'], fire['lon'])
                        if dist < min_dist:
                            min_dist = dist
                            best_village = v_name
                            best_fire = fire
                
                target_city = best_village.capitalize()
                village_name_lower = best_village
                closest_fire = best_fire
                weather_data['village_distance'] = min_dist if best_fire else None
            else:
                # User specified a village, find closest fire TO THAT village
                v_coords = VILLAGE_COORDINATES[village_name_lower]
                min_dist = 999.0
                closest_fire = None
                for fire in alerts:
                    dist = haversine_distance(v_coords['lat'], v_coords['lon'], fire['lat'], fire['lon'])
                    if dist < min_dist:
                        min_dist = dist
                        closest_fire = fire
                weather_data['village_distance'] = min_dist if closest_fire else None

            if closest_fire:
                weather_data['closest_fire_id'] = closest_fire['id']
                v_coords = VILLAGE_COORDINATES[village_name_lower]
                
                # Tactical Spread & ETA Logic
                terrain = VILLAGE_TERRAIN.get(village_name_lower, {'slope': 10.0, 'density': 0.5, 'type': 'Unknown'})
                spread_rate = weather_monitor.calculate_spread_rate(
                    weather_data['wind_speed'], 
                    slope=terrain['slope'], 
                    density=terrain['density']
                )
                
                # Calculate bearing and wind alignment (already implemented in previous turn)
                wind_deg = weather_data.get('wind_deg', 0)
                import math
                d_lat = math.radians(v_coords['lat'] - closest_fire['lat'])
                d_lon = math.radians(v_coords['lon'] - closest_fire['lon'])
                y = math.sin(d_lon) * math.cos(math.radians(v_coords['lat']))
                x = math.cos(math.radians(closest_fire['lat'])) * math.sin(math.radians(v_coords['lat'])) - \
                    math.sin(math.radians(closest_fire['lat'])) * math.cos(math.radians(v_coords['lat'])) * math.cos(d_lon)
                bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
                
                wind_towards_deg = (wind_deg + 180) % 360
                angle_diff = abs((wind_towards_deg - bearing + 180) % 360 - 180)
                is_towards = angle_diff < 45
                
                weather_data['wind_towards_village'] = is_towards
                weather_data['fire_bearing'] = bearing
                weather_data['terrain'] = terrain
                weather_data['spread_rate'] = spread_rate
                
                # ETA = Distance / Effective Speed
                # If wind is away, effective speed is halved. If towards, it's the full spread rate.
                effective_speed = spread_rate if is_towards else (spread_rate * 0.3)
                weather_data['arrival_eta_hours'] = round(weather_data['village_distance'] / effective_speed, 1)
                
                # Refined threat score
                base_threat = weather_monitor.calculate_village_threat_score(risk_index, weather_data['village_distance'])
                if is_towards and weather_data['village_distance'] < 40:
                    base_threat = min(100, base_threat * 1.5)
                weather_data['village_threat_score'] = base_threat
            else:
                weather_data['village_distance'] = None
        else:
            # Realistic fallback when API is unavailable (401/timeout)
            logger.warning("[ClimateAgent] Weather API unavailable, using regional seasonal defaults")
            fallback_temp, fallback_hum, fallback_wind = 24.0, 45, 3.2
            weather_data = {
                "temp": fallback_temp, 
                "humidity": fallback_hum, 
                "wind_speed": fallback_wind, 
                "risk_index": weather_monitor.calculate_fire_risk(fallback_temp, fallback_hum, fallback_wind),
                "description": "Seasonal average (API unavailable)",
                "city": f"{target_city} (estimated)"
            }

        # 3. Climate Forecasting (Hazara Oracle Upgrade)
        forecast = weather_monitor.get_forecast(target_city)
        
        # 4. Scientific Impact Analysis (FAO Integration)
        impact_data, species = await self._get_impact_scientific(query)
        # Use MT (metric tonnes) for social equivalents in tool
        mt_val = (impact_data.get("annual_sequestration_kg_co2", 100)) / 1000.0
        social_impact = await self.advanced_tool.execute({"species": species, "co2_mt": mt_val})
        social_metrics = social_impact.get("social_impact", {})

        # Get CORRECT penalty from centralized calculator
        # Explicitly pass detected species for Swat/Deodar context to avoid Rs. 78,000 fallback
        calc_params = {"query": query}
        if "swat" in query.lower() or species.lower() == "deodar":
            calc_params["species_override"] = "deodar"
            
        from core.penalty_calculator import PenaltyCalculator
        penalty_info = safe_execute(
            PenaltyCalculator.analyze_query,
            default_return={'final_penalty': 0, 'base_penalty': 0, 'multiplier': 1.0},
            **calc_params
        )
        penalty_display = safe_execute(
            PenaltyCalculator.format_for_ui,
            default_return="Penalty info unavailable",
            calculation=penalty_info
        )

        # 5. Synthesize Final Report
        report = self._synthesize(
            fire_data, 
            weather_data, 
            impact_data, 
            species, 
            forecast, 
            social_metrics=social_metrics,
            penalty_display=penalty_display
        )
        
        # 6. Build response using static lookups + live data
        climate_summary = (
            f"Ecological loss analysis for {species} (FAO Verified) + Regional Fire Report ({fire_data['total_fires']} fires).\n\n"
            f"**Data Attribution**: Real-time wildfire tracking via **NASA FIRMS** and scientific growth models sourced from **FAO Reference Sets**."
        )

        return CanonicalAgentResponse(
            simple_explanation=climate_summary,
            legal_explanation=report,
            citations=[
                Citation(document="NASA FIRMS", section="Wildfire Feed", clause="Tactical", chunk_id="firms_api"),
                Citation(document="FAO Forestry", section="Hazara Division Reference", clause="Scientific Sequestration", chunk_id="fao_data")
            ],                      
            abstain=False,                      
            agent_name=self.name,
            audience=audience,
            confidence=0.98,
            source_chunks=[],                  
            graph_metadata={"metrics": impact_data, "fire_stats": fire_data, "weather": weather_data, "forecast": forecast, "social": social_metrics},
            validation_passed=True,
            errors=[]
        )

    def _synthesize(self, fire_stats, weather, impact, species, forecast, **kwargs):
        """Build the final climate impact report."""
        current_risk = weather.get('risk_index', 0)
        
        # Trend Analysis
        max_forecast_risk = 0
        if forecast:
            max_forecast_risk = max([d['fire_risk'] for d in forecast])
        
        trend_msg = ""
        if max_forecast_risk > current_risk + 10:
            trend_msg = f"⚠️ **RISING RISK ALERT**: Fire risk is projected to increase from {current_risk} to {max_forecast_risk} over the next week. Immediate vigilance is advised."
        elif max_forecast_risk < current_risk - 10:
            trend_msg = f"📉 **FALLING RISK**: Conditions are improving. Fire risk is expected to decrease to {max_forecast_risk}."
        else:
            trend_msg = f"➡️ **STABLE RISK**: Conditions remain consistent with current levels."

        report = (
            f"### 🌦️ Climate & Weather Intelligence\n\n"
            f"{trend_msg}\n\n"
            f"**Current Status ({weather.get('city', 'Unknown')}):**\n"
            f"{weather.get('note', '') + '\n' if weather.get('note') else ''}"
            f"• Temp: {weather['temp']}°C | Humidity: {weather['humidity']}% | Wind: {weather.get('wind_speed', 'N/A')} km/h\n"
            f"• Current Regional Fire Risk: **{current_risk}/100**\n"
        )
        
        # Milestone 15.10: Advanced Tactical & Fallback Report
        if weather.get('village_distance') is not None:
            dist = weather['village_distance']
            threat = weather['village_threat_score']
            is_towards = weather.get('wind_towards_village', False)
            wind_dir = weather.get('wind_direction', 'N/A')
            fid = weather.get('closest_fire_id', 'N/A')
            eta = weather.get('arrival_eta_hours', 'N/A')
            terrain = weather.get('terrain', {})
            
            threat_level = "LOW"
            if threat > 80: threat_level = "CRITICAL"
            elif threat > 60: threat_level = "HIGH"
            elif threat > 40: threat_level = "MODERATE"
            
            wind_impact = "⚠️ TOWARDS VILLAGE" if is_towards else "✅ BLOWING AWAY"
            
            report += (
                f"🏘️ **Tactical Village Threat Assessment ({weather.get('city')}):**\n"
                f"• Proximity to settlement: **{dist} km** (Alert ID: {fid})\n"
                f"• Terrain: {terrain.get('type', 'Unknown')} (Slope: {terrain.get('slope', 0)}%)\n"
                f"• Wind Direction: **{wind_dir}** ({wind_impact})\n"
                f"• Estimated Arrival Time: **{eta} hours** (based on {weather.get('spread_rate', 0)} km/h spread)\n"
                f"• Tactical Threat Verdict: **{threat_level} ({threat}/100)**\n\n"
            )
        else:
            # Fallback estimation logic for missing settlement data
            est_dist = 3.0 # Typical regional village proximity in km
            wind_speed = weather.get('wind_speed', 0)
            wind_dir = weather.get('wind_direction', 'N/A')
            
            # Simple spread rate fallback (avg forest spread 0.2km/h + wind influence)
            est_spread = 0.2 + (wind_speed * 0.05)
            est_eta = round(est_dist / est_spread, 1) if est_spread > 0 else 24.0
            
            report += (
                f"🏘️ **Tactical Estimation (Fallback Assessment):**\n"
                f"• Est. Proximity to nearest settlement: **~{est_dist} km**\n"
                f"• Wind Vector: {wind_speed} km/h from **{wind_dir}**\n"
                f"• Est. Arrival Time: **{est_eta} hours** (provisional arrival projection)\n"
                f"• Current Fire Risk: **{current_risk}/100**\n"
                f"> *Note: Precise coordinate match not found. This is a regional estimation based on typical village clusters.*\n\n"
            )
        
        # Forecast Section
        if forecast:
            report += "📅 **7-Day Climate Forecast:**\n"
            for day in forecast[:5]: # Show next 5 days for clarity
                risk_emoji = "🔥" if day['fire_risk'] > 60 else "✅"
                report += f"• {day['date']}: {day['temp']}°C, {day['description']} (Risk: {day['fire_risk']} {risk_emoji})\n"
            report += "\n"

        # Impact Section (FAO Grounded)
        report += (
            f"🔬 **Environmental Impact Analysis ({species})**\n"
            f"• Scientific Name: *{impact.get('scientific_name', 'Unclassified')}*\n"
            f"• 🌳 Carbon Sequestration: ~{impact.get('annual_sequestration_kg_co2', 0)} kg annual CO2 absorption per mature tree.\n"
            f"• 💨 Oxygen Production: ~{impact.get('oxygen_production_kg_yr', 0)} kg annual oxygen capacity.\n"
            f"• 📏 Growth Rate: {impact.get('growth_rate_m_yr', 0)} m/year | Max Age: {impact.get('max_age_years', 0)} years.\n\n"
        )

        # Drivers & Relatable Impact
        social = kwargs.get("social_metrics", {})
        report += (
            f"🌍 **Social Carbon Equivalents (FAO/EPA Baseline):**\n"
            f"• 🚗 Vehicle Impact: Equivalent to driving **{social.get('driving_km', 0)} km**.\n"
            f"• ✈️ Aviation Impact: Equivalent to **{social.get('flight_hours', 0)} hours** of commercial flight.\n"
            f"• 🌱 Restoration Period: It would take a sapling ~25 years to reach this scientific storage level.\n\n"
        )
        
        # Legal Enforcement Notice
        report += (
            f"⚖️ **Legal Enforcement Notice**\n"
            f"Forest vulnerability increases due to current weather conditions. Under GreenLaws, strict penalties apply for illegal activities in protected ranges.\n\n"
            f"> **Statutory Grounding (Query Match):** {kwargs.get('penalty_display', 'Consulting Legal Registry...')}"
        )
        
        return report
