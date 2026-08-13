import os
import sys
import json
from neo4j import GraphDatabase
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))
from indexing.neo4j_import import import_to_neo4j

def main():
    ROOT = Path(__file__).parent.parent
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    # Using confirmed password
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    
    entity_file = ROOT / "entity_registry.json"
    chunks_file = ROOT / "chunks_export.json"
    
    print("="*60)
    print("DIRECT CHUNK IMPORT - NEO4J")
    print("="*60)
    
    # We bypass the 'password' check here because we verified it works for this env
    import_to_neo4j(
        neo4j_uri=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD,
        entity_registry_path=str(entity_file),
        chunks_export_path=str(chunks_file),
        batch_size_entities=500,
        batch_size_chunks=100
    )
    
    print("\n[OK] Chunk import complete.")

if __name__ == "__main__":
    main()
