
import os
import sys
from pathlib import Path

# CRITICAL: Set environment variables
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from retrieval.graph_rag_retriever import GraphRAGRetriever

def verify():
    print("\n🔍 VERIFYING SYSTEM RESTORATION...")
    
    retriever = GraphRAGRetriever()
    
    test_queries = [
        "Can a Forest Officer arrest me without a warrant?",
        "Is Cheerh a reserved specie?",
        "What are the seigniorage fees for Biar trees?",
        "Tell me about Pinus Roxburghii."
    ]
    
    for query in test_queries:
        print(f"\n--- Testing Query: '{query}' ---")
        
        # 1. Test Retrieval (Full Pipeline)
        results = retriever.hybrid_search(query, k=3)
        print(f"✅ Retrieved: {len(results)} chunks")
        
        for i, res in enumerate(results):
            score = res.get('final_score', 0)
            law = res.get('metadata', {}).get('law_title', 'Unknown')
            section = res.get('metadata', {}).get('section', 'N/A')
            print(f"   [{i+1}] Final Score: {score:.3f} | Law: {law} | Section: {section}")
            print(f"       Snippet: {res['text'][:100]}...")

if __name__ == "__main__":
    verify()
