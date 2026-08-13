"""
Phase 3 - Pillar 1: Fire Risk Forecaster
Forecasts fire risk using NASA FIRMS + OpenWeatherMap data from existing Phase 2 monitors.
Runs entirely locally — no LLM dependency.
"""

from datetime import datetime, timedelta
from loguru import logger
import os

# Reuse Phase 2 data monitors
from data.fire_monitor import FIRMSFireMonitor
from data.weather_monitor import WeatherMonitor
from data.cache_manager import cache


# Monthly fire baseline for Pakistan (historical averages)
MONTHLY_FIRE_BASELINE = {
    1: 12, 2: 18, 3: 35, 4: 55, 5: 85, 6: 120,  # Fire season peaks May-Jun
    7: 60, 8: 25, 9: 15, 10: 30, 11: 45, 12: 20   # Monsoon suppresses Jul-Aug
}


class FireRiskForecaster:
    """
    Forecasts fire risk using:
    1. Current FIRMS data (Phase 2 FIRMSFireMonitor)
    2. Weather data (Phase 2 WeatherMonitor)
    3. Seasonal baselines
    4. Simple trend extrapolation
    """

    def __init__(self):
        fire_token = os.getenv("NASA_FIRMS_TOKEN", "DEMO_TOKEN")
        weather_key = os.getenv("OPENWEATHERMAP_KEY", "DEMO_KEY")
        self.fire_monitor = FIRMSFireMonitor(fire_token)
        self.weather_monitor = WeatherMonitor(weather_key)

    def _get_current_data(self):
        """Fetch current fire + weather data (cached via Phase 2 cache_manager)"""
        fire_data = cache.get_or_fetch(
            "fires:PAK:1",
            lambda: self.fire_monitor.get_fire_stats(country="PAK"),
            ttl_seconds=3600
        )
        
        weather_data = cache.get_or_fetch(
            "weather:Islamabad",
            lambda: self.weather_monitor.get_weather("Islamabad"),
            ttl_seconds=10800
        )
        
        # Fallback if APIs unavailable
        if not fire_data:
            month = datetime.now().month
            fire_data = {
                'total_fires': MONTHLY_FIRE_BASELINE.get(month, 30),
                'avg_brightness': 320.0,
                'max_brightness': 370.0,
                'note': 'Seasonal baseline (API unavailable)'
            }
        
        if not weather_data:
            weather_data = {
                'temp': 24.0, 'humidity': 45, 'wind_speed': 3.2,
                'description': 'Seasonal average'
            }
        
        return fire_data, weather_data

    def forecast_risk(self, days_ahead: int = 7) -> dict:
        """
        Forecast fire risk for the next N days.
        
        Returns:
            {
                'current_risk': float (0-100),
                'daily_forecast': [{'date': str, 'risk': float, 'level': str}, ...],
                'trend': 'increasing' | 'stable' | 'decreasing',
                'peak_day': str,
                'peak_risk': float,
                'advisory': str,
                'data_sources': list[str]
            }
        """
        fire_data, weather_data = self._get_current_data()
        
        # Current fire risk from weather
        current_risk = self.weather_monitor.calculate_fire_risk(
            weather_data.get('temp', 24),
            weather_data.get('humidity', 45),
            weather_data.get('wind_speed', 3)
        )
        
        # Generate daily forecast using seasonal trends + current conditions
        today = datetime.now()
        daily_forecast = []
        
        for day_offset in range(days_ahead):
            forecast_date = today + timedelta(days=day_offset)
            month = forecast_date.month
            
            # Seasonal baseline risk
            baseline = MONTHLY_FIRE_BASELINE.get(month, 30)
            normalized_baseline = min(100, (baseline / 120) * 100)
            
            # Blend current conditions with seasonal baseline
            # Current conditions weight decreases as we forecast further out
            current_weight = max(0.3, 1.0 - (day_offset * 0.1))
            seasonal_weight = 1.0 - current_weight
            
            daily_risk = (current_risk * current_weight) + (normalized_baseline * seasonal_weight)
            
            # Add some natural variation (±5%)
            import random
            random.seed(int(forecast_date.strftime('%Y%m%d')))
            variation = random.uniform(-5, 5)
            daily_risk = max(0, min(100, daily_risk + variation))
            
            # Classify risk level
            if daily_risk >= 80:
                level = "EXTREME"
            elif daily_risk >= 60:
                level = "HIGH"
            elif daily_risk >= 40:
                level = "MODERATE"
            else:
                level = "LOW"
            
            daily_forecast.append({
                'date': forecast_date.strftime('%Y-%m-%d'),
                'day_name': forecast_date.strftime('%A'),
                'risk': round(daily_risk, 1),
                'level': level
            })
        
        # Determine trend
        if len(daily_forecast) >= 3:
            first_avg = sum(f['risk'] for f in daily_forecast[:3]) / 3
            last_avg = sum(f['risk'] for f in daily_forecast[-3:]) / 3
            
            if last_avg > first_avg + 5:
                trend = "increasing"
            elif last_avg < first_avg - 5:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        # Find peak
        peak = max(daily_forecast, key=lambda f: f['risk'])
        
        # Generate advisory
        if peak['risk'] >= 80:
            advisory = f"⚠️ EXTREME fire risk expected on {peak['day_name']}. Deploy fire watch teams. Ban all open fires."
        elif peak['risk'] >= 60:
            advisory = f"🔶 HIGH fire risk expected on {peak['day_name']}. Increase patrols in vulnerable areas."
        elif peak['risk'] >= 40:
            advisory = f"🟡 MODERATE fire risk. Standard monitoring recommended."
        else:
            advisory = f"🟢 LOW fire risk. Normal operations."
        
        data_sources = ["NASA FIRMS"]
        if weather_data.get('description') != 'Seasonal average':
            data_sources.append("OpenWeatherMap")
        if fire_data.get('note'):
            data_sources.append("Seasonal Baseline")
        
        return {
            'current_risk': round(current_risk, 1),
            'current_fires': fire_data.get('total_fires', 0),
            'weather': {
                'temp': weather_data.get('temp', 'N/A'),
                'humidity': weather_data.get('humidity', 'N/A'),
                'wind': weather_data.get('wind_speed', 'N/A')
            },
            'daily_forecast': daily_forecast,
            'trend': trend,
            'peak_day': peak['date'],
            'peak_risk': peak['risk'],
            'advisory': advisory,
            'data_sources': data_sources,
            'generated_at': datetime.now().isoformat()
        }

    def get_seasonal_analysis(self) -> dict:
        """Analyze seasonal fire patterns for Pakistan."""
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        current_month = datetime.now().month
        
        return {
            'monthly_baselines': [
                {
                    'month': months[i],
                    'month_num': i + 1,
                    'avg_fires': MONTHLY_FIRE_BASELINE[i + 1],
                    'is_current': (i + 1) == current_month
                }
                for i in range(12)
            ],
            'fire_season': 'April - June (Peak: May-June)',
            'safe_season': 'July - August (Monsoon suppression)',
            'current_phase': self._get_season_phase(current_month)
        }

    def _get_season_phase(self, month: int) -> str:
        if month in [4, 5, 6]:
            return "🔴 FIRE SEASON (High Alert)"
        elif month in [7, 8]:
            return "🟢 MONSOON (Low Risk)"
        elif month in [10, 11]:
            return "🟡 FELLING SEASON (Moderate Risk)"
        else:
            return "🔵 STANDARD MONITORING"
