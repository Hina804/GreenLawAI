"""
remediate_duplicate_nodes.py
Finds and merges duplicate nodes with the same node_id in Neo4j database.
Transfers relationships, unions labels/properties, and removes duplicates.
"""

import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RemediateDuplicates")

load_dotenv(dotenv_path="E:/GL_AI/.env")

def main():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.error("Neo4j package not found! Please run: pip install neo4j")
        return
        
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    username = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    
    logger.info(f"Connecting to Neo4j database '{database}' at {uri}...")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    try:
        with driver.session(database=database) as session:
            # 1. Find all duplicate node_ids
            logger.info("Scanning for duplicate node_ids...")
            query_find_dups = """
            MATCH (n)
            WHERE n.node_id IS NOT NULL
            WITH n.node_id AS nid, count(n) AS cnt
            WHERE cnt > 1
            RETURN nid, cnt
            """
            result = session.run(query_find_dups)
            dup_records = list(result)
            
            if not dup_records:
                logger.info("No duplicate node_ids found in the database. Clean!")
                return
                
            logger.info(f"Found {len(dup_records)} duplicate node_ids to merge.")
            
            for rec in dup_records:
                nid = rec["nid"]
                logger.info(f"Merging duplicates for node_id: '{nid}'...")
                
                # Fetch all nodes with this node_id
                query_fetch_nodes = """
                MATCH (n)
                WHERE n.node_id = $nid
                RETURN id(n) AS node_element_id, labels(n) AS labels, n AS properties
                """
                nodes = [dict(r) for r in session.run(query_fetch_nodes, nid=nid)]
                logger.info(f"  Found {len(nodes)} duplicate nodes.")
                
                # We will pick the "keeper" as the node with the most labels
                # (or longest properties count if tie)
                nodes.sort(key=lambda x: (len(x["labels"]), len(x["properties"])), reverse=True)
                keeper = nodes[0]
                discards = nodes[1:]
                
                keeper_id = keeper["node_element_id"]
                logger.info(f"  Keeper Node ID: {keeper_id}, Labels: {keeper['labels']}")
                
                # We will collect all labels and properties to merge onto keeper
                union_labels = set(keeper["labels"])
                merged_properties = dict(keeper["properties"])
                
                for discard in discards:
                    discard_id = discard["node_element_id"]
                    logger.info(f"  Processing discard Node ID: {discard_id}, Labels: {discard['labels']}")
                    
                    # Union labels
                    union_labels.update(discard["labels"])
                    
                    # Merge properties (prefer longer/non-null values)
                    for k, v in discard["properties"].items():
                        if v is not None and v != "":
                            if k not in merged_properties or merged_properties[k] is None or merged_properties[k] == "":
                                merged_properties[k] = v
                            elif len(str(v)) > len(str(merged_properties[k])):
                                merged_properties[k] = v
                                
                    # Transfer incoming relationships from discard to keeper
                    # match (s)-[r]->(discard) merge (s)-[new_r:TYPE]->(keeper)
                    query_in_rels = """
                    MATCH (s)-[r]->(d)
                    WHERE id(d) = $discard_id
                    RETURN id(s) AS start_id, type(r) AS rel_type, properties(r) AS props
                    """
                    in_rels = session.run(query_in_rels, discard_id=discard_id)
                    for r_rec in in_rels:
                        start_id = r_rec["start_id"]
                        rel_type = r_rec["rel_type"]
                        props = r_rec["props"]
                        
                        query_merge_in = f"""
                        MATCH (start) WHERE id(start) = $start_id
                        MATCH (keeper) WHERE id(keeper) = $keeper_id
                        MERGE (start)-[new_r:`{rel_type}`]->(keeper)
                        SET new_r += $props
                        """
                        session.run(query_merge_in, start_id=start_id, keeper_id=keeper_id, props=props)
                        
                    # Transfer outgoing relationships from discard to keeper
                    # match (discard)-[r]->(e) merge (keeper)-[new_r:TYPE]->(e)
                    query_out_rels = """
                    MATCH (d)-[r]->(e)
                    WHERE id(d) = $discard_id
                    RETURN id(e) AS end_id, type(r) AS rel_type, properties(r) AS props
                    """
                    out_rels = session.run(query_out_rels, discard_id=discard_id)
                    for r_rec in out_rels:
                        end_id = r_rec["end_id"]
                        rel_type = r_rec["rel_type"]
                        props = r_rec["props"]
                        
                        query_merge_out = f"""
                        MATCH (keeper) WHERE id(keeper) = $keeper_id
                        MATCH (end) WHERE id(end) = $end_id
                        MERGE (keeper)-[new_r:`{rel_type}`]->(end)
                        SET new_r += $props
                        """
                        session.run(query_merge_out, keeper_id=keeper_id, end_id=end_id, props=props)
                        
                    # Delete the discard node
                    query_delete = "MATCH (d) WHERE id(d) = $discard_id DETACH DELETE d"
                    session.run(query_delete, discard_id=discard_id)
                    logger.info(f"  Detached and deleted discard Node ID: {discard_id}")
                    
                # Update keeper's properties
                query_update_props = "MATCH (k) WHERE id(k) = $keeper_id SET k = $props"
                session.run(query_update_props, keeper_id=keeper_id, props=merged_properties)
                
                # Update keeper's labels
                labels_str = "".join([f":`{l}`" for l in union_labels])
                query_update_labels = f"MATCH (k) WHERE id(k) = $keeper_id SET k{labels_str}"
                session.run(query_update_labels, keeper_id=keeper_id)
                logger.info(f"  Updated keeper Node ID: {keeper_id} with merged properties and labels: {list(union_labels)}")
                
            logger.info("Deduplication complete! ✓")
            
    finally:
        driver.close()

if __name__ == "__main__":
    main()
