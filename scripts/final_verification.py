"""
Final verification audit after remediation.
"""
import json
import pickle
import os
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
driver.verify_connectivity()

print("=" * 60)
print("POST-REMEDIATION VERIFICATION AUDIT")
print("=" * 60)

results = {}

with driver.session() as session:

    # 1. Entity.type populated?
    r = session.run("MATCH (e:Entity) WHERE e.type IS NOT NULL RETURN count(e) AS cnt").single()
    typed_entities = r["cnt"]
    r2 = session.run("MATCH (e:Entity) RETURN count(e) AS cnt").single()
    total_entities = r2["cnt"]
    results["Entity.type populated"] = f"{typed_entities}/{total_entities}"
    status1 = "PASS" if typed_entities == total_entities else "FAIL"

    # 2. LegalDocument nodes
    r = session.run("MATCH (d:LegalDocument) RETURN count(d) AS cnt").single()
    legal_docs = r["cnt"]
    results["LegalDocument nodes"] = legal_docs
    status2 = "PASS" if legal_docs == 19 else "FAIL"

    # 3. HAS_SECTION relationships
    r = session.run("MATCH ()-[:HAS_SECTION]->() RETURN count(*) AS cnt").single()
    has_sec = r["cnt"]
    results["HAS_SECTION links"] = has_sec
    status3 = "PASS" if has_sec >= 19 else "WARN"

    # 4. MENTIONS count
    r = session.run("MATCH ()-[:MENTIONS]->() RETURN count(*) AS cnt").single()
    mentions = r["cnt"]
    results["MENTIONS relationships"] = mentions
    status4 = "PASS" if mentions >= 5112 else "FAIL"  # 5112 is clean baseline after noisy entity removal

    # 5. Chunk connectivity
    r = session.run("""
        MATCH (c:Chunk) OPTIONAL MATCH (c)-[:PART_OF_HIERARCHY]->(s)
        RETURN count(c) AS total, count(s) AS linked
    """).single()
    connectivity = round(100.0 * r["linked"] / r["total"], 2) if r["total"] > 0 else 0
    results["Chunk connectivity"] = f"{connectivity}%"
    status5 = "PASS" if connectivity == 100.0 else "FAIL"

    # 6. Orphan chunks
    r = session.run("MATCH (c:Chunk) WHERE NOT (c)-[:PART_OF_HIERARCHY]->() RETURN count(c) AS cnt").single()
    orphans = r["cnt"]
    results["Orphan chunks"] = orphans
    status6 = "PASS" if orphans == 0 else "FAIL"

driver.close()

# 7. Entity registry noise
with open(ROOT / "entity_registry.json", "r", encoding="utf-8") as f:
    data = json.load(f)
entities = data.get("entities", {})
entity_list = list(entities.values()) if isinstance(entities, dict) else entities
noisy = [e for e in entity_list if e.get("canonical_name","").replace("_","").replace(" ","").isnumeric()
         or len(e.get("canonical_name","").replace("_","").replace(" ","")) <= 2]
noise_rate = round(100 * len(noisy) / len(entity_list), 2) if entity_list else 0
results["Entity noise rate"] = f"{noise_rate}% ({len(noisy)} noisy / {len(entity_list)} total)"
status7 = "PASS" if noise_rate < 5 else "FAIL"

# 8. FAISS empty text
with open(ROOT / "faiss_index" / "metadata.pkl", "rb") as f:
    meta = pickle.load(f)
empties = [m for m in meta if not m.get("text", "").strip()]
results["FAISS empty text chunks"] = len(empties)
status8 = "PASS" if len(empties) == 0 else "WARN"

# Print
print(f"\n{'Component':<35} {'Result':<25} {'Status'}")
print("-" * 70)
print(f"{'Entity.type populated':<35} {str(results['Entity.type populated']):<25} {status1}")
print(f"{'LegalDocument nodes':<35} {str(results['LegalDocument nodes']):<25} {status2}")
print(f"{'HAS_SECTION links':<35} {str(results['HAS_SECTION links']):<25} {status3}")
print(f"{'MENTIONS relationships':<35} {str(results['MENTIONS relationships']):<25} {status4}")
print(f"{'Chunk connectivity':<35} {str(results['Chunk connectivity']):<25} {status5}")
print(f"{'Orphan chunks':<35} {str(results['Orphan chunks']):<25} {status6}")
print(f"{'Entity noise rate':<35} {str(results['Entity noise rate']):<25} {status7}")
print(f"{'FAISS empty text chunks':<35} {str(results['FAISS empty text chunks']):<25} {status8}")

all_pass = all(s == "PASS" for s in [status1, status2, status3, status4, status5, status6, status7, status8])
print("\n" + "=" * 60)
print(f"OVERALL: {'PRODUCTION READY' if all_pass else 'NEEDS ATTENTION'}")
print("=" * 60)
