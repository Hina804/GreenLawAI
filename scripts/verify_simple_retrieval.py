import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from retrieval.graph_rag_retriever import GraphRAGRetriever

async def verify_simple():
    print("="*70)
    print("      🔍 SIMPLE RETRIEVAL VERIFICATION")
    print("="*70)
    
    retriever = GraphRAGRetriever(chroma_persist_dir="faiss_index")
    
    # 1. Test Vector Search
    print("\n--- Testing Vector Search ---")
    v_results = await retriever.vector_search("penalties for Deodar", k=2)
    print(f"Vector Results: {len(v_results)}")
    for i, r in enumerate(v_results):
        print(f"  [{i+1}] {r.get('metadata', {}).get('law_title')} | ID: {r.get('chunk_id')}")

    # 2. Test Graph Search
    print("\n--- Testing Graph Search ---")
    # Using 'government' which is confirmed in entity_registry.json
    entities = ["government"]
    g_results = await retriever.graph_search(entities, k=2)
    print(f"Graph Results: {len(g_results)}")
    for i, r in enumerate(g_results):
        print(f"  [{i+1}] {r.get('metadata', {}).get('law_title')} | ID: {r.get('chunk_id')}")

    print("\n" + "="*70)
    if len(v_results) > 0 and len(g_results) > 0:
        print("✅ SUCCESS: Both Vector and Graph are yielding results!")
    else:
        print("❌ FAILURE: Missing data from one or both sources.")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(verify_simple())
