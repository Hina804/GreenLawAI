import os
import sys
import numpy as np
import faiss

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from data_pipeline.indexing.embedding_generator import EmbeddingGenerator
from data_pipeline.indexing.faiss_store import FAISSStore

def test_existing_index():
    index_path = "e:/GL_AI/faiss_index_cases"
    if not os.path.exists(index_path):
        print("Index path not found.")
        return
        
    embedder = EmbeddingGenerator()
    store = FAISSStore(persist_directory=index_path, collection_name="court_cases")
    
    query = "Illegal logging of Himalayan Deodar at night in a reserved forest area"
    query_vec = embedder.encode_single(query)
    
    print(f"\nSearching index at: {index_path}")
    results = store.search(query_vec, k=5)
    
    print(f"Found {len(results)} results.")
    for r in results:
        print(f"  - ID: {r['metadata'].get('case_id')} | Similarity: {r['score']:.4f}")
        # print(f"    Text: {r['text'][:100]}...")

if __name__ == "__main__":
    test_existing_index()
