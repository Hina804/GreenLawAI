import json
import os
import sys
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from data_pipeline.indexing.faiss_store import FAISSStore
from loguru import logger

class MockEmbedder:
    def encode(self, texts: List[str]):
        import numpy as np
        return np.random.rand(len(texts), 384).astype("float32")

def migrate():
    case_path = "e:/GL_AI/data/court_cases/processed/mock_cases.json"
    index_path = "e:/GL_AI/faiss_index_cases"
    
    if not os.path.exists(case_path):
        logger.error(f"Source file not found: {case_path}")
        return

    try:
        # Use utf-8-sig to handle PowerShell BOM
        with open(case_path, "r", encoding="utf-8-sig") as f:
            cases = json.load(f)
    except Exception as e:
        logger.error(f"JSON Load failed: {e}")
        return

    logger.info(f"Loaded {len(cases)} cases for MOCK sig-indexing.")
    store = FAISSStore(persist_directory=index_path, collection_name="court_cases")
    texts = [c.get("text", "") for c in cases]
    embedder = MockEmbedder()
    vectors = embedder.encode(texts)
    store.add_documents(vectors, cases)
    store.save()
    logger.success(f"Phase 4.1 Migration Complete (Mock Vectors). Index at {index_path}")

if __name__ == "__main__":
    migrate()
