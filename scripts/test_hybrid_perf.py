"""
test_hybrid_perf.py
===================
Runs specialized query benchmarks to compare Vector vs. Graph vs. Hybrid retrieval.
It displays retrieval latencies, chunk scores, and overlap ratios.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root and src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
load_dotenv(dotenv_path="E:/GL_AI/.env")

from retrieval.graph_rag_retriever import GraphRAGRetriever

HYBRID_PERF_QUERIES = [
    "Can a forest officer compound offences under Section 68?",
    "What is the legal status of Guzara forests under KPK Ordinance?",
    "Is it illegal to clear forest land for cultivation in a reserved forest?",
    "What are the transit rules for firewood and charcoal?"
]

async def benchmark_queries():
    print("=" * 80)
    print("      HYBRID RETRIEVAL BENCHMARK: VECTOR VS. GRAPH VS. HYBRID")
    print("=" * 80)
    
    # Initialize retriever
    retriever = GraphRAGRetriever(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        neo4j_user=os.getenv("NEO4J_USERNAME", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password")
    )
    
    for q_idx, query in enumerate(HYBRID_PERF_QUERIES, 1):
        print(f"\n[BENCHMARK #{q_idx}] QUERY: \"{query}\"")
        print("-" * 80)
        
        # 1. Entity Extraction
        entities = await retriever.extract_entities_from_query(query)
        print(f"Extracted Entities: {entities}")
        
        # 2. Pure Vector Search Benchmark
        start_v = time.time()
        vector_results = await retriever.vector_search(query, k=5)
        elapsed_v = time.time() - start_v
        
        # 3. Pure Graph Search Benchmark
        start_g = time.time()
        graph_results = await retriever.graph_search(entities, k=5)
        elapsed_g = time.time() - start_g
        
        # 4. Hybrid Search Benchmark
        start_h = time.time()
        hybrid_results = await retriever.hybrid_search(query, k=5)
        elapsed_h = time.time() - start_h
        
        # 5. Output Comparison
        print(f"\nPerformance / Latency Breakdown:")
        print(f"  * Vector-Only Search : {elapsed_v*1000:.2f} ms (Found {len(vector_results)} chunks)")
        print(f"  * Graph-Only Search  : {elapsed_g*1000:.2f} ms (Found {len(graph_results)} chunks)")
        print(f"  * Hybrid Search      : {elapsed_h*1000:.2f} ms (Combined & Merged to {len(hybrid_results)} chunks)")
        
        # 6. Show top merged chunks & verify if they have vector + graph scores (Hybrid overlaps)
        print(f"\nTop 3 Retained Results:")
        for idx, res in enumerate(hybrid_results[:3], 1):
            chunk_id = res.get("chunk_id", "")
            scores = res.get("scores", {})
            v_score = scores.get("vector", 0.0)
            g_score = scores.get("graph", 0.0)
            final_score = scores.get("weighted", 0.0)
            
            # Determine source label
            source = "EXPERT"
            if not chunk_id.startswith("eko_"):
                if v_score > 0 and g_score > 0:
                    source = "HYBRID (V+G)"
                elif v_score > 0:
                    source = "VECTOR"
                else:
                    source = "GRAPH"
            
            meta = res.get("metadata", {})
            text = res.get("text", "")[:100].replace("\n", " ")
            print(f"  {idx}. [{source}] ID: {chunk_id}")
            print(f"     Text: \"{text}...\"")
            print(f"     Scores -> Vector: {v_score:.3f} | Graph: {g_score:.3f} | Weighted Final: {final_score:.3f}")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(benchmark_queries())
