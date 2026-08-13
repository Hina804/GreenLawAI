import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from indexing.vector_indexer import VectorIndexer

def main():
    persist_dir = "e:/GL_AI/chroma_db_v3"
    
    # Initialize indexer (this should load existing FAISS index)
    indexer = VectorIndexer(
        chroma_persist_dir=persist_dir,
        collection_name="legal_docs",
        device="cpu",
        enable_entities=True
    )
    
    print("\n[OK] VectorIndexer loaded. Regenerating exports...")
    
    # Export for Neo4j (using the new flattened logic)
    indexer.export_entity_registry("e:/GL_AI/entity_registry.json")
    indexer.export_chunks_for_neo4j("e:/GL_AI/chunks_export.json")
    
    print("[OK] Regeneration complete.")

if __name__ == "__main__":
    main()
