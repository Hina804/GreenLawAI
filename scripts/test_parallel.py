
import asyncio
import yaml
import time
from agents.coordinator import AgentCoordinator
from loguru import logger

async def test_parallel_dispatch():
    # Load config
    with open("config/rag_config.yaml") as f:
        config = yaml.safe_load(f)
    
    coordinator = AgentCoordinator(config)
    
    # Query that triggers both Legal and Climate
    query = "What are the legal protections for Deodar trees and how much carbon do they sequester?"
    
    logger.info(f"Testing parallel dispatch for query: {query}")
    
    start_time = time.time()
    result = await coordinator.run(query, thread_id="test_parallel_123")
    end_time = time.time()
    
    print("\n--- COORDINATOR RESULT ---")
    print(f"Total Time: {end_time - start_time:.2f}s")
    print(f"Primary Intent: {result['intent_data']['primary_intent']}")
    print(f"Possible Intents: {result['intent_data']['possible_intents']}")
    print(f"Next Nodes Triggered: {result['next_nodes']}")
    
    print("\nAgents Responded:")
    for agent, output in result.get('agent_outputs', {}).items():
        print(f" - {agent}: {len(output.get('response', ''))} chars")
    
    print("\nFinal Synthesized Response Snippet:")
    print(result['response'][:200] + "...")
    print("--------------------------\n")

    # Cleanup
    await coordinator.close()

if __name__ == "__main__":
    asyncio.run(test_parallel_dispatch())
