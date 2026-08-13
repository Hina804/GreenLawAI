"""
Re-import Neo4j :Chunk nodes from unified FAISS export.

Safe for data_processed: only READS faiss_index_unified, WRITES a new JSON at repo root,
then loads into Neo4j. Does not modify phase_6 folders under documents/ or new_documents/.

Typical flow:
  1. python scripts/export_unified_faiss_for_neo4j.py
  2. python scripts/reimport_neo4j_unified.py --wipe-chunks
  3. python scripts/_neo4j_chunk_audit.py   # verify ~13357 chunks
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "src"))

from data_pipeline.indexing.neo4j_import import (  # noqa: E402
    create_constraints,
    import_chunks,
    import_entities,
)

DEFAULT_EXPORT = ROOT / "chunks_export_unified.json"
DEFAULT_ENTITIES = ROOT / "entity_registry.json"


def wipe_chunks(session) -> None:
    """Remove existing chunk layer so counts match unified FAISS exactly."""
    print("Wiping existing :Chunk nodes (and orphan :Clause nodes) ...")
    session.run("MATCH (c:Chunk) DETACH DELETE c")
    session.run(
        """
        MATCH (cl:Clause)
        WHERE NOT (cl)<-[:CONTAINS_CLAUSE]-()
        DELETE cl
        """
    )
    remaining = session.run("MATCH (c:Chunk) RETURN count(c) AS n").single()["n"]
    print(f"  Remaining :Chunk nodes: {remaining}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import unified FAISS chunks into Neo4j")
    parser.add_argument(
        "--chunks-export",
        type=Path,
        default=DEFAULT_EXPORT,
        help="Path to chunks_export_unified.json",
    )
    parser.add_argument(
        "--entity-registry",
        type=Path,
        default=DEFAULT_ENTITIES,
        help="Optional entity_registry.json (skip with --skip-entities)",
    )
    parser.add_argument(
        "--wipe-chunks",
        action="store_true",
        help="Delete all :Chunk nodes before import (recommended)",
    )
    parser.add_argument(
        "--skip-entities",
        action="store_true",
        help="Only import chunks, not entities",
    )
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    if not args.chunks_export.exists():
        print(f"[FAIL] Export not found: {args.chunks_export}")
        print("Run first:  python scripts/export_unified_faiss_for_neo4j.py")
        return 1

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    # Prefer bolt:// for single-instance Desktop (neo4j:// needs routing)
    if uri.startswith("neo4j://"):
        bolt_uri = "bolt://" + uri[len("neo4j://") :]
        print(f"Note: using {bolt_uri} (converted from {uri})")
        uri = bolt_uri

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[FAIL] pip install neo4j")
        return 1

    print("=" * 72)
    print("NEO4J UNIFIED CHUNK RE-IMPORT")
    print("=" * 72)
    print(f"  URI       = {uri}")
    print(f"  DATABASE  = {database}")
    print(f"  CHUNKS    = {args.chunks_export}")
    print(f"  WIPE      = {args.wipe_chunks}")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print("  STATUS    = CONNECTED\n")

    with driver.session(database=database) as session:
        create_constraints(session)

        if args.wipe_chunks:
            wipe_chunks(session)

        if not args.skip_entities and args.entity_registry.exists():
            print("\nImporting entities ...")
            import_entities(session, str(args.entity_registry), batch_size=500)
        elif not args.skip_entities:
            print("\n[WARN] entity_registry.json not found — skipping entities")

        print("\nImporting chunks ...")
        import_chunks(session, str(args.chunks_export), batch_size=args.batch_size)

        total = session.run("MATCH (c:Chunk) RETURN count(c) AS n").single()["n"]
        print(f"\n[OK] Neo4j now has {total:,} :Chunk nodes")

    driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
