import asyncio
import os
import sys
from pathlib import Path

# Setup paths
_project_root = Path(__file__).resolve().parent.parent
_src_dir = _project_root / "src"

for p in [str(_project_root), str(_src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.services.forest_watchdog import ForestWatchdog
from src.data.weather_monitor import WeatherMonitor
from src.agents.climate_agent import ClimateAgent
from src.agents.awareness_agent import AwarenessAgent

async def test_watchdog():
    print("--- Testing ForestWatchdog ---")
    dog = ForestWatchdog()
    await dog.scan_for_illegal_logging()
    await dog.scan_for_fires()
    print("Watchdog scan completed.")

async def test_climate_oracle():
    print("\n--- Testing Climate Oracle Forecast ---")
    wm = WeatherMonitor(os.getenv("OPENWEATHERMAP_KEY", "DEMO_KEY"))
    forecast = wm.get_forecast("Abbottabad")
    print(f"Forecast for Abbottabad: {len(forecast)} days retrieved.")
    for day in forecast[:3]:
        print(f"  {day['date']}: {day['temp']}C, Fire Risk: {day['fire_risk']}")

async def test_agents():
    print("\n--- Testing Agents in Autonomous Mode ---")
    # Mock config
    config = {"llm": {"provider": "mock"}}
    
    climate = ClimateAgent(config)
    awareness = AwarenessAgent(config)
    
    query = "Is there a fire risk in Abbottabad for the next week?"
    print(f"Query: {query}")
    
    # Test Climate Agent
    resp = await climate.run(query, [], context={})
    print(f"\nClimate Agent Message Preview:\n{resp.legal_explanation[:200]}...")
    
    # Test Awareness Agent
    resp_aw = await awareness.run(query, [], audience="citizen")
    print(f"\nAwareness Agent Simple Explanation:\n{resp_aw.simple_explanation[:200]}...")
    hub = resp_aw.graph_metadata.get('citizen_hub', {})
    print(f"Citizen Hub Data: {hub.get('seasonal', {}).get('season')}")

if __name__ == "__main__":
    asyncio.run(test_watchdog())
    asyncio.run(test_climate_oracle())
    asyncio.run(test_agents())
