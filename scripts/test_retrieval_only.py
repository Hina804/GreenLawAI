
import os
import sys
import yaml
from pathlib import Path

# CRITICAL: Set environment variables BEFORE any other imports to prevent hangs
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
sys.path.insert(0, src_path)

from retrieval.graph_rag_retriever import GraphRAGRetriever

def test_retrieval():
    print("\n🔍 TESTING RETRIEVAL ONLY...")
    
    # Load config
    config_path = os.path.join(current_dir, "config", "rag_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Initialize Retriever
    try:
        retriever = GraphRAGRetriever(
            neo4j_uri=config['neo4j']['uri'],
            neo4j_user=config['neo4j']['user'],
            neo4j_password=config['neo4j']['password'],
            chroma_persist_dir=config.get('chromadb', {}).get('persist_directory', './chroma_db_v3')
        )
    except Exception as e:
        print(f"❌ Failed to initialize retriever: {e}")
        return

    # Query
    query = "Can a Forest Officer arrest me without a warrant?"
    print(f"\nQuery: '{query}'")
    
    # Extract Entities
    entities = retriever.extract_entities_from_query(query)
    print(f"Extracted Entities: {entities}")

    # Hybrid Search
    results = retriever.hybrid_search(query, k=5)
    print(f"\n📥 Retrieved {len(results)} chunks.")
    
    for i, res in enumerate(results):
        print(f"\n--- Result {i+1} [Score: {res.get('final_score', 0):.3f}] ---")
        print(f"Source: {res['metadata'].get('law_title')} - {res['metadata'].get('section')}")
        print(f"Text Snippet: {res['text'][:300]}...")
        if "eko_" in str(res.get('chunk_id')):
            print("✅ THIS IS AN EKO CHUNK")

if __name__ == "__main__":
    test_retrieval()
