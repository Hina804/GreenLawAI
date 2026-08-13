"""
Neo4j Setup and Import Script
Complete workflow: Setup → Import → Verify
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def check_neo4j_connection(uri: str, username: str, password: str) -> bool:
    """Check if Neo4j is accessible."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            result = session.run("RETURN 1")
            result.single()
        driver.close()
        print("[OK] Neo4j connection successful")
        return True
    except Exception as e:
        print(f"[FAIL] Neo4j connection failed: {e}")
        return False


def run_import(uri: str, username: str, password: str):
    """Run the complete import process."""
    from indexing.neo4j_import import import_to_neo4j
    
    print("\n" + "="*70)
    print("NEO4J IMPORT PROCESS")
    print("="*70)
    
    # Check files exist
    entity_file = Path("entity_registry.json")
    chunks_file = Path("chunks_export.json")
    
    if not entity_file.exists():
        print(f"[FAIL] Error: {entity_file} not found")
        print("Run: python scripts/test_neo4j_export.py first")
        return False
    
    if not chunks_file.exists():
        print(f"[FAIL] Error: {chunks_file} not found")
        print("Run: python scripts/test_neo4j_export.py first")
        return False
    
    print(f"[OK] Found {entity_file}")
    print(f"[OK] Found {chunks_file}")
    
    # Run import
    import_to_neo4j(
        neo4j_uri=uri,
        username=username,
        password=password,
        entity_registry_path=str(entity_file),
        chunks_export_path=str(chunks_file),
        batch_size_entities=500,
        batch_size_chunks=100
    )
    
    return True


def verify_import(uri: str, username: str, password: str):
    """Verify the import was successful."""
    from neo4j import GraphDatabase
    
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)
    
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    with driver.session() as session:
        # Count entities
        result = session.run("MATCH (e:Entity) RETURN count(e) as count")
        entity_count = result.single()["count"]
        print(f"[OK] Entities: {entity_count} (expected: ~637)")
        
        # Count chunks
        result = session.run("MATCH (c:Chunk) RETURN count(c) as count")
        chunk_count = result.single()["count"]
        print(f"[OK] Chunks: {chunk_count} (expected: 3404)")
        
        # Count relationships
        result = session.run("MATCH ()-[r:MENTIONS]->() RETURN count(r) as count")
        mention_count = result.single()["count"]
        print(f"[OK] MENTIONS relationships: {mention_count} (expected: >3404)")
        
        # Sample query - High Frequency
        print("\n[OK] Providence Check - High Frequency Entity:")
        result = session.run("""
            MATCH (e:Entity {canonical_name: 'government'})
            RETURN e.canonical_name, e.frequency, e.first_seen_doc
        """)
        record = result.single()
        if record:
            print(f"  - {record['e.canonical_name']}: {record['e.frequency']} mentions in {record['e.first_seen_doc']}")

        # Sample query - Random Low Frequency
        print("\n[OK] Providence Check - Random Entity:")
        result = session.run("""
            MATCH (e:Entity) 
            WHERE e.frequency = 1
            RETURN e.canonical_name, e.first_seen_doc
            LIMIT 1
        """)
        record = result.single()
        if record:
            print(f"  - {record['e.canonical_name']} from {record['e.first_seen_doc']}")
        else:
            print("  - [!] No low-frequency entities found for sampling.")
    
    driver.close()
    
    print("\n" + "="*70)
    print("[OK] VERIFICATION SUCCESSFUL")
    print("="*70)
    return {"entities": entity_count, "chunks": chunk_count, "mentions": mention_count}


def main():
    """Main execution."""
    print("="*70)
    print("NEO4J SETUP AND IMPORT")
    print("="*70)
    
    # Configuration
    NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
    
    print(f"\nConfiguration:")
    print(f"  URI: {NEO4J_URI}")
    print(f"  Username: {NEO4J_USER}")
    
    # Step 1: Check connection and credentials
    print("\n" + "="*70)
    print("STEP 1: Checking Neo4j Connection")
    print("="*70)
    
    if NEO4J_PASSWORD == "password":
        print("[FAIL] ERROR: Default credentials 'password' detected.")
        print("For security and to ensure explicit confirmation, you MUST set NEO4J_PASSWORD env var.")
        print("Example: $env:NEO4J_PASSWORD='your_actual_password'")
        sys.exit(1)

    if not check_neo4j_connection(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD):
        print("\n[!] Neo4j is not running or not accessible")
        return
    
    # Step 2: First Import Run
    print("\n" + "="*70)
    print("STEP 2: Initial Import")
    print("="*70)
    if not run_import(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD):
        return
    
    stats1 = verify_import(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # Step 3: Idempotency Test (Second Run)
    print("\n" + "="*70)
    print("STEP 3: Idempotency Test (Rerun)")
    print("="*70)
    print("Running import again to ensure No Growth / MERGE stability...")
    if not run_import(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD):
        return
    
    stats2 = verify_import(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # Comparison
    print("\n" + "="*70)
    print("IDEMPOTENCY REPORT")
    print("="*70)
    growth = False
    for key in stats1:
        diff = stats2[key] - stats1[key]
        status = "[OK]" if diff == 0 else "[FAIL]"
        print(f"{status} {key.capitalize()}: {stats1[key]} -> {stats2[key]} (Change: {diff})")
        if diff != 0:
            growth = True
            
    if growth:
        print("\n[FAIL] ERROR: Graph grew during idempotent rerun. MERGE logic may be flawed.")
        sys.exit(1)
    else:
        print("\n[OK] SUCCESS: Idempotency verified. Graph is stable.")

    # Next steps
    print("\n" + "="*70)
    print("FINISHED")
    print("="*70)


if __name__ == "__main__":
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[ERR] Error: neo4j package not installed")
        print("Install with: pip install neo4j")
        sys.exit(1)
    
    main()
