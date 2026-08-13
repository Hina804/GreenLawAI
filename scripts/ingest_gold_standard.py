import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from indexing.vector_indexer import VectorIndexer

def main():
    # Configuration
    ROOT = Path(__file__).parent.parent
    DOCS_DIR = ROOT / "data_processed" / "documents"
    PERSIST_DIR = ROOT / "faiss_index"
    
    print("="*60)
    print("GOLD STANDARD INGESTION - FAISS")
    print("="*60)
    
    # Initialize indexer
    indexer = VectorIndexer(
        persist_dir=str(PERSIST_DIR),
        collection_name="legal_docs",
        max_chunk_size=512,
        device="cpu",
        enable_entities=True
    )
    
    # Identify the 19 Gold Standard documents from manifest
    manifest_path = ROOT / "data_processed" / "batch_manifest.json"
    doc_paths = []
    
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            manifest_docs = manifest.get("documents", {})
            print(f"Manifest contains {len(manifest_docs)} documents.")
            
            for doc_id in manifest_docs:
                doc_dir = DOCS_DIR / doc_id
                rules_path = doc_dir / "phase_4" / "phase_4_4_1_rules.json"
                if rules_path.exists():
                    doc_paths.append(rules_path)
                else:
                    print(f"[!] Warning: Missing phase_4_4_1_rules.json in {doc_id}")
    else:
        print("[FAIL] batch_manifest.json not found!")
        return
    
    print(f"Found {len(doc_paths)} valid documents for ingestion.")
    
    # Index documents
    all_stats = []
    for path in doc_paths:
        try:
            stats = indexer.index_document(str(path))
            all_stats.append(stats)
        except Exception as e:
            print(f"[FAIL] Error indexing {path.name}: {e}")
            
    # Print summary
    print(f"\n{'='*60}")
    print(f"INGESTION SUMMARY")
    print(f"{'='*60}")
    
    for stat in all_stats:
        print(f"  {stat.get('law_title', 'Unknown')}: {stat.get('total_chunks', 0)} chunks")
        
    # Export for Neo4j
    print(f"\n{'='*60}")
    print(f"EXPORTING FOR NEO4J")
    print(f"{'='*60}")
    indexer.export_entity_registry(str(ROOT / "entity_registry.json"))
    indexer.export_chunks_for_neo4j(str(ROOT / "chunks_export.json"))
    print(f"[OK] Exported registry and chunks for Neo4j import.")
    
    print(f"\n[OK] Ingestion complete. {len(all_stats)} documents indexed into FAISS.")

if __name__ == "__main__":
    main()
