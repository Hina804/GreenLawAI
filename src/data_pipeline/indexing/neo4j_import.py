"""
Neo4j Import - Batch Import Scripts for Entities and Chunks
Handles constraints, batch imports with MERGE strategy, and transaction management.
"""

from typing import Dict, Any, List
from pathlib import Path
import json


# Neo4j Metadata Schema
NEO4J_METADATA = {
    # Identity
    "chunk_id",
    "neo4j_chunk_id",
    
    # Hierarchy
    "law_title",
    "chapter",
    "section",
    "clause",
    "subclause",
    
    # Entities (canonical)
    "entity_mentions_canonical",
    "entity_types_canonical",
    
    # Minimal metrics
    "token_count",
    
    # Provenance
    "source_file",
    "version"
}

CHROMADB_ONLY_METADATA = {
    # Statistics
    "entity_filter_stats",
    "entity_count",
    "raw_count",
    "filtered_count",
    "reduction_pct",
    
    # Chunk metrics
    "text_length",
    "chunk_index",
    "total_chunks_in_section",
    
    # Timestamps
    "indexed_at",
    
    # Full hierarchy path (redundant in graph)
    "hierarchy_path",
    
    # Clause details (stored in separate nodes)
    "clauses",
    "sentences",
    "has_clauses"
}


def prepare_neo4j_metadata(chunk_metadata: Dict) -> Dict:
    """Extract only Neo4j-relevant metadata."""
    neo4j_meta = {}
    for key in NEO4J_METADATA:
        if key in chunk_metadata:
            neo4j_meta[key] = chunk_metadata[key]
    return neo4j_meta


def import_to_neo4j(
    neo4j_uri: str,
    username: str,
    password: str,
    entity_registry_path: str,
    chunks_export_path: str,
    batch_size_entities: int = 500,
    batch_size_chunks: int = 100
):
    """
    Import data to Neo4j with batching and MERGE strategy.
    
    Args:
        neo4j_uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
        username: Neo4j username
        password: Neo4j password
        entity_registry_path: Path to entity_registry.json
        chunks_export_path: Path to chunks export JSON
        batch_size_entities: Batch size for entity import
        batch_size_chunks: Batch size for chunk import
    """
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[ERR] Error: neo4j package not installed")
        print("Install with: pip install neo4j")
        return
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(username, password))
    
    try:
        with driver.session() as session:
            # 1. Create constraints
            print("\n" + "="*60)
            print("STEP 1: Creating Constraints")
            print("="*60)
            create_constraints(session)
            
            # 2. Import entities
            print("\n" + "="*60)
            print("STEP 2: Importing Entities")
            print("="*60)
            import_entities(session, entity_registry_path, batch_size_entities)
            
            # 3. Import chunks
            print("\n" + "="*60)
            print("STEP 3: Importing Chunks")
            print("="*60)
            import_chunks(session, chunks_export_path, batch_size_chunks)
            
            # 4. Link entities
            print("\n" + "="*60)
            print("STEP 4: Linking Entities to Chunks")
            print("="*60)
            link_entities(session, batch_size_chunks)
            
            print("\n" + "="*60)
            print("IMPORT COMPLETE")
            print("="*60)
    
    finally:
        driver.close()


def create_constraints(session):
    """Create uniqueness constraints and indexes."""
    constraints = [
        # Entity constraints
        "CREATE CONSTRAINT entity_canonical_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.canonical_name IS UNIQUE",
        "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
        
        # Chunk constraints
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
        
        # Clause constraints
        "CREATE CONSTRAINT clause_id IF NOT EXISTS FOR (cl:Clause) REQUIRE cl.clause_id IS UNIQUE",
        
        # Section constraints
        "CREATE CONSTRAINT section_id IF NOT EXISTS FOR (s:Section) REQUIRE (s.law_title, s.section) IS UNIQUE",
    ]
    
    for constraint in constraints:
        try:
            session.run(constraint)
            print(f"[OK] Created: {constraint.split('FOR')[0].strip()}")
        except Exception as e:
            print(f"[!] Constraint already exists or error: {str(e)[:50]}")


