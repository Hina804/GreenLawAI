from neo4j import GraphDatabase
import os

def verify():
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "bypass_auth" # We bypassed auth in neo4j.conf
    
    print(f"Connecting to {uri}...")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            print("Querying counts...")
            
            # Entities
            res_e = session.run("MATCH (e:Entity) RETURN count(e) as count")
            e_count = res_e.single()["count"]
            
            # Chunks
            res_c = session.run("MATCH (c:Chunk) RETURN count(c) as count")
            c_count = res_c.single()["count"]
            
            # Mentions
            res_r = session.run("MATCH ()-[r:MENTIONS]->() RETURN count(r) as count")
            r_count = res_r.single()["count"]
            
            print(f"--- RESULTS ---")
            print(f"Entities: {e_count}")
            print(f"Chunks: {c_count}")
            print(f"Relationships: {r_count}")
            print(f"---------------")
            
        driver.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
