"""
ingest_manual_graphs_to_neo4j.py
Batch imports compiled graph CSV tables into Neo4j with full schema enforcement.
"""

import os
import sys
import csv
import logging
from pathlib import Path
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("IngestNeo4j")

# Load environment variables
load_dotenv(dotenv_path="E:/GL_AI/.env")

CSV_DIR = Path("E:/GL_AI/data_processed/graph_exports")
NODES_CSV = CSV_DIR / "nodes.csv"
RELS_CSV = CSV_DIR / "relationships.csv"
CONSTRAINTS_CYPHER = CSV_DIR / "constraints.cypher"

def main():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.error("Neo4j package not found! Please run: pip install neo4j")
        return
        
    # Read environment credentials
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    username = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    
    logger.info(f"Connecting to Neo4j database '{database}' at {uri}...")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    try:
        with driver.session(database=database) as session:
            # 1. Apply Schema Constraints
            logger.info("Applying schema constraints...")
            if CONSTRAINTS_CYPHER.exists():
                with open(CONSTRAINTS_CYPHER, "r", encoding="utf-8") as f:
                    statements = f.read().split(";")
                    
                for statement in statements:
                    statement = statement.strip()
                    if not statement or statement.startswith("--"):
                        continue
                    try:
                        session.run(statement)
                        logger.info(f"  Applied constraint/index ✓")
                    except Exception as e:
                        logger.warning(f"  Constraint warning (likely already exists): {str(e)[:80]}")
            else:
                logger.warning("Constraints file not found! Skipping Step 1.")
                
            # 2. Batch-Ingest Nodes
            logger.info("Loading nodes.csv...")
            if not NODES_CSV.exists():
                logger.error("nodes.csv not found! Aborting.")
                return
                
            nodes_by_label_group = {}
            with open(NODES_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    label_str = row[":LABEL"]
                    if not label_str:
                        label_str = "KPK_Entity"
                        
                    if label_str not in nodes_by_label_group:
                        nodes_by_label_group[label_str] = []
                        
                    # Extract standard fields (resilient to header renaming)
                    node_id = row.get("node_id", row.get("node_id:ID"))
                    if not node_id:
                        logger.warning(f"Skipping node row with missing ID: {row}")
                        continue
                        
                    # Group remaining fields as properties
                    properties = {}
                    for k, v in row.items():
                        if k not in ["node_id", "node_id:ID", ":LABEL", "source_file", "creation_timestamp", "export_version", "logic_hash"] and v != "":
                            properties[k] = v
                            
                    # Add standard metadata properties
                    properties["source_file"] = row.get("source_file", "")
                    properties["creation_timestamp"] = row.get("creation_timestamp", "")
                    properties["export_version"] = row.get("export_version", "")
                    
                    nodes_by_label_group[label_str].append({
                        "node_id": node_id,
                        "properties": properties
                    })
                    
            # Load nodes label group by label group
            for label_group, nodes in nodes_by_label_group.items():
                labels = label_group.split(";")
                labels_cypher = "".join([f":`{l}`" for l in labels])
                
                # Perform batched UNWIND updates (1000 nodes per batch)
                batch_size = 1000
                total = len(nodes)
                logger.info(f"Ingesting {total} nodes of type ({label_group})...")
                
                for i in range(0, total, batch_size):
                    batch = nodes[i:i+batch_size]
                    query = f"""
                    UNWIND $batch AS node
                    MERGE (n {{node_id: node.node_id}})
                    SET n += node.properties
                    SET n{labels_cypher}
                    """
                    session.run(query, batch=batch)
                    
            logger.info("Node ingestion completed successfully ✓")
            
            # 3. Batch-Ingest Relationships
            logger.info("Loading relationships.csv...")
            if not RELS_CSV.exists():
                logger.error("relationships.csv not found! Aborting.")
                return
                
            rels_by_type = {}
            with open(RELS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rel_type = row[":TYPE"]
                    if not rel_type:
                        rel_type = "RELATES_TO"
                        
                    if rel_type not in rels_by_type:
                        rels_by_type[rel_type] = []
                        
                    # Extract fields (resilient to header renaming)
                    start_id = row.get(":START_ID", row.get("start_id"))
                    end_id = row.get(":END_ID", row.get("end_id"))
                    relationship_id = row.get("relationship_id")
                    
                    if not start_id or not end_id:
                        logger.warning(f"Skipping relationship row with missing start/end ID: {row}")
                        continue
                        
                    # Extract properties
                    properties = {}
                    for k, v in row.items():
                        if k not in [":START_ID", "start_id", ":END_ID", "end_id", ":TYPE", "relationship_id", "source_file", "creation_timestamp", "export_version", "logic_hash"] and v != "":
                            properties[k] = v
                            
                    # Add standard metadata properties
                    properties["source_file"] = row.get("source_file", "")
                    properties["creation_timestamp"] = row.get("creation_timestamp", "")
                    properties["export_version"] = row.get("export_version", "")
                    
                    rels_by_type[rel_type].append({
                        "start_id": start_id,
                        "end_id": end_id,
                        "relationship_id": relationship_id,
                        "properties": properties
                    })
                    
            # Load relationships type by type
            for rel_type, rels in rels_by_type.items():
                batch_size = 1000
                total = len(rels)
                logger.info(f"Ingesting {total} relationships of type ({rel_type})...")
                
                for i in range(0, total, batch_size):
                    batch = rels[i:i+batch_size]
                    query = f"""
                    UNWIND $batch AS rel
                    MATCH (start {{node_id: rel.start_id}})
                    MATCH (end {{node_id: rel.end_id}})
                    MERGE (start)-[r:`{rel_type}` {{relationship_id: rel.relationship_id}}]->(end)
                    SET r += rel.properties
                    """
                    session.run(query, batch=batch)
                    
            logger.info("Relationship ingestion completed successfully ✓")
            logger.info("Step 4 Ingestion Complete! ✓")
            
    finally:
        driver.close()

if __name__ == "__main__":
    main()
