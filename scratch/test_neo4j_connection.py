from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")

print(f"Testing connection to {uri} with user {user}...")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 1 as connection_test")
        record = result.single()
        if record and record["connection_test"] == 1:
            print("✅ Neo4j Connection SUCCESSFUL!")
        else:
            print("❌ Neo4j Connection FAILED: Unexpected response.")
    driver.close()
except Exception as e:
    print(f"❌ Neo4j Connection FAILED: {e}")
