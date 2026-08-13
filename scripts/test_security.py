
import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from agents.coordinator import AgentCoordinator

async def test_rate_limiting():
    print("Testing Operational Hardening: Rate Limiting...")
    
    # 1. Initialize Coordinator
    config = {
        "neo4j": {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "password"},
        "llm": {"provider": "mock", "model": "gpt-4"} 
    }
    
    # Mocking necessary components to avoid heavy initialization
    coordinator = AgentCoordinator(config, db_path="e:/GL_AI/data/test_security.db")
    
    # 2. Simulate rapid fire requests (above the 10 RPM limit)
    print("Sending 12 rapid-fire requests (Limit is 10 RPM)...")
    results = []
    for i in range(12):
        print(f"Request {i+1}...")
        result = await coordinator.run(f"Hello request {i}", thread_id="test_user")
        results.append(result)
        
    # 3. Analyze Results
    allowed = [r for r in results if "error" not in r]
    denied = [r for r in results if "error" in r]
    
    print(f"\nResults Analysis:")
    print(f" - Total Requests: {len(results)}")
    print(f" - Allowed: {len(allowed)}")
    print(f" - Denied (Rate Limited): {len(denied)}")
    
    if len(denied) >= 2:
        print("\n✅ Rate limiting successfully triggered!")
    else:
        print("\n❌ Rate limiting failed to trigger correctly.")

    # Cleanup
    import os
    if os.path.exists("e:/GL_AI/data/test_security.db"):
        os.remove("e:/GL_AI/data/test_security.db")
    print("✅ Test cleanup complete.")

if __name__ == "__main__":
    asyncio.run(test_rate_limiting())
