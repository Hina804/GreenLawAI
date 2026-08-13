"""Independent Neo4j chunk audit — confirm counts and compare to FAISS."""
import os
import pickle
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

try:
    from neo4j import GraphDatabase
except ImportError:
    print("[FAIL] pip install neo4j")
    sys.exit(1)

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")
database = os.getenv("NEO4J_DATABASE", "neo4j")

FAISS_META = ROOT / "data_processed" / "faiss_index_unified" / "metadata.pkl"


def run():
    print("=" * 72)
    print("NEO4J CONNECTION")
    print("=" * 72)
    print(f"  URI      = {uri}")
    print(f"  USER     = {user}")
    print(f"  DATABASE = {database}")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print("  STATUS   = CONNECTED\n")

    with driver.session(database=database) as s:
        # Total nodes / relationships
        total_nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        total_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        print("=" * 72)
        print("DATABASE TOTALS")
        print("=" * 72)
        print(f"  Total nodes         = {total_nodes:,}")
        print(f"  Total relationships = {total_rels:,}")

        # All labels with counts
        print("\n" + "=" * 72)
        print("ALL NODE LABELS (sorted by count)")
        print("=" * 72)
        labels = s.run(
            """
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN label, count(*) AS c
            ORDER BY c DESC
            """
        ).data()
        chunk_like = 0
        for row in labels:
            lbl = row["label"]
            c = row["c"]
            marker = ""
            if "chunk" in lbl.lower() or lbl == "Chunk":
                chunk_like += c
                marker = "  <-- chunk-related"
            print(f"  {lbl:<40} {c:>8,}{marker}")

        # Multiple ways to count Chunk
        print("\n" + "=" * 72)
        print("CHUNK COUNT (multiple queries — should agree)")
        print("=" * 72)
        queries = {
            "MATCH (c:Chunk) RETURN count(c)": "label :Chunk",
            "MATCH (c:Chunk) RETURN count(c) AS c WHERE c.chunk_id IS NOT NULL": "Chunk with chunk_id",
            "MATCH (c) WHERE 'Chunk' IN labels(c) RETURN count(c)": "IN labels(Chunk)",
            "MATCH (c:Chunk) RETURN count(DISTINCT c.chunk_id)": "DISTINCT chunk_id",
        }
        for cypher, desc in queries.items():
            try:
                val = s.run(cypher).single()
                # handle different return keys
                count = list(val.values())[0] if val else 0
                print(f"  {desc:<35} {count:>8,}")
            except Exception as exc:
                print(f"  {desc:<35} ERROR: {exc}")

        # Sample chunk properties
        print("\n" + "=" * 72)
        print("SAMPLE :Chunk PROPERTIES (first 3)")
        print("=" * 72)
        samples = s.run(
            """
            MATCH (c:Chunk)
            RETURN c.chunk_id AS chunk_id,
                   c.document_id AS document_id,
                   c.law_title AS law_title,
                   c.section AS section,
                   c.section_id AS section_id,
                   keys(c) AS prop_keys
            LIMIT 3
            """
        ).data()
        for i, row in enumerate(samples, 1):
            keys = row.pop("prop_keys", [])
            print(f"  [{i}] keys={keys}")
            for k, v in row.items():
                val = str(v)[:80] if v is not None else None
                print(f"       {k} = {val}")

        # Distinct document ids in Neo4j chunks
        print("\n" + "=" * 72)
        print("NEO4J CHUNK DOCUMENT COVERAGE")
        print("=" * 72)
        distinct_docs = s.run(
            """
            MATCH (c:Chunk)
            RETURN count(DISTINCT coalesce(c.document_id, c.law_title)) AS docs
            """
        ).single()["docs"]
        print(f"  Distinct document_id / law_title on :Chunk = {distinct_docs:,}")

        neo_doc_samples = s.run(
            """
            MATCH (c:Chunk)
            RETURN DISTINCT coalesce(c.document_id, c.law_title) AS doc
            ORDER BY doc
            LIMIT 8
            """
        ).data()
        print("  Sample doc ids in Neo4j:")
        for r in neo_doc_samples:
            print(f"    - {r['doc']}")

        # Document nodes
        doc_count = s.run("MATCH (d:Document) RETURN count(d) AS c").single()["c"]
        print(f"\n  :Document nodes = {doc_count:,}")

    driver.close()

    # FAISS comparison
    print("\n" + "=" * 72)
    print("FAISS UNIFIED INDEX COMPARISON")
    print("=" * 72)
    if not FAISS_META.exists():
        print(f"  [SKIP] Not found: {FAISS_META}")
        return

    with open(FAISS_META, "rb") as f:
        meta = pickle.load(f)
    print(f"  FAISS metadata records = {len(meta):,}")

    faiss_doc_ids = {m.get("doc_id") for m in meta if m.get("doc_id")}
    print(f"  Distinct FAISS doc_id values = {len(faiss_doc_ids):,}")
    print("  Sample FAISS doc_ids:")
    for d in sorted(faiss_doc_ids)[:8]:
        print(f"    - {d}")

    # Re-open for overlap check
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database=database) as s:
        overlap = 0
        sample_faiss = sorted(faiss_doc_ids)[:50]
        for doc_id in sample_faiss:
            n = s.run(
                """
                MATCH (c:Chunk)
                WHERE c.document_id = $doc OR c.law_title = $doc
                RETURN count(c) AS n
                """,
                doc=doc_id,
            ).single()["n"]
            if n:
                overlap += 1
        print(f"\n  FAISS doc_ids found in Neo4j (of first 50 checked) = {overlap}/50")

        # Reverse: how many neo4j doc ids appear in faiss?
        neo_docs = [
            r["doc"]
            for r in s.run(
                """
                MATCH (c:Chunk)
                RETURN DISTINCT coalesce(c.document_id, c.law_title) AS doc
                """
            ).data()
        ]
        neo_set = {d for d in neo_docs if d}
        faiss_overlap = len(neo_set & faiss_doc_ids)
        print(f"  Neo4j doc ids also in FAISS = {faiss_overlap:,} / {len(neo_set):,}")

    driver.close()
    print("\n" + "=" * 72)
    print("CONCLUSION")
    print("=" * 72)
    print("  If :Chunk count is ~2953 and FAISS is ~13357, they are different corpora.")
    print("  Overlap near 0 confirms Neo4j was NOT built from faiss_index_unified.")
    print("=" * 72)


if __name__ == "__main__":
    run()
