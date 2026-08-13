import os
import sys
import pandas as pd
from neo4j import GraphDatabase
from pathlib import Path
import json
from dotenv import load_dotenv

load_dotenv()

def main():
    # Configuration
    ROOT = Path(__file__).parent.parent
    DOCS_DIR = ROOT / "data_processed" / "documents"
    
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    
    print("="*60)
    print("SOVEREIGN GRAPH IMPORT - NEO4J")
    print("="*60)
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("[OK] Connected to Neo4j.")
    except Exception as e:
        print(f"[FAIL] Could not connect to Neo4j: {e}")
        return

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
                nodes_csv = doc_dir / "phase_6" / "graph_export" / "nodes.csv"
                rels_csv = doc_dir / "phase_6" / "graph_export" / "relationships.csv"
                if nodes_csv.exists() and rels_csv.exists():
                    doc_paths.append((doc_id, nodes_csv, rels_csv))
                else:
                    print(f"[!] Warning: Missing graph exports in {doc_id}")
    else:
        print("[FAIL] batch_manifest.json not found!")
        return
    
    print(f"Found {len(doc_paths)} documents for graph import.")
    
    with driver.session() as session:
        # Create core constraints if not already there
        print("Ensuring constraints...")
        session.run("CREATE CONSTRAINT section_node_id IF NOT EXISTS FOR (s:Section) REQUIRE s.node_id IS UNIQUE")
        session.run("CREATE CONSTRAINT law_node_id IF NOT EXISTS FOR (l:Law) REQUIRE l.node_id IS UNIQUE")
        session.run("CREATE INDEX node_id_index IF NOT EXISTS FOR (n:Document) ON (n.node_id)")

        for doc_id, nodes_path, rels_path in doc_paths:
            print(f"\nImporting {doc_id}...")
            
            # Load Nodes
            nodes_df = pd.read_csv(nodes_path)
            # Replace NaN with None for Neo4j compatibility
            nodes_df = nodes_df.where(pd.notnull(nodes_df), None)
            
            nodes_list = nodes_df.to_dict('records')
            
            # Dynamic label handling
            # In nodes.csv, :LABEL is usually Law;KPK_Law or similar
            # We will use the first label as the primary label for the node, 
            # and add any others if possible. For simplicity, we'll use 'Section' for hierarchy nodes
            # and 'Law' for roots.
            
            query_nodes = """
            UNWIND $nodes AS node
            MERGE (n:Section {node_id: coalesce(node['node_id'], node['node_id:ID'])})
            SET n += node
            SET n:GenericNode
            """
            
            try:
                session.run(query_nodes, nodes=nodes_list)
                print(f"  [OK] Ingested {len(nodes_list)} nodes.")
            except Exception as e:
                print(f"  [FAIL] Node ingestion failed for {doc_id}: {e}")
                continue

            # Load Relationships
            rels_df = pd.read_csv(rels_path)
            rels_df = rels_df.where(pd.notnull(rels_df), None)
            rels_list = rels_df.to_dict('records')
            
            try:
                # We'll iterate through types to avoid APOC dependency for dynamic types
                rel_types = rels_df[':TYPE'].unique()
                for rel_type in rel_types:
                    type_specific_rels = [r for r in rels_list if r[':TYPE'] == rel_type]
                    # Filter out types that might not be valid Cypher identifiers if any
                    safe_type = str(rel_type).replace("-", "_").replace(" ", "_").upper()
                    
                    query_type = f"""
                    UNWIND $rels AS rel
                    MATCH (start {{node_id: coalesce(rel['start_id'], rel[':START_ID'])}})
                    MATCH (end {{node_id: coalesce(rel['end_id'], rel[':END_ID'])}})
                    MERGE (start)-[r:{safe_type}]->(end)
                    SET r += rel
                    """
                    session.run(query_type, rels=type_specific_rels)
                
                print(f"  [OK] Ingested {len(rels_list)} relationships ({len(rel_types)} types).")
            except Exception as e:
                print(f"  [FAIL] Relationship ingestion failed for {doc_id}: {e}")

    driver.close()
    print("\nSovereign Graph Import Complete.")

if __name__ == "__main__":
    main()
