import asyncio
import sys
from pathlib import Path
import yaml

# Add src to path
src_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(src_path))

from agents.coordinator import AgentCoordinator

def load_config():
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "rag_config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

async def test_memory():
    config = load_config()
    coordinator = AgentCoordinator(config)
    
    thread_id = "test_user_123"
    
    print(f"--- Turn 1: Setting Context ---")
    q1 = "What are the logging trends in Hazara?"
    res1 = await coordinator.run(q1, thread_id=thread_id)
    print(f"Res 1: {res1['response']}")
    print(f"Stored Entities: {res1['intent_data'].get('entities', {}).get('locations')}")
    
    print(f"\n--- Turn 2: Follow-up (Implicit context) ---")
    q2 = "Is there an anomaly there?"
    # The 'there' should refer to 'Hazara' stored in intent_data
    res2 = await coordinator.run(q2, thread_id=thread_id)
    print(f"Res 2: {res2['response']}")
    # If successful, res2 should mention Hazara despite it not being in q2
    
if __name__ == "__main__":
    asyncio.run(test_memory())
