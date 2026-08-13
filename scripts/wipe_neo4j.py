from neo4j import GraphDatabase
import os
from pathlib import Path

# Try to load env if available (though we found it empty)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
user = os.getenv('NEO4J_USER', 'neo4j')
pwd = os.getenv('NEO4J_PASSWORD', 'password')

print(f"Connecting to {uri} as {user}...")

try:
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as session:
        # Check node count before
        result = session.run("MATCH (n) RETURN count(n) as count")
        initial_count = result.single()['count']
        print(f"Found {initial_count} nodes.")
        
        if initial_count > 0:
            print("Wiping database...")
            session.run("MATCH (n) DETACH DELETE n")
            
            # Verify
            result = session.run("MATCH (n) RETURN count(n) as count")
            final_count = result.single()['count']
            print(f"Post-wipe count: {final_count}")
        else:
            print("Database is already empty.")
            
    driver.close()
    print("Cleanup complete.")
except Exception as e:
    print(f"Error during Neo4j cleanup: {e}")
    print("\nIf authentication failed, please set NEO4J_PASSWORD in your environment.")
