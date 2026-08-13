"""Check MENTIONS direction in the actual DB."""
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

with driver.session() as s:
    # Check direction: is it (Chunk)-[:MENTIONS]->(Entity) or (Entity)-[:MENTIONS]->(Chunk)?
    print("=== Direction check: (Chunk)-[:MENTIONS]->(Entity) ===")
    r1 = s.run("""
        MATCH (c:Chunk)-[:MENTIONS]->(e:Entity {canonical_name: 'guzara_forest'})
        RETURN count(c) as count
    """)
    print(f"  Forward direction count: {r1.single()['count']}")

    print("\n=== Direction check: (Entity)-[:MENTIONS]->(Chunk) ===")
    r2 = s.run("""
        MATCH (e:Entity {canonical_name: 'guzara_forest'})-[:MENTIONS]->(c:Chunk)
        RETURN count(c) as count
    """)
    print(f"  Reverse direction count: {r2.single()['count']}")

    print("\n=== Direction check: any direction ===")
    r3 = s.run("""
        MATCH (c:Chunk)-[:MENTIONS]-(e:Entity {canonical_name: 'guzara_forest'})
        RETURN count(c) as count
    """)
    print(f"  Any direction count: {r3.single()['count']}")

    # Now run the EXACT Cypher from graph_rag_retriever.py
    print("\n=== EXACT retriever Cypher simulation ===")
    search_terms = ['guzara', 'guzara_forest', 'guzara forest', 'forest_officer', 'forest officer']
    r4 = s.run("""
        UNWIND $entities AS query_term
        MATCH (e:Entity)
        WHERE toLower(e.canonical_name) = toLower(query_term)
           OR any(alias IN e.aliases WHERE toLower(alias) = toLower(query_term))
        
        MATCH (c:Chunk)-[:MENTIONS]->(e)
        
        OPTIONAL MATCH (c)-[:PART_OF_HIERARCHY*1..3]->(s:Section)<-[:HAS_SECTION]-(d:LegalDocument)
        
        RETURN c.chunk_id, 
               left(c.text, 100) as preview,
               COALESCE(d.document_id, c.document_id) as law_title, 
               COALESCE(s.section_id, c.section_id) as section,
               count(DISTINCT e) as direct_mentions,
               e.type as entity_type
        ORDER BY direct_mentions DESC
        LIMIT 10
    """, entities=search_terms, k=10)
    
    count = 0
    for rec in r4:
        count += 1
        print(f"  [{count}] mentions={rec['direct_mentions']}, law={rec['law_title']}, section={rec['section']}")
        print(f"      {rec['preview']}...")
    if count == 0:
        print("  (NO RESULTS)")
    print(f"  Total: {count}")

driver.close()
