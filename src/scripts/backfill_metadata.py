"""
scripts/backfill_metadata.py
============================
One-time script to fix existing FAISS chunks that have law_title = N/A.

HOW IT WORKS
------------
1. Opens the live FAISS store and calls audit_incomplete() to find bad chunks.
2. For each bad chunk, looks up its source document in Neo4j using the chunk's
   _id or doc_id field to find the parent Document node, then reads
   law_title and section from there.
3. Patches the FAISS metadata record in-place using patch_metadata().
4. Saves the FAISS store once at the end (not after every record).
5. Prints a summary so you know what was fixed and what still needs work.

USAGE
-----
    python src/scripts/backfill_metadata.py
    python src/scripts/backfill_metadata.py --dry-run      # preview only, no writes
    python src/scripts/backfill_metadata.py --audit-only   # just count bad records

ENVIRONMENT VARIABLES
---------------------
    NEO4J_URI       bolt://localhost:7687
    NEO4J_USER      neo4j
    NEO4J_PASSWORD  password
    FAISS_DIR       ./data_processed/faiss_index_unified
"""

import os
import sys
import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

# ── path setup ───────────────────────────────────────────────────────────────
# Ensure repo `src/` is importable regardless of CWD.
# File is `src/scripts/backfill_metadata.py` → repo src dir is 2 levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_SRC_DIR))
load_dotenv(REPO_ROOT / ".env")

from data_pipeline.indexing.faiss_store import FAISSStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill")


# ── Neo4j lookup ─────────────────────────────────────────────────────────────

def get_neo4j_driver(uri: str, user: str, password: str, database: str = "neo4j"):
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver._gl_database = database  # noqa: SLF001 — attach for session()
        return driver
    except Exception as e:
        log.error("Cannot connect to Neo4j: %s", e)
        return None


def _neo4j_session(driver):
    database = getattr(driver, "_gl_database", os.environ.get("NEO4J_DATABASE", "neo4j"))
    return driver.session(database=database)


def lookup_chunk_in_neo4j(
    driver,
    chunk_id: str,
    doc_id: str | None = None,
    faiss_row_id: str | None = None,
    faiss_index: int | None = None,
) -> dict:
    """
    Query Neo4j for a Chunk node matching chunk_id.
    Returns a dict with law_title and section, or empty dict if not found.

    Adjust the Cypher query to match your actual node labels and property names.
    """
    cypher = """
        MATCH (c:Chunk {chunk_id: $chunk_id})
        OPTIONAL MATCH (c)-[:BELONGS_TO]->(d:Document)
        RETURN
            coalesce(c.law_title, d.law_title, d.title, d.name)  AS law_title,
            coalesce(c.section,   c.section_id, c.section_code)  AS section
        LIMIT 1
    """
    try:
        with _neo4j_session(driver) as session:
            record = session.run(cypher, chunk_id=chunk_id).single()
            if record and record["law_title"] and record["law_title"] != "N/A":
                return {
                    "law_title": record["law_title"] or "N/A",
                    "section":   record["section"]   or "N/A",
                }

            if faiss_index is not None:
                record = session.run(
                    """
                    MATCH (c:Chunk {chunk_id: $chunk_id})
                    OPTIONAL MATCH (c)-[:BELONGS_TO]->(d:Document)
                    RETURN
                        coalesce(d.title, d.name, c.law_title, c.document_id) AS law_title,
                        coalesce(c.section, c.section_id, 'unknown') AS section
                    LIMIT 1
                    """,
                    chunk_id=f"faiss_unified_{faiss_index}",
                ).single()
                if record and record["law_title"] and record["law_title"] != "N/A":
                    return {
                        "law_title": record["law_title"] or "N/A",
                        "section":   record["section"]   or "N/A",
                    }

            if faiss_row_id:
                record = session.run(
                    """
                    MATCH (c:Chunk)
                    WHERE c.faiss_row_id = $fid OR c.chunk_id = $fid
                    OPTIONAL MATCH (c)-[:BELONGS_TO]->(d:Document)
                    RETURN
                        coalesce(d.title, d.name, c.law_title, c.document_id) AS law_title,
                        coalesce(c.section, c.section_id, 'unknown') AS section
                    LIMIT 1
                    """,
                    fid=faiss_row_id,
                ).single()
                if record and record["law_title"] and record["law_title"] != "N/A":
                    return {
                        "law_title": record["law_title"] or "N/A",
                        "section":   record["section"]   or "N/A",
                    }

            # FAISS uses chunk_0_<hash> ids; Neo4j often uses CHNK_doc_* — join on doc_id.
            if doc_id:
                doc_cypher = """
                    MATCH (c:Chunk)
                    WHERE c.document_id = $doc_id OR c.law_title = $doc_id
                    OPTIONAL MATCH (c)-[:BELONGS_TO]->(d:Document)
                    RETURN
                        coalesce(d.title, d.name, c.law_title, $doc_id) AS law_title,
                        coalesce(c.section, c.section_id, 'unknown') AS section
                    LIMIT 1
                """
                record = session.run(doc_cypher, doc_id=doc_id).single()
                if record:
                    return {
                        "law_title": record["law_title"] or "N/A",
                        "section":   record["section"]   or "N/A",
                    }
    except Exception as e:
        log.warning("Neo4j lookup failed for chunk %s: %s", chunk_id, e)
    return {}


