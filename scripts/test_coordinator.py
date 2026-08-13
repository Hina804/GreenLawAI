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

async def test_coordinator():
    config = load_config()
    coordinator = AgentCoordinator(config)
    
    test_queries = [
        "What are the penalties for felling trees in Section 27?",
        "How does reforestation help in carbon sequestration?",
        "Are there any unusual logging patterns reported in the northern areas?",
        "Hi, what can you do for me?"
    ]
    
    for query in test_queries:
        print(f"\n--- Testing Query: {query} ---")
        try:
            result = await coordinator.run(query)
            print(f"Final Response: {result['response']}")
            print(f"Routing History: {result['intent_data']['primary_intent']}")
        except Exception as e:
            print(f"Error: {e}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_coordinator())
