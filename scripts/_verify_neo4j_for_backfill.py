"""Quick Neo4j + FAISS alignment check for backfill_metadata.py."""
import os
import pickle
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from neo4j import GraphDatabase  # noqa: E402

FAISS_DIR = ROOT / "data_processed" / "faiss_index_unified"


def main() -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    print("=" * 72)
    print("NEO4J CONFIG (from .env when present)")
    print("=" * 72)
    print(f"  NEO4J_URI       = {uri}")
    print(f"  NEO4J_USER      = {user}")
    print(f"  NEO4J_DATABASE  = {database}")
    print(f"  NEO4J_PASSWORD  = {'*' * len(password) if password else '(empty)'}")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
    except Exception as exc:
        print(f"\n[FAIL] Cannot connect: {exc}")
        return 1

    print("\n[OK] Connected to Neo4j")

    with driver.session(database=database) as session:
        for label in ("Chunk", "DocumentChunk", "Document"):
            count = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]
            print(f"  :{label} count = {count}")

        with_law = session.run(
            """
            MATCH (c:Chunk)
            WHERE c.law_title IS NOT NULL AND c.law_title <> 'N/A'
            RETURN count(c) AS c
            """
        ).single()["c"]
        print(f"  :Chunk with law_title (not N/A) = {with_law}")

        samples = session.run(
            """
            MATCH (c:Chunk)
            RETURN c.chunk_id AS chunk_id, c.law_title AS law_title, c.section AS section
            LIMIT 3
            """
        ).data()
        print("\n  Sample :Chunk nodes:")
        for row in samples:
            print(f"    {row}")

    meta_path = FAISS_DIR / "metadata.pkl"
    if not meta_path.exists():
        print(f"\n[FAIL] FAISS metadata not found: {meta_path}")
        driver.close()
        return 1

    with open(meta_path, "rb") as handle:
        metadata = pickle.load(handle)

    print("\n" + "=" * 72)
    print("FAISS vs NEO4J ID ALIGNMENT")
    print("=" * 72)
    print(f"  FAISS metadata records = {len(metadata)}")

    sample = metadata[0]
    print(f"  Sample FAISS keys = {sorted(sample.keys())[:12]}...")
    chunk_id = sample.get("chunk_id") or sample.get("doc_id") or sample.get("_id")
    print(f"  Sample lookup id = {chunk_id}")

    with driver.session(database=database) as session:
        hit = session.run(
            """
            MATCH (c:Chunk {chunk_id: $chunk_id})
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(d:Document)
            RETURN
                c.chunk_id AS chunk_id,
                coalesce(c.law_title, d.law_title, d.title, d.name) AS law_title,
                coalesce(c.section, c.section_id, c.section_code) AS section
            LIMIT 1
            """,
            chunk_id=chunk_id,
        ).single()
        print(f"  :Chunk lookup (backfill query) = {dict(hit) if hit else None}")

        doc_chunk = session.run(
            """
            MATCH (c:DocumentChunk)
            WHERE c.node_id = $chunk_id OR c.faiss_index_id = $chunk_id
            RETURN c.node_id AS node_id LIMIT 1
            """,
            chunk_id=chunk_id,
        ).single()
        print(f"  :DocumentChunk lookup = {dict(doc_chunk) if doc_chunk else 'not found'}")

    # Spot-check 20 random FAISS ids against :Chunk
    import random

    picks = random.sample(metadata, min(20, len(metadata)))
    matched = 0
    with driver.session(database=database) as session:
        for row in picks:
            cid = row.get("chunk_id") or row.get("doc_id") or row.get("_id")
            found = session.run(
                "MATCH (c:Chunk {chunk_id: $chunk_id}) RETURN c.chunk_id LIMIT 1",
                chunk_id=cid,
            ).single()
            if found:
                matched += 1

    print(f"\n  Random sample :Chunk match rate = {matched}/{len(picks)}")

    # Join via FAISS doc_id -> Neo4j Chunk.document_id or Chunk.law_title
    doc_id = sample.get("doc_id")
    if doc_id:
        with driver.session(database=database) as session:
            by_doc = session.run(
                """
                MATCH (c:Chunk)
                WHERE c.document_id = $doc_id OR c.law_title = $doc_id
                RETURN count(c) AS c
                """,
                doc_id=doc_id,
            ).single()["c"]
            print(f"\n  FAISS doc_id '{doc_id}' -> :Chunk rows = {by_doc}")
            neo4j_docs = session.run(
                """
                MATCH (c:Chunk)
                RETURN DISTINCT coalesce(c.document_id, c.law_title) AS doc
                LIMIT 5
                """
            ).data()
            print("  Sample Neo4j Chunk doc ids:", [r["doc"] for r in neo4j_docs])

    driver.close()
    print("\n" + "=" * 72)
    if matched == 0 and len(picks) > 0:
        print("[WARN] FAISS ids do not match :Chunk {chunk_id} in this Neo4j DB.")
        print("       Backfill will rely on heuristics only unless labels/ids are aligned.")
    elif matched > 0:
        print("[OK] Neo4j :Chunk nodes align with FAISS ids (partial or full).")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
