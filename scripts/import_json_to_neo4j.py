import os
import sys
import json
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

def main():
    base = Path("E:/GL_AI/data_processed/documents")
    
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    
    success = 0
    with driver.session() as session:
        # Constraints
        session.run("CREATE CONSTRAINT section_node_id IF NOT EXISTS FOR (s:Section) REQUIRE s.node_id IS UNIQUE")
        session.run("CREATE INDEX node_id_index IF NOT EXISTS FOR (n:Document) ON (n.node_id)")

        for doc_dir in sorted(base.iterdir()):
            if not doc_dir.is_dir(): continue
            
            p6_json = doc_dir / "phase_6" / "phase_6_6_graph_construction.json"
            if not p6_json.exists(): continue
            
            with open(p6_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            nodes_by_type = data.get("data", {}).get("nodes_by_type", {})
            rels_by_type = data.get("data", {}).get("relationships_by_type", {})
            
            if not nodes_by_type and not rels_by_type:
                continue

            try:
                # Import Nodes
                for node_type, nodes in nodes_by_type.items():
                    # Sanitize list properties for Neo4j by converting them to strings or JSON if complex
                    sanitized_nodes = []
                    for n in nodes:
                        clean_props = {}
                        for k, v in n.get("properties", {}).items():
                            if isinstance(v, (dict, list)):
                                clean_props[k] = json.dumps(v)
                            else:
                                clean_props[k] = v
                        n["properties"] = clean_props
                        sanitized_nodes.append(n)

                    query = f"""
                    UNWIND $nodes AS node
                    MERGE (n:{node_type} {{node_id: node.node_id}})
                    SET n += node.properties
                    SET n:GenericNode
                    """
                    session.run(query, nodes=sanitized_nodes)

                # Import Relationships
                for rel_type, rels in rels_by_type.items():
                    safe_type = str(rel_type).replace("-", "_").replace(" ", "_").upper()
                    
                    sanitized_rels = []
                    for r in rels:
                        clean_props = {}
                        for k, v in r.get("properties", {}).items():
                            if isinstance(v, (dict, list)):
                                clean_props[k] = json.dumps(v)
                            else:
                                clean_props[k] = v
                        r["properties"] = clean_props
                        sanitized_rels.append(r)

                    query = f"""
                    UNWIND $rels AS rel
                    MATCH (start {{node_id: rel.start_node_id}})
                    MATCH (end {{node_id: rel.end_node_id}})
                    MERGE (start)-[r:{safe_type}]->(end)
                    SET r += rel.properties
                    """
                    session.run(query, rels=sanitized_rels)
                
                success += 1
            except Exception as e:
                print(f"Error importing {doc_dir.name}: {e}")

    print(f"Graph JSON import complete. Successfully imported {success} documents.")
    driver.close()

if __name__ == "__main__":
    main()
