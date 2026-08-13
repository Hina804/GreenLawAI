import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent
from core.schemas import AudienceType

async def verify_retrieval():
    config = {
        "faiss_index_path": "e:/GL_AI/faiss_index_cases"
    }
    
    agent = CaseRetrievalAgent(config=config)
    
    test_queries = [
        "What was the verdict in the Timber Smuggling case of Akram Khan?",
        "Tell me about corporate logging penalties in Peshawar.",
        "Was Malik Safdar found guilty for firewood collection?"
    ]
    
    print("--- Judiciary Retrieval Accuracy Check ---")
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        # CaseRetrievalAgent.run expects (query, retrieved_chunks, audience, context)
        # Note: In the final pipeline, retrieved_chunks might be passed by the coordinator,
        # but the agent itself also does _vector_retrieve(query).
        response = await agent.run(query=query, retrieved_chunks=[], audience=AudienceType.PROFESSIONAL)
        
        print(f"Top Case IDs: {response.source_nodes}")
        print(f"Confidence: {response.confidence}")
        # print(f"Snippet: {response.response[:200]}...")
        
        # Simple verification: matches should contain specific IDs
        if "KPK-2023-001" in str(response.source_nodes) and "Akram Khan" in query:
             print(">> SUCCESS: Correct case found.")
        elif "KPK-2024-012" in str(response.source_nodes) and "ABC Logging" in query:
             print(">> SUCCESS: Correct corporate case found.")
        elif "KPK-2022-088" in str(response.source_nodes) and "Malik Safdar" in query:
             print(">> SUCCESS: Correct acquittal case found.")

if __name__ == "__main__":
    asyncio.run(verify_retrieval())
