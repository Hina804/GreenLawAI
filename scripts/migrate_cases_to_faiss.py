import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from data_pipeline.indexing.faiss_store import FAISSStore
from data_pipeline.indexing.embedding_generator import EmbeddingGenerator

def migrate():
    print("--- Phase 4, Week 1: Judiciary Vector Migration ---")
    
    # Paths
    source_json = "data/court_cases/processed/mock_cases.json"
    target_index = "faiss_index_cases"
    
    if not os.path.exists(source_json):
        print(f"ERROR: Source {source_json} missing.")
        return

    # 1. Initialize Tools
    embedder = EmbeddingGenerator()
    store = FAISSStore(persist_directory=target_index, collection_name="court_cases")
    
    # 2. Load Data
    with open(source_json, "r") as f:
        cases = json.load(f)
    print(f"Loaded {len(cases)} cases for migration.")
    
    # 3. Process & Index
    texts = [c.get("text", "") or c.get("offense_details", "") for c in cases]
    metadatas = cases
    
    embeddings = embedder.encode(texts)
    store.add_documents(embeddings, metadatas)
    
    print(f"SUCCESS: Migrated {len(cases)} cases to {target_index}")
    print(f"Total Vectors in Store: {store.index.ntotal}")

if __name__ == "__main__":
    migrate()

