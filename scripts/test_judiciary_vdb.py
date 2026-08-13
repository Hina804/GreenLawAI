import asyncio
import os
import sys
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent
from core.schemas import AudienceType
from loguru import logger

async def test_agent():
    logger.info("Starting Judiciary Vector DB Verification...")
    
    # 1. Initialize Agent
    agent = CaseRetrievalAgent()
    
    # 2. Test Query
    query = "What is the penalty for illegal logging in a protected forest at night?"
    
    # 3. Execution
    response = await agent.run(
        query=query,
        retrieved_chunks=[],
        audience=AudienceType.FIELD_RANGER
    )
    
    print("\n--- AGENT RESPONSE START ---")
    print(response.response)
    print("--- AGENT RESPONSE END ---\n")
    
    if "SCALED RETRIEVAL" in response.response:
        logger.success("Verification PASSED: Agent is using the Vector Index.")
    else:
        logger.error("Verification FAILED: Agent returned incorrect format.")

if __name__ == "__main__":
    asyncio.run(test_agent())
