"""
GL_AI - Hybrid Retrieval Query Tester
======================================
Tests multiple query types across the Vector + Graph + Expert pipeline.

USAGE:
  python scripts/test_queries.py                    # Run all preset queries
  python scripts/test_queries.py "your question"    # Run a single custom query
  python scripts/test_queries.py --interactive       # Interactive mode (keep asking)
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from retrieval.graph_rag_retriever import GraphRAGRetriever


# ── Preset Test Queries (covering different retrieval paths) ──────────────

TEST_QUERIES = [
    # 1. Species-specific penalty with location (tests Entity Extraction + Graph traversal)
    "What are the penalties for cutting Deodar trees in Khyber Pakhtunkhwa?",
    
    # 2. Legal definition with jurisdiction (tests Vector + Entity disambiguation)
    "According to Pakistan Forest Law, what is the legal definition of timber?",
    
    # 3. Authority hierarchy with specific action (tests Expert Overlay + Graph depth)
    "Who has the authority to confiscate timber vehicles under Section 42?",
    
    # 4. Cross-referencing sections (tests Graph relationships + Vector)
    "How does Section 33 of the Forest Act relate to Section 26 on penalties?",
    
    # 5. Species protection status with geographic qualifier (tests Expert + Graph)
    "Is Chir pine a protected species in Punjab province according to current laws?",
    
    # 6. Procedural authority with conditions (tests Graph traversal with conditions)
    "Under what conditions can a Range Forest Officer arrest without warrant?",
    
    # 7. Fee calculation for specific timber type (tests Expert numeric extraction)
    "What is the current seigniorage fee rate for Blue Pine timber per cubic foot?",
    
    # 8. Temporal comparison with specific amendments (tests Expert + Historical)
    "What amendments were made to forest penalties from the 1927 Act to the 2022 Act?",
    
    # 9. Specific offence with livestock type (tests Expert + Vector precision)
    "What is the penalty for grazing buffalo and cows in a notified reserved forest?",
    
    # 10. Officer powers with jurisdictional limit (tests Vector + Graph authority)
    "What are the boundary survey powers of the Forest Settlement Officer under Chapter II?",
]


def print_separator(char="=", width=70):
    print(char * width)


def classify_source(result: dict) -> str:
    """Determine where this result came from."""
    chunk_id = result.get("chunk_id", "")
    scores = result.get("scores", {})
    
    if chunk_id.startswith("eko_"):
        return "EXPERT"
    
    v = scores.get("vector", 0)
    g = scores.get("graph", 0)
    
    if v > 0 and g > 0:
        return "HYBRID (V+G)"
    elif v > 0:
        return "VECTOR"
    elif g > 0:
        return "GRAPH"
    else:
        return "UNKNOWN"


async def run_single_query(retriever: GraphRAGRetriever, query: str, query_num: int = 0):
    """Run one query and display detailed results."""
    print()
    print_separator("=")
    if query_num:
        print(f"  QUERY #{query_num}")
    print(f"  Q: {query}")
    print_separator("=")
    
    # Show extracted entities
    entities = await retriever.extract_entities_from_query(query)
    print(f"  Extracted Entities: {entities if entities else '(none)'}")
    print_separator("-")
    
    # Run hybrid search
    start = time.time()
    results = await retriever.hybrid_search(query, k=5)
    elapsed = time.time() - start
    
    if not results:
        print("  [NO RESULTS] The retriever returned zero chunks.")
        return
    
    # Categorize results
    source_counts = {"EXPERT": 0, "VECTOR": 0, "GRAPH": 0, "HYBRID (V+G)": 0, "UNKNOWN": 0}
    
    print(f"\n  Found {len(results)} results in {elapsed:.2f}s\n")
    
    for i, res in enumerate(results):
        source = classify_source(res)
        source_counts[source] = source_counts.get(source, 0) + 1
        scores = res.get("scores", {})
        meta = res.get("metadata", {})
        text = res.get("text", "")[:120]
        
        print(f"  [{i+1}] SOURCE: {source}")
        print(f"      Law:     {meta.get('law_title', 'N/A')}")
        print(f"      Section: {meta.get('section', 'N/A')}")
        print(f"      Scores:  V={scores.get('vector', 0):.3f}  G={scores.get('graph', 0):.3f}  "
              f"O={scores.get('overlap', 0):.3f}  Final={scores.get('weighted', 0):.3f}")
        print(f"      Text:    {text}...")
        print()
    
    # Summary bar
    active = {k: v for k, v in source_counts.items() if v > 0}
    summary = " | ".join(f"{k}: {v}" for k, v in active.items())
    print(f"  >> Source Breakdown: {summary}")
    print_separator("-")


async def run_all_queries(retriever: GraphRAGRetriever):
    """Run all preset queries sequentially."""
    print()
    print_separator("#")
    print("  GL_AI HYBRID RETRIEVAL - MULTI-QUERY TEST")
    print(f"  Running {len(TEST_QUERIES)} preset queries...")
    print_separator("#")
    
    for i, query in enumerate(TEST_QUERIES, 1):
        await run_single_query(retriever, query, query_num=i)
    
    print()
    print_separator("#")
    print("  ALL QUERIES COMPLETE")
    print_separator("#")


async def interactive_mode(retriever: GraphRAGRetriever):
    """Keep prompting for queries until user types 'exit'."""
    print()
    print_separator("#")
    print("  GL_AI HYBRID RETRIEVAL - INTERACTIVE MODE")
    print("  Type your query and press Enter. Type 'exit' to quit.")
    print_separator("#")
    
    while True:
        print()
        try:
            query = input("  Your Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not query or query.lower() in ("exit", "quit", "q"):
            print("  Exiting interactive mode.")
            break
        
        await run_single_query(retriever, query)


async def main():
    # Initialize retriever (one-time cost)
    print("Initializing GraphRAG Retriever...")
    retriever = GraphRAGRetriever(
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "password")
    )
    
    # Determine mode from command-line args
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--interactive":
            await interactive_mode(retriever)
        else:
            # Single custom query
            custom_query = " ".join(sys.argv[1:])
            await run_single_query(retriever, custom_query)
    else:
        # Default: run all preset queries
        await run_all_queries(retriever)


if __name__ == "__main__":
    asyncio.run(main())
