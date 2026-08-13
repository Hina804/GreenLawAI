"""
verify_ingested_graph.py
Run this script to verify your Neo4j and FAISS databases after manual ingestion.
"""

import os
import pickle
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to python path
sys.path.append(str(Path(__file__).parent.parent))

# Load environments
load_dotenv(dotenv_path="E:/GL_AI/.env")

def verify_neo4j():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[FAIL] Neo4j library not installed. Run: pip install neo4j")
        return

    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    username = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    print("\n" + "="*80)
    print(f"VERIFYING NEO4J GRAPH DATABASE ('{database}' at {uri})")
    print("="*80)

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        driver.verify_connectivity()
        print("[SUCCESS] Connected to Neo4j database.")
    except Exception as e:
        print(f"[FAIL] Connection to Neo4j failed: {e}")
        return

    with driver.session(database=database) as session:
        # 1. Verify Document nodes loaded
        print("\n1. Loaded Documents (showing top 10):")
        query_docs = """
        MATCH (d:Document)
        RETURN coalesce(d.title, d.node_id) AS title, d.source_doc_id AS source, d.creation_timestamp AS timestamp
        ORDER BY title
        LIMIT 10
        """
        results = session.run(query_docs)
        print(f"   {'Document Title':<55} | {'Source ID':<30}")
        print(f"   {'-'*55}-+-{'-'*30}")
        for r in results:
            print(f"   {str(r['title'])[:53]:<55} | {str(r['source'])[:28]:<30}")

        # 2. Check Species optimizations
        print("\n2. Ingested Species Optimizations (showing top 10):")
        query_species = """
        MATCH (s:Species)
        RETURN s.node_id AS id, s.common_name AS name, s.legal_status AS status, s.source_doc_id AS doc_id
        ORDER BY name
        LIMIT 10
        """
        results = session.run(query_species)
        print(f"   {'Common Name':<30} | {'Legal Status':<20} | {'Source Document':<30}")
        print(f"   {'-'*30}-+-{'-'*20}-+-{'-'*30}")
        for r in results:
            name = r['name'] or r['id']
            status = r['status'] or 'None'
            doc = r['doc_id'] or 'None'
            print(f"   {str(name)[:28]:<30} | {str(status)[:18]:<20} | {str(doc)[:28]:<30}")

        # 3. Structural counts: Node labels
        print("\n3. Structural Completeness - Node Label counts:")
        query_labels = """
        MATCH (n)
        RETURN labels(n) AS label, count(*) AS count
        ORDER BY count DESC
        """
        results = session.run(query_labels)
        for r in results:
            print(f"   {str(r['label']):<50} : {r['count']}")

        # 4. Structural counts: Relationship types
        print("\n4. Structural Completeness - Relationship Type counts:")
        query_rels = """
        MATCH ()-[r]->()
        RETURN type(r) AS rel_type, count(*) AS count
        ORDER BY count DESC
        """
        results = session.run(query_rels)
        for r in results:
            print(f"   {str(r['rel_type']):<50} : {r['count']}")

    driver.close()

def verify_faiss():
    print("\n" + "="*80)
    print("VERIFYING UNIFIED FAISS RETRIEVAL INDEX")
    print("="*80)
    
    index_path = Path("E:/GL_AI/data_processed/faiss_index_unified/vectors.index")
    meta_path = Path("E:/GL_AI/data_processed/faiss_index_unified/metadata.pkl")
    config_path = Path("E:/GL_AI/data_processed/faiss_index_unified/config.json")
    
    if not (index_path.exists() and meta_path.exists()):
        print("[FAIL] Unified FAISS files not found at E:/GL_AI/data_processed/faiss_index_unified/")
        return
        
    try:
        import faiss
    except ImportError:
        print("[FAIL] faiss library not installed. Run: pip install faiss-cpu")
        return

    try:
        index = faiss.read_index(str(index_path))
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
            
        print(f"[SUCCESS] Unified index loaded successfully.")
        print(f"  * Total vectors in merged index : {index.ntotal}")
        print(f"  * Total items in unified metadata: {len(meta)}")
        
        # Check source counts
        manual_cnt = len([m for m in meta if m.get('_source') == 'manual_corrections'])
        baseline_cnt = len([m for m in meta if m.get('_source') != 'manual_corrections'])
        print(f"  * Baseline vectors count       : {baseline_cnt}")
        print(f"  * Manual corrections count     : {manual_cnt}")
        
        # Sample check
        sample_manual = [m for m in meta if m.get('_source') == 'manual_corrections'][:2]
        print(f"\nSample manual chunks in index:")
        for sm in sample_manual:
            print(f"  - Chunk ID: {sm.get('id')} | Doc ID: {sm.get('metadata', {}).get('doc_id')}")
            print(f"    Text snippet: {sm.get('text')[:100]}...")
            
    except Exception as e:
        print(f"[FAIL] Error verifying FAISS index: {e}")

if __name__ == "__main__":
    verify_neo4j()
    verify_faiss()
