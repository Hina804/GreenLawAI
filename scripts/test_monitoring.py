
import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from agents.monitoring_agent import MonitoringAgent

async def test_monitoring():
    print("=== Testing Monitoring Agent (Real CSV Feed) ===")
    
    # Initialize with empty config
    agent = MonitoringAgent(config={})
    
    # Test 1: General Trend (System-wide)
    print("\n--- Test 1: System-wide trends ---")
    res1 = await agent.process("Show me incident trends")
    meta1 = res1.get('incidents_metadata', {})
    print(f"Total Incidents: {meta1.get('total_incidents_found')}")
    print(f"Hotspots: {meta1.get('hotspots')}")
    
    # Test 2: District Filter (Swat)
    print("\n--- Test 2: Swat District Filter ---")
    context = {'entities': {'locations': ['Swat']}}
    res2 = await agent.process("Any incidents in Swat?", context)
    meta2 = res2.get('incidents_metadata', {})
    print(f"Incidents in Swat: {meta2.get('total_incidents_found')}")
    print(f"Filter used: {meta2.get('district_filter')}")
    
    # Check if data matches seed
    if meta1.get('total_incidents_found') >= 8 and meta2.get('total_incidents_found') >= 3:
        print("\n✅ PASS: Real data retrieved successfully.")
    else:
        print("\n❌ FAIL: Data mismatch.")

if __name__ == "__main__":
    asyncio.run(test_monitoring())
