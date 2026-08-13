
import sys
import os
from pathlib import Path
import numpy as np

# Add src to path
src_path = Path("e:/GL_AI/src")
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "data_pipeline"))

from preprocessing_pipeline.phase_6_graph_construction import EmbeddingGenerator, FAISSIndexer

def spot_check():
    print("=== GreenLawAI FAISS Index Spot-Check ===")
    
    # 1. Initialize Components
    print("Initializing Embedding Generator...")
    embedder = EmbeddingGenerator()
    
    print("Initializing FAISS Index Manager...")
    indexer = FAISSIndexer()
    
    # 2. Load Index
    index_path = "e:/GL_AI/data_processed/faiss_index_new"
    print(f"Loading index from: {index_path}")
    
    try:
        # We need to manually load the index file and the registry
        # The FAISSIndexManager usually has a load method
        if hasattr(indexer, 'load_index'):
            indexer.load_index(index_path)
        else:
            # Fallback if load_index is not there (check file again)
            import faiss
            import pickle
            
            indexer.index = faiss.read_index(str(Path(index_path) / "index.faiss"))
            with open(Path(index_path) / "chunk_registry.pkl", "rb") as f:
                indexer.chunk_registry = pickle.load(f)
            print("Index loaded manually.")
            
        print(f"Index loaded. Total vectors: {indexer.index.ntotal}")
        
    except Exception as e:
        print(f"Failed to load index: {e}")
        return

    # 3. Define Queries
    queries = [
        "What are the rules for police recruitment in NWFP 1937?",
        "Fire safety provisions for building construction",
        "Management rules for Guzara forests in Khyber Pakhtunkhwa"
    ]
    
    # 4. Run Searches
    for query in queries:
        print(f"\n--- Query: {query} ---")
        
        # Generate embedding for query
        # MultilingualEmbeddingModel.generate_embedding(text, metadata)
        query_vec = embedder.embedding_model.generate_embedding(query, {})
        
        if query_vec is None:
            print("Failed to generate query embedding.")
            continue
            
        # Search index
        # index.search(vecs, k)
        vecs = np.array([query_vec]).astype('float32')
        D, I = indexer.index.search(vecs, 3) # Top 3
        
        # Print Results
        for i, (dist, idx) in enumerate(zip(D[0], I[0])):
            if idx == -1:
                print(f" {i+1}. No match")
                continue
                
            chunk = indexer.chunk_registry.get(idx)
            if chunk:
                print(f" {i+1}. [Score: {dist:.4f}] Doc: {chunk.metadata.get('file_name', 'Unknown')}")
                text_snippet = chunk.text[:200].replace('\n', ' ')
                print(f"    Snippet: {text_snippet}...")
            else:
                print(f" {i+1}. [Score: {dist:.4f}] Chunk metadata missing for ID {idx}")

if __name__ == "__main__":
    spot_check()
