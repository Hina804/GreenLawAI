import sys
import os
import asyncio
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fusion.FusionEngine import FusionEngine
from core.schemas import CanonicalAgentResponse, AudienceType, Citation

async def test_consensus_logic():
    print("Testing Multi-Agent Consensus Enforcement (Phase 3 Week 4)...")
    
    fusion = FusionEngine()
    await fusion.load({})
    
    # 1. Simulate Legal Agent proposing a penalty for Deodar
    legal_resp = CanonicalAgentResponse(
        simple_explanation="Penalty for cutting Deodar trees.",
        legal_explanation="Under Forest Act 1927...",
        citations=[Citation(document="Forest Act", section="25(a)")],
        agent_name="Judiciary",
        confidence=0.9,
        graph_metadata={"penalty_details": {"species_involved": "Deodar"}}
    )
    
    # 2. Case A: AGREEMENT (Climate also reports Deodar)
    climate_resp_ok = CanonicalAgentResponse(
        simple_explanation="Deodar forest density is high.",
        legal_explanation="Scientific data matches region.",
        citations=[Citation(document="FAO", section="1.2")],
        agent_name="Climate",
        confidence=0.85,
        graph_metadata={"metrics": {"species": "Deodar"}}
    )
    
    verdict_ok = fusion.reconcile([legal_resp, climate_resp_ok])
    print(f"\nScenario A (Alignment): {verdict_ok.consensus_status}")
    print(f"Trust Score: {verdict_ok.trust_score}")
    assert verdict_ok.consensus_status == "agreement"
    
    # 3. Case B: CONFLICT (Monitoring sees NO activity)
    monitoring_resp_fail = CanonicalAgentResponse(
        simple_explanation="No activity detected via FIRMS/GFW.",
        legal_explanation="Remote sensing is clear.",
        citations=[Citation(document="GFW", section="Live")],
        agent_name="Monitoring",
        confidence=0.95,
        graph_metadata={"activity_detected": False}
    )
    
    verdict_fail = fusion.reconcile([legal_resp, monitoring_resp_fail])
    print(f"\nScenario B (Activity Conflict): {verdict_fail.consensus_status}")
    print(f"Conflicts: {verdict_fail.conflicts}")
    print(f"Trust Score: {verdict_fail.trust_score} (Should be penalized)")
    
    assert verdict_fail.consensus_status == "conflict"
    assert any("Active Threat Mismatch" in c for c in verdict_fail.conflicts)
    assert verdict_fail.trust_score < 0.6  # Penalized from 0.9 avg

    print("\n✅ CONSENSUS VERIFICATION SUCCESSFUL")

if __name__ == "__main__":
    asyncio.run(test_consensus_logic())
