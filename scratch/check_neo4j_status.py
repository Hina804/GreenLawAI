from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")

def test_neo4j():
    print(f"DEBUG: Testing connection to {uri} as user {user}")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Check for actual data
            res = session.run("MATCH (n:CourtCase) RETURN count(n) as count")
            count = res.single()["count"]
            print(f"SUCCESS: Connected to Neo4j.")
            print(f"DATA_STATUS: Found {count} CourtCase nodes.")
            
            if count == 0:
                print("WARNING: Database is empty. Hybrid search will yield no results.")
            else:
                print("VERIFIED: Connection is to a LIVE database with data.")
        driver.close()
    except Exception as e:
        print(f"FAILURE: Could not connect to Neo4j. Error: {e}")

if __name__ == "__main__":
    test_neo4j()