# ── Heuristic fallback (if Neo4j can't help) ─────────────────────────────────

def heuristic_law_title(meta: dict) -> str:
    """
    Try to derive law_title from other fields already in the metadata.
    Extend this dict as you learn your actual document naming conventions.
    """
    doc_id = meta.get("doc_id", "") or meta.get("source", "") or ""
    KNOWN_PREFIXES = {
        "DOC_20260214_100316": "KPK Forest Ordinance 2002",
        "DOC_20260214_100126": "KPK Forest Rules 2002",
        "DOC_20260214_101828": "KPK Forest Act 2002",
        "DOC_20260214_144443": "Punjab Forest Rules",
        "DOC_20260215_231941": "Forest Act 1927",
    }
    for prefix, title in KNOWN_PREFIXES.items():
        if prefix in doc_id:
            return title
    return "N/A"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backfill law_title/section in FAISS metadata")
    parser.add_argument("--dry-run",    action="store_true", help="Preview changes, do not write")
    parser.add_argument("--audit-only", action="store_true", help="Just count incomplete records")
    parser.add_argument(
        "--faiss-dir",
        default=None,
        help="FAISS persist directory (overrides FAISS_DIR env var).",
    )
    args = parser.parse_args()

    # Default matches the repository's standard output location.
    faiss_dir = args.faiss_dir or os.environ.get("FAISS_DIR", "./data_processed/faiss_index_unified")
    neo4j_uri = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER",    "neo4j")
    neo4j_pass = os.environ.get("NEO4J_PASSWORD", "password")
    neo4j_db   = os.environ.get("NEO4J_DATABASE", "neo4j")

    log.info("Neo4j target: %s  database=%s  user=%s", neo4j_uri, neo4j_db, neo4j_user)

    # ── Load FAISS store ──────────────────────────────────────────────────────
    log.info("Loading FAISS store from: %s", faiss_dir)
    store = FAISSStore(persist_directory=faiss_dir)

    stats = store.get_stats()
    log.info("Total chunks: %d   Incomplete: %d",
             stats["total_documents"], stats["incomplete_chunks"])

    incomplete = store.audit_incomplete()
    if not incomplete:
        log.info("No incomplete records found — nothing to backfill.")
        return

    log.info("Found %d incomplete chunks to patch.", len(incomplete))

    if args.audit_only:
        print("\n-- AUDIT RESULTS ------------------------------------------------")
        for m in incomplete[:50]:           # cap output at 50
            print(f"  id={m.get('_id')}  doc_id={m.get('doc_id', '?')}  "
                  f"text={m.get('text','')[:60]}")
        if len(incomplete) > 50:
            print(f"  ... and {len(incomplete) - 50} more.")
        return

    # ── Connect to Neo4j ──────────────────────────────────────────────────────
    driver = get_neo4j_driver(neo4j_uri, neo4j_user, neo4j_pass, database=neo4j_db)
    if not driver:
        log.warning("Neo4j unavailable — will use heuristic fallback only.")

    # ── Patch loop ────────────────────────────────────────────────────────────
    fixed       = 0
    heuristic   = 0
    still_bad   = 0

    for meta in incomplete:
        faiss_id      = meta.get("_id", "")
        source_doc_id = meta.get("doc_id")
        faiss_index   = meta.get("_index")
        chunk_id      = meta.get("chunk_id") or source_doc_id or faiss_id

        # Try Neo4j first
        updates = (
            lookup_chunk_in_neo4j(
                driver,
                chunk_id,
                doc_id=source_doc_id,
                faiss_row_id=faiss_id,
                faiss_index=faiss_index,
            )
            if driver
            else {}
        )

        # Fall back to heuristic if Neo4j returned nothing useful
        if not updates or updates.get("law_title") == "N/A":
            guessed_title = heuristic_law_title(meta)
            if guessed_title != "N/A":
                updates = {
                    "law_title": guessed_title,
                    "section":   updates.get("section", meta.get("section", "N/A")),
                }
                heuristic += 1

        if not updates or updates.get("law_title") == "N/A":
            log.debug("No fix found for chunk %s", faiss_id)
            still_bad += 1
            continue

        log.info("  %s %s  ->  law_title='%s'  section='%s'",
                 "[DRY-RUN]" if args.dry_run else "PATCH",
                 faiss_id,
                 updates.get("law_title"),
                 updates.get("section"))

        if not args.dry_run:
            store.patch_metadata(faiss_id, updates)
            fixed += 1

    # ── Final save (one write, not one per record) ────────────────────────────
    if not args.dry_run and fixed > 0:
        store.save()
        log.info("FAISS store saved.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n-- BACKFILL SUMMARY ------------------------------------------------")
    print(f"  Total incomplete records  : {len(incomplete)}")
    print(f"  Fixed via Neo4j           : {fixed - heuristic}")
    print(f"  Fixed via heuristic       : {heuristic}")
    print(f"  Still N/A (no source)     : {still_bad}")
    if args.dry_run:
        print("  (DRY-RUN — no changes were written)")
    print("--------------------------------------------------------------------")

    if still_bad:
        print(
            "\n[ACTION NEEDED] Some chunks could not be resolved.\n"
            "Fix 6.3_graph_builder.py so new documents always carry\n"
            "law_title + section before calling add_documents().\n"
        )


if __name__ == "__main__":
    main()