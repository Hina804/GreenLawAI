from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# Testing bolt protocol which is standard for local standalone Neo4j
uri = "bolt://127.0.0.1:7687"
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")

def test_neo4j():
    print(f"DEBUG: Testing connection to {uri}")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            res = session.run("MATCH (n) RETURN count(n) as count")
            count = res.single()["count"]
            print(f"SUCCESS: Connected via BOLT.")
            print(f"DATA_STATUS: {count} total nodes in DB.")
        driver.close()
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    test_neo4j()
