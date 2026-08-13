
import sys
import os
import yaml
from pathlib import Path

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
sys.path.append(src_path)
print(f"Added to path: {src_path}")

from retrieval.graph_rag_retriever import GraphRAGRetriever
from indexing.embedding_generator import EmbeddingGenerator

def test_eko_fines():
    print("\n🌲 Testing EKO Fine Injection...")
    
    # Initialize
    config_path = os.path.join(current_dir, "config", "rag_config.yaml")
    if not os.path.exists(config_path):
        # Fallback for some envs
        config_path = os.path.join(current_dir, "src", "config", "config.yaml")

    with open(config_path) as f:
        config = yaml.safe_load(f)
    # embed_service = EmbeddingGenerator() # Not needed for Retriever init
    retriever = GraphRAGRetriever(
        neo4j_uri=config['neo4j']['uri'],
        neo4j_user=config['neo4j']['user'],
        neo4j_password=config['neo4j']['password'],
        chroma_persist_dir=config.get('chroma', {}).get('persist_dir', "./chroma_db"),
        # embed_service=embed_service # REMOVED
    )
    
    # Test Query
    query = "What are the new fines for deforestation?"
    print(f"Query: '{query}'")
    
    # Check Entity Extraction
    entities = retriever.extract_entities_from_query(query)
    print(f"Extracted Entities: {entities}")
    
    if "fines" in entities or "penalties" in entities:
        print("✅ Success: 'fines'/'penalties' detected as entity.")
    else:
        print("❌ Failure: Keywords not detected.")
        
    # Check Retrieval
    results = retriever.hybrid_search(query)
    
    # Verify EKO content is in results
    eko_found = False
    for res in results:
        if "Schedule-III" in res['text'] and "2022 Amendment" in res['text']:
            print("✅ Success: EKO Content found in retrieval results.")
            print(f"   Content: {res['text'][:100]}...")
            eko_found = True
            break
            
    if not eko_found:
        print("❌ Failure: EKO content NOT found in top results.")

if __name__ == "__main__":
    test_eko_fines()
