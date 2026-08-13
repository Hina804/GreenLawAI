import asyncio
import os
import sys
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from retrieval.graph_rag_retriever import GraphRAGRetriever

async def verify_hybrid():
    print("="*70)
    print("      [VERIFYING] HYBRID RETRIEVAL (VECTOR + GRAPH)")
    print("="*70)
    
    # 1. Initialize Retriever
    retriever = GraphRAGRetriever(
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "password")
    )
    
    # 2. Test Query (Something that should trigger both)
    # Penalties for Deodar (Species entity + Penalty concept)
    query = "What are the penalties for cutting Deodar trees?"
    
    print(f"\nQuery: '{query}'")
    print("-" * 30)
    
    # 3. Perform Hybrid Search
    try:
        results = await retriever.hybrid_search(query, k=5)
        
        vector_count = sum(1 for r in results if 'vector_score' in r)
        graph_count = sum(1 for r in results if 'graph_score' in r)
        expert_count = sum(1 for r in results if r.get('source') == 'expert_overlay')
        
        print(f"\nFound {len(results)} total chunks:")
        print(f"  - Vector Chunks: {vector_count}")
        print(f"  - Graph Chunks:  {graph_count}")
        print(f"  - Expert Facts:  {expert_count}")
        
        print("\n--- SAMPLE SOURCES ---")
        for i, res in enumerate(results[:5]):
            source = res.get('source', 'unknown')
            doc = res.get('metadata', {}).get('law_title', 'N/A')
            snippet = res.get('text', '')[:100]
            print(f"[{i+1}] SOURCE: {source.upper()} | DOC: {doc}")
            print(f"    Text: {snippet}...")
            
    except Exception as e:
        print(f"\n[ERROR] Retrieval Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_hybrid())
