import sys
import os
import asyncio
import io
from typing import Dict, Any

# Ensure UTF-8 output for Windows consoles
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agents.climate_agent import ClimateAgent
from data.carbon_calculator import carbon_calculator

async def test_advanced_climate():
    print("Testing Advanced Knowledge Tools (FAO Integration)...")
    
    # 1. Test Carbon Calculator (Scientific Baseline)
    print("1. Testing Carbon Calculator (Deodar)...")
    deodar_risk = carbon_calculator.estimate_at_risk(cluster_size=2, species_key="deodar")
    print(f"Species: {deodar_risk['species']} ({deodar_risk['scientific_name']})")
    print(f"Total MTCO2 Risk: {deodar_risk['total_mtco2_risk']}")
    
    # 2. Test Carbon Calculator (Scrub Fallback)
    print("\n2. Testing Carbon Calculator (Scrub Fallback)...")
    scrub_risk = carbon_calculator.estimate_at_risk(cluster_size=2, species_key="unknown_shrub")
    print(f"Species: {scrub_risk['species']}")
    print(f"Total MTCO2 Risk: {scrub_risk['total_mtco2_risk']}")
    
    # 3. Test ClimateAgent Report (End-to-End)
    print("\n3. Testing ClimateAgent Scientific Report...")
    agent = ClimateAgent(config={"NASA_FIRMS_TOKEN": "demo", "OPENWEATHERMAP_KEY": "demo"})
    response = await agent.run(query="What is the environmental impact of cutting 10 Deodar trees in Swat?", retrieved_chunks=[])
    
    print("\n--- AGENT REPORT PREVIEW ---")
    print(response.legal_explanation[:500] + "...")
    
    # Verify social impact in metadata
    social = response.graph_metadata.get("social", {})
    if social.get("driving_km") > 0:
        print(f"SUCCESS: Social Equivalents Found: {social['driving_km']} km driving.")
    else:
        print("FAILURE: Social equivalents missing from metadata.")

if __name__ == "__main__":
    asyncio.run(test_advanced_climate())
