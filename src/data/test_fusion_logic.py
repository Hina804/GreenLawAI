import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from data.geo_intelligence import GeoIntelligenceCoordinator, GeoEvent

def test_fusion_math():
    gc = GeoIntelligenceCoordinator()
    
    # Base Event: NASA FIRMS (Reliability 0.85)
    f = GeoEvent(id="F1", type="fire", lat=34.1, lon=73.2, timestamp=datetime.now(), severity="HIGH", confidence="NOMINAL", source="NASA-FIRMS", details={})
    
    # Case 1: Single Source
    fused_1 = gc.fuse_intelligence_layers([f], None)
    c1 = fused_1[0].details["confidence_score"]
    print(f"Case 1 (Single NASA): {c1} (Expected ~0.85)")
    
    # Case 2: Multi-Source (NASA + GFW)
    d = GeoEvent(id="D1", type="deforestation", lat=34.1, lon=73.2, timestamp=datetime.now(), severity="HIGH", confidence="NOMINAL", source="GFW-Integrated", details={})
    fused_2 = gc.fuse_intelligence_layers([f, d], None)
    # The fuser currently merges GFW into the fire event's confidence
    # Look for the 'fire' event in the output
    fire_evt = [e for e in fused_2 if e.type == 'fire'][0]
    c2 = fire_evt.details["confidence_score"]
    print(f"Case 2 (NASA + GFW): {c2} (Expected > 0.85, ~0.97)")
    
    # Case 3: Recall Heuristic
    # Cloud cover 80% should yield ~20% recall
    weather_cloudy = {"clouds": 80, "fire_risk": 50, "source": "live_api"}
    fused_3 = gc.fuse_intelligence_layers([f], weather_cloudy)
    r3 = fused_3[0].details["system_recall_est"]
    print(f"Case 3 (80% Clouds): Recall {r3} (Expected ~0.2)")

    if c1 == 0.85 and c2 > 0.95 and r3 == 0.2:
        print("\nSUCCESS: Probabilistic Fusion Logic Verified.")
    else:
        print("\nFAILURE: Math mismatch.")

if __name__ == "__main__":
    test_fusion_math()