def import_entities(session, entity_registry_path: str, batch_size: int):
    """Import entities in batches."""
    with open(entity_registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    entities = registry['entities']
    total = len(entities)
    
    print(f"Importing {total} entities in batches of {batch_size}...")
    
    for i in range(0, total, batch_size):
        batch = entities[i:i+batch_size]
        
        query = """
        UNWIND $entities AS entity
        MERGE (e:Entity {canonical_name: entity.canonical_name})
        ON CREATE SET
            e.entity_type = entity.entity_type,
            e.frequency = entity.frequency,
            e.chunk_count = entity.chunk_count,
            e.aliases = entity.aliases,
            e.first_seen_doc = entity.first_seen_doc,
            e.last_seen_doc = entity.last_seen_doc,
            e.created_at = datetime()
        ON MATCH SET
            e.frequency = entity.frequency,
            e.chunk_count = entity.chunk_count,
            e.updated_at = datetime()
        """
        
        session.run(query, entities=batch)
        print(f"  Imported batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
    
    print(f"[OK] Imported {total} entities")


def import_chunks(session, chunks_export_path: str, batch_size: int):
    """Import chunks with clauses in batches."""
    with open(chunks_export_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chunks = data['chunks']
    
    # Pre-process chunks to handle stringified JSON from ChromaDB
    print("Pre-processing chunks to parse JSON fields...")
    for chunk in chunks:
        # Parse clauses
        if 'clauses' in chunk and isinstance(chunk['clauses'], str):
            try:
                chunk['clauses'] = json.loads(chunk['clauses'])
            except Exception:
                chunk['clauses'] = []
        
        # Parse entity mentions
        if 'entity_mentions_canonical' in chunk and isinstance(chunk['entity_mentions_canonical'], str):
            try:
                chunk['entity_mentions_canonical'] = json.loads(chunk['entity_mentions_canonical'])
            except Exception:
                chunk['entity_mentions_canonical'] = []
                
        # Parse entity types
        if 'entity_types_canonical' in chunk and isinstance(chunk['entity_types_canonical'], str):
            try:
                chunk['entity_types_canonical'] = json.loads(chunk['entity_types_canonical'])
            except Exception:
                chunk['entity_types_canonical'] = []

    total = len(chunks)
    print(f"Importing {total} chunks in batches of {batch_size}...")
    
    for i in range(0, total, batch_size):
        batch = chunks[i:i+batch_size]
        
        query = """
        UNWIND $chunks AS chunk
        MERGE (c:Chunk {chunk_id: chunk.chunk_id})
        SET c.text = chunk.text,
            c.token_count = chunk.token_count,
            c.law_title = chunk.law_title,
            c.section = chunk.section,
            c.section_id = chunk.section_id,
            c.document_id = chunk.document_id,
            c.source_file = chunk.source_file,
            c.version = chunk.version,
            c.faiss_row_id = chunk.faiss_row_id,
            c.faiss_index = chunk.faiss_index,
            c.source_chunk_id = chunk.source_chunk_id,
            c.entity_mentions_canonical = chunk.entity_mentions_canonical,
            c.entity_types_canonical = chunk.entity_types_canonical
        
        // Create clause nodes if present
        WITH c, chunk
        UNWIND COALESCE(chunk.clauses, []) AS clause
        MERGE (cl:Clause {clause_id: clause.clause_id})
        SET cl.text = clause.text,
            cl.clause_marker = clause.clause_marker,
            cl.start_offset = clause.start_offset,
            cl.end_offset = clause.end_offset
        MERGE (c)-[:CONTAINS_CLAUSE]->(cl)
        """
        
        session.run(query, chunks=batch)
        print(f"  Imported batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
    
    print(f"[OK] Imported {total} chunks")


def link_entities(session, batch_size: int):
    """Link chunks to entities."""
    # Note: For larger datasets, use apoc.periodic.iterate or proper batching with SKIP
    # For now, we process all in one go as the dataset is small (103 chunks)
    query = """
    MATCH (c:Chunk)
    WHERE c.entity_mentions_canonical IS NOT NULL
    UNWIND c.entity_mentions_canonical AS entity_name
    MATCH (e:Entity {canonical_name: entity_name})
    MERGE (c)-[:MENTIONS]->(e)
    RETURN count(*) as links_created
    """
    
    print("Linking entities to chunks...")
    result = session.run(query)
    record = result.single()
    links_created = record["links_created"] if record else 0
    
    print(f"[OK] Created {links_created} MENTIONS relationships")


if __name__ == "__main__":
    # Example usage
    import_to_neo4j(
        neo4j_uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
        entity_registry_path="entity_registry.json",
        chunks_export_path="chunks_export.json",
        batch_size_entities=500,
        batch_size_chunks=100
    )
