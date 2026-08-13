import os
import sys
from neo4j import GraphDatabase

def main():
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    
    print("="*60)
    print("HIERARCHY STITCHING - NEO4J")
    print("="*60)
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            # Stitch Chunks to Sections
            print("Grafting Chunks onto Section hierarchy...")
            query = """
            MATCH (c:Chunk)
            WHERE c.section_id IS NOT NULL
            MATCH (s:GenericNode {node_id: c.section_id})
            MERGE (c)-[r:PART_OF_HIERARCHY]->(s)
            RETURN count(r) as count
            """
            result = session.run(query)
            count = result.single()['count']
            print(f"[OK] Created {count} PART_OF_HIERARCHY relationships.")
            
            # Verify connectivity
            print("\nVerifying connectivity...")
            verify_query = """
            MATCH (c:Chunk)
            OPTIONAL MATCH (c)-[:PART_OF_HIERARCHY]->(s)
            RETURN count(c) as total, count(s) as linked
            """
            result = session.run(verify_query)
            stats = result.single()
            total = stats['total']
            linked = stats['linked']
            
            print(f"Total Chunks: {total}")
            print(f"Linked Chunks: {linked}")
            
            if total > 0:
                percent = (linked / total) * 100
                print(f"Connectivity: {percent:.1f}%")
                
                if percent < 90:
                    print("[!] Warning: Low connectivity. Check if section_ids match node_ids.")
                else:
                    print("[OK] High connectivity achieved.")

        driver.close()
    except Exception as e:
        print(f"[FAIL] Error during stitching: {e}")

if __name__ == "__main__":
    main()
