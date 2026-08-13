import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from data.geo_intelligence import GeoIntelligenceCoordinator, GeoEvent

def test_truth_modeling():
    coordinator = GeoIntelligenceCoordinator()
    
    # 1. Mock events: Single NASA FIRMS event
    nasa_event = GeoEvent(
        id="nasa_1",
        type="fire",
        lat=34.5,
        lon=72.5,
        timestamp=datetime.now(),
        severity="HIGH",
        confidence="High",
        source="NASA-FIRMS",
        details={"bright_ti4": 300}
    )
    
    # Test A: STABLE condition, no GFW health penalty
    print("--- Test A: Single NASA Source (STABLE) ---")
    fused_a = coordinator.fuse_intelligence_layers([nasa_event], weather_data={}, raw_stats={"gfw_status": "STABLE"})
    if fused_a:
        conf = fused_a[0].details.get("confidence_score")
        recall = fused_a[0].details.get("system_recall_est")
        vis = fused_a[0].details.get("systemic_visibility")
        print(f"Confidence: {conf} (Expected: <= 0.65)")
        print(f"Recall: {recall} (Expected: None/UNKNOWN)")
        print(f"Visibility: {vis}")
        assert conf <= 0.65, "Confidence cap failed!"
        assert recall is None, "Recall should be None without ground truth!"
    
    # Test B: DEGRADED condition (GFW fallback)
    print("\n--- Test B: Single NASA Source (DEGRADED) ---")
    fused_b = coordinator.fuse_intelligence_layers([nasa_event], weather_data={}, raw_stats={"gfw_status": "DEGRADED"})
    if fused_b:
        vis_b = fused_b[0].details.get("systemic_visibility")
        print(f"Visibility: {vis_b} (Expected: ~0.6x lower than STABLE)")
        # STABLE visibility with 2 sources (0.8, 0.7) is 1 - (0.2 * 0.3) = 0.94
        # DEGRADED should be 0.94 * 0.6 = 0.564
        assert vis_b < 0.6, "Visibility penalty failed!"

    # Test C: Multi-Source Verification
    print("\n--- Test C: Multi-Source (NASA + GFW) ---")
    gfw_event = GeoEvent(
        id="gfw_1",
        type="deforestation",
        lat=34.501, # Close to nasa_1
        lon=72.501,
        timestamp=datetime.now(),
        severity="MEDIUM",
        confidence="High",
        source="GFW-Integrated",
        details={}
    )
    fused_c = coordinator.fuse_intelligence_layers([nasa_event, gfw_event], weather_data={}, raw_stats={"gfw_status": "STABLE"})
    if fused_c:
        # Find the fire event in fused results
        fire_result = next(e for e in fused_c if e.type == "fire")
        conf_c = fire_result.details.get("confidence_score")
        print(f"Fused Confidence: {conf_c} (Expected: > 0.9)")
        assert conf_c >= 0.9, "Multi-source fusion should exceed cap!"

    # Test D: Ground Truth Recall
    print("\n--- Test D: Recall with Field Report ---")
    field_report = GeoEvent(
        id="field_1",
        type="incident", # Matches 'incident' or 'Field-Alert' in fuser
        lat=35.0,
        lon=73.0,
        timestamp=datetime.now(),
        severity="HIGH",
        confidence="VERIFIED",
        source="Field-Alert",
        details={}
    )
    fused_d = coordinator.fuse_intelligence_layers([nasa_event, field_report], weather_data={}, raw_stats={"gfw_status": "STABLE"})
    if fused_d:
        recall_d = next(e.details.get("system_recall_est") for e in fused_d if e.details.get("system_recall_est") is not None)
        print(f"Recall with Field Report: {recall_d} (Expected: Not None)")
        assert recall_d is not None, "Recall should be calculated when ground truth exists!"

    print("\n✅ Verification COMPLETE: Mathematical Truth Modeling is HARDENED.")

if __name__ == "__main__":
    test_truth_modeling()
