
import sys
import os
import yaml
from pathlib import Path

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
sys.path.append(src_path)

from retrieval.graph_rag_retriever import GraphRAGRetriever

def run_sanity_test():
    print("\n⚖️ Pillar 4: Hybrid Retrieval Sanity Audit")
    print("="*60)
    
    # Initialize
    config_path = os.path.join(current_dir, "config", "rag_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
        
    retriever = GraphRAGRetriever(
        neo4j_uri=config['neo4j']['uri'],
        neo4j_user=config['neo4j']['user'],
        neo4j_password=config['neo4j']['password'],
        chroma_persist_dir=config.get('chroma', {}).get('persist_dir', "./chroma_db_v3")
    )

    if not retriever.driver:
        print("❌ CRITICAL: Neo4j Driver not initialized. Start Neo4j first!")
        return

    test_cases = [
        {
            "query": "What are penalties under Section 26?",
            "expectation": "Graph Dominance",
            "desc": "Legal section search should heavily leverage graph mentions."
        },
        {
            "query": "Policy goal for climate adaptation",
            "expectation": "Vector Dominance",
            "desc": "General policy text should rely on vector similarity."
        },
        {
            "query": "Who enforces forest offences?",
            "expectation": "Hybrid Balance",
            "desc": "Common actors should appear in both vector and graph."
        }
    ]

    for test in test_cases:
        print(f"\n🔍 Testing: '{test['query']}'")
        print(f"🎯 Expectation: {test['expectation']} ({test['desc']})")
        
        results = retriever.hybrid_search(test['query'], k=3)
        
        if not results:
            print("   ⚠️ No results found.")
            continue
            
        for i, res in enumerate(results, 1):
            scores = res.get('scores', {})
            v_score = scores.get('vector', 0)
            g_score = scores.get('graph', 0)
            o_score = scores.get('overlap', 0)
            
            # Simple dominance detection
            dominance = "HYBRID"
            if g_score > v_score * 1.5: dominance = "GRAPH"
            if v_score > g_score * 1.5: dominance = "VECTOR"
            
            print(f"   {i}. [{dominance}] {res['metadata']['law_title']} (Sec {res['metadata']['section']})")
            print(f"      Weights -> Vector: {v_score:.3f} | Graph: {g_score:.3f} | Overlap: {o_score:.3f} | Total: {res['final_score']:.3f}")
            print(f"      Text: {res['text'][:100]}...")

if __name__ == "__main__":
    run_sanity_test()
