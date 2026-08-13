
import sys
import os
import yaml
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from retrieval.graph_rag_retriever import GraphRAGRetriever
from embedding.embedding_service import EmbeddingService

def test_retrieval(query: str):
    print(f"\n🔎 Testing Retrieval for: '{query}'")
    
    # Initialize services
    config_path = Path("config/config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
        
    embed_service = EmbeddingService(config)
    retriever = GraphRAGRetriever(config, embed_service)
    
    # Run Retrieval
    results = retriever.hybrid_search(query, top_k=5)
    
    print(f"\n✅ Retrieved {len(results)} chunks:")
    for i, res in enumerate(results):
        print(f"\n--- Result {i+1} (Score: {res['score']:.4f}) ---")
        print(f"File: {res['metadata'].get('filename', 'Unknown')}")
        print(f"Content Preview: {res['text'][:300]}...")
        
        # Check if it mentions fines/penalties
        lower_text = res['text'].lower()
        if any(w in lower_text for w in ['fine', 'penalty', 'rupee', 'imprisonment']):
            print("   >>> Contains penalty keywords!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = "fines for deforestation"
    test_retrieval(query)
