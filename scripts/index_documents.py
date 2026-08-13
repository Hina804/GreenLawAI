"""
Batch Indexing Script
Index all structured JSONs in the forestry directory.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from indexing.vector_indexer import VectorIndexer


def main(input_dir: str = "./data_processed/forestry/structured", persist_dir: str = "./chroma_db_v3"):
    """Run batch indexing on all forestry documents."""
    
    # Initialize indexer
    indexer = VectorIndexer(
        chroma_persist_dir=persist_dir,
        collection_name="legal_docs",
        max_chunk_size=512,
        device="cpu",
        enable_entities=True  # Enable entity extraction for GraphRAG
    )
    
    # Index all documents in forestry/structured directory
    stats = indexer.index_directory(
        directory=input_dir,
        pattern="*_structured.json"
    )
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"INDEXING COMPLETE")
    print(f"{'='*60}")
    
    for stat in stats:
        print(f"\n{stat['law_title']}")
        print(f"  Sections: {stat['total_sections']}")
        print(f"  Chunks: {stat['total_chunks']}")
    
    # Export for Neo4j
    print(f"\n{'='*60}")
    print(f"EXPORTING FOR NEO4J")
    print(f"{'='*60}")
    indexer.export_entity_registry("entity_registry.json")
    indexer.export_chunks_for_neo4j("chunks_export.json")
    print("[OK] Exported entity_registry.json and chunks_export.json")

    # Get final stats
    final_stats = indexer.get_stats()
    print(f"\n{'='*60}")
    print(f"FINAL CHROMADB STATS")
    print(f"{'='*60}")
    print(f"Total documents: {final_stats['total_documents']}")
    print(f"Collection: {final_stats['collection_name']}")
    print(f"Storage: {final_stats['persist_directory']}")
    
    print(f"\n[OK] Vector store ready for querying!")


if __name__ == "__main__":
    main()
