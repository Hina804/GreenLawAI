
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

try:
    from tools.climate_tools import ClimateKnowledgeTool
    
    def test_spread_math():
        tool = ClimateKnowledgeTool()
        
        # Test Case 1: High Wind, High Temp (Critical)
        res1 = tool.calculate_village_risk(temp=35, wind_speed=40, humidity=20, distance_km=5)
        print(f"Test 1 (Hard): {res1}")
        assert res1['risk_level'] == "CRITICAL"
        assert res1['spread_risk_index'] > 70
        assert res1['estimated_arrival_hours'] <= 0.5
        
        print("\n[PASS] Wildfire Spread Math verified successfully.")

    if __name__ == "__main__":
        test_spread_math()

except Exception as e:
    print(f"[FAIL] Test Failed: {e}")
    sys.exit(1)
