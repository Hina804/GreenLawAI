import os
import sys
import glob
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

def main():
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USER", "neo4j")
    PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    print("Connecting to Neo4j...")
    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        driver.verify_connectivity()
        print("Connection successful!")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    doc_dirs = glob.glob("E:/GL_AI/data_processed/documents/*")
    
    with driver.session() as session:
        # constraints
        session.run("CREATE CONSTRAINT section_node_id IF NOT EXISTS FOR (s:Section) REQUIRE s.node_id IS UNIQUE")
        session.run("CREATE INDEX node_id_index IF NOT EXISTS FOR (n:Document) ON (n.node_id)")

        success_docs = 0
        
        for doc_dir in doc_dirs:
            if not os.path.isdir(doc_dir):
                continue
                
            nodes_path = os.path.join(doc_dir, "phase_6", "graph_export", "nodes.csv")
            rels_path = os.path.join(doc_dir, "phase_6", "graph_export", "relationships.csv")
            
            if os.path.exists(nodes_path) and os.path.exists(rels_path):
                try:
                    nodes_df = pd.read_csv(nodes_path)
                    nodes_df = nodes_df.where(pd.notnull(nodes_df), None)
                    nodes_list = nodes_df.to_dict('records')
                    
                    if not nodes_list:
                        continue
                    
                    query_nodes = """
                    UNWIND $nodes AS node
                    MERGE (n:GenericNode {node_id: coalesce(node['node_id'], node['node_id:ID'])})
                    SET n += node
                    """
                    session.run(query_nodes, nodes=nodes_list)
                    
                    rels_df = pd.read_csv(rels_path)
                    rels_df = rels_df.where(pd.notnull(rels_df), None)
                    rels_list = rels_df.to_dict('records')
                    
                    if rels_list:
                        rel_types = rels_df[':TYPE'].unique()
                        for rel_type in rel_types:
                            type_specific_rels = [r for r in rels_list if r[':TYPE'] == rel_type]
                            safe_type = str(rel_type).replace("-", "_").replace(" ", "_").upper()
                            query_type = f"""
                            UNWIND $rels AS rel
                            MATCH (start {{node_id: coalesce(rel['start_id'], rel[':START_ID'])}})
                            MATCH (end {{node_id: coalesce(rel['end_id'], rel[':END_ID'])}})
                            MERGE (start)-[r:{safe_type}]->(end)
                            SET r += rel
                            """
                            session.run(query_type, rels=type_specific_rels)
                    
                    success_docs += 1
                except Exception as e:
                    print(f"Error importing {os.path.basename(doc_dir)}: {e}")
            else:
                pass # not all have graph exports

    print(f"Successfully imported graph exports for {success_docs} documents.")
    driver.close()

if __name__ == "__main__":
    main()
