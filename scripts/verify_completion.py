import os
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv

def verify():
    load_dotenv()
    
    print("=" * 60)
    print("FINAL INTEGRATION AUDIT")
    print("=" * 60)
    
    # 1. Check Neo4j
    print("\n[1/3] Auditing Neo4j Knowledge Graph...")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    doc_count = 0
    total_chunks = 0
    linked_chunks = 0
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Document Count via property
            res = session.run("MATCH (n) WHERE n.document_id IS NOT NULL RETURN count(DISTINCT n.document_id) as count, collect(DISTINCT n.document_id) as ids")
            record = res.single()
            doc_count = record["count"]
            doc_ids = sorted(record["ids"])
            
            # Chunk Count and Connectivity
            res_chunks = session.run("""
                MATCH (c:Chunk) 
                OPTIONAL MATCH (c)-[r:PART_OF_HIERARCHY]->(s)
                RETURN count(c) as total_chunks, count(r) as linked_chunks
            """)
            chunk_record = res_chunks.single()
            total_chunks = chunk_record["total_chunks"]
            linked_chunks = chunk_record["linked_chunks"]
            
            print(f"  - Unique Document IDs found: {doc_count}")
            print(f"  - Total Chunk Nodes: {total_chunks}")
            print(f"  - Linked Chunks: {linked_chunks}")
            if total_chunks > 0:
                print(f"  - Connectivity: {(linked_chunks/total_chunks)*100:.1f}%")
            
            print("\n  In-Graph Document IDs:")
            for did in doc_ids:
                print(f"    - {did}")
                
        driver.close()
    except Exception as e:
        print(f"  [ERROR] Neo4j Audit failed: {e}")

    # 2. Check chunks_export.json (FAISS Source)
    print("\n[2/3] Auditing Export Registry (FAISS Synchronization)...")
    export_path = "chunks_export.json"
        
    if os.path.exists(export_path):
        try:
            with open(export_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                export_docs = set()
                if isinstance(data, list):
                    export_docs = set(c.get('document_id') for c in data if isinstance(c, dict))
                    print(f"  - Chunks in export file: {len(data)}")
                elif isinstance(data, dict):
                    # If it's a dict, maybe the chunks are in a key like 'chunks'
                    chunks = data.get('chunks', [])
                    if not chunks and data: # fallback if it's a dict of chunks
                        chunks = list(data.values())
                    
                    if chunks and isinstance(chunks[0], dict):
                        export_docs = set(c.get('document_id') for c in chunks if isinstance(c, dict))
                        print(f"  - Chunks detected in export: {len(chunks)}")
                    else:
                        print(f"  - Dict structure unknown. Keys: {list(data.keys())[:5]}")
                
                if export_docs:
                    print(f"  - Unique Document IDs in export: {len(export_docs)}")
                    print("\n  Exported Document IDs:")
                    for edid in sorted(export_docs):
                        print(f"    - {edid}")
                else:
                    print("  - No Document IDs found in export.")
                    
        except Exception as e:
            print(f"  [ERROR] Export Audit failed: {e}")
    else:
        print(f"  [WARNING] chunks_export.json not found at {export_path}")

    # 3. Final Verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    if doc_count == 19:
        print("  - [PASS] All 19 Gold Standard documents are in Neo4j.")
    else:
        print(f"  - [FAIL] Expected 19 documents, found {doc_count}.")
        
    if total_chunks > 0 and linked_chunks == total_chunks:
        print("  - [PASS] 100% Graph Connectivity achieved.")
    else:
        print("  - [FAIL] Incomplete connectivity detected.")
    print("=" * 60)

if __name__ == "__main__":
    verify()
