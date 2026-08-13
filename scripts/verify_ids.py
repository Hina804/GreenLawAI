from neo4j import GraphDatabase
import os

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'))
with driver.session() as s:
    print("--- Chunk Samples ---")
    res = s.run('MATCH (c:Chunk) RETURN c.chunk_id as cid, c.section_id as sid, c.document_id as did LIMIT 5')
    for r in res:
        print(f"CID: {r['cid']} | SID: {r['sid']} | DID: {r['did']}")
        
    print("\n--- GenericNode Samples ---")
    res = s.run('MATCH (n:GenericNode) RETURN n.node_id as nid, n.section_id as sid LIMIT 5')
    for r in res:
        print(f"NID: {r['nid']} | SID: {r['sid']}")
        
    print("\n--- Count Stats ---")
    res = s.run('MATCH (c:Chunk) RETURN count(c) as count')
    print(f"Total Chunks: {res.single()['count']}")
    
    res = s.run('MATCH (n:GenericNode) RETURN count(n) as count')
    print(f"Total GenericNodes: {res.single()['count']}")
    
    res = s.run('MATCH (c:Chunk) WHERE c.section_id IS NOT NULL RETURN count(c) as count')
    print(f"Chunks with section_id: {res.single()['count']}")

driver.close()
