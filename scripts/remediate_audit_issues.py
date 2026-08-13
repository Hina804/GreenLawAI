"""
=============================================================
GREENLAWAI - FULL AUDIT REMEDIATION SCRIPT
=============================================================
Fixes the following issues identified in the audit:

  FIX 1: Entity.type NULL on all Neo4j entity nodes
  FIX 2: Missing LegalDocument nodes in Neo4j (0 of 19)
  FIX 3: 349 noisy entities (pure-numeric / garbage chars)
  FIX 4: 1,135 missing MENTIONS relationships
  FIX 5: first_seen_doc provenance (filename → doc ID)
  FIX 6: 9 FAISS chunks with empty text field

Run:  python scripts/remediate_audit_issues.py
"""

import json
import pickle
import re
import os
import faiss
import numpy as np
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
ENTITY_REGISTRY_PATH = ROOT / "entity_registry.json"
FAISS_DIR = ROOT / "faiss_index"
CHUNKS_EXPORT_PATH = ROOT / "chunks_export.json"
MANIFEST_PATH = ROOT / "data_processed" / "batch_manifest.json"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

def connect_neo4j():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("[OK] Connected to Neo4j.")
    return driver


def load_entity_registry():
    with open(ENTITY_REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def save_entity_registry(data):
    with open(ENTITY_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved cleaned entity_registry.json")


def is_noisy(canonical_name: str) -> bool:
    """Return True if an entity name is pure noise."""
    stripped = canonical_name.replace("_", "").replace(" ", "").replace("-", "")
    if stripped.isnumeric():
        return True
    if len(stripped) <= 2:
        return True
    # OCR garbage: contains only punctuation, bullets, newlines
    if re.fullmatch(r"[\W_]+", canonical_name):
        return True
    return False


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    docs = manifest.get("documents", manifest) if isinstance(manifest, dict) else manifest
    return {d["document_id"]: d for d in docs if "document_id" in d}


# ─────────────────────────────────────────────────────────
# FIX 3: Clean noisy entities from registry
# ─────────────────────────────────────────────────────────

def fix_entity_noise(data: dict) -> dict:
    print("\n" + "="*60)
    print("FIX 3: Removing Noisy Entities from Registry")
    print("="*60)

    entities = data.get("entities", [])
    if isinstance(entities, dict):
        entity_list = list(entities.values())
    else:
        entity_list = entities

    before = len(entity_list)
    clean = [e for e in entity_list if not is_noisy(e.get("canonical_name", ""))]
    removed = before - len(clean)

    print(f"  Before: {before} entities")
    print(f"  Removed (noisy): {removed}")
    print(f"  After: {len(clean)} entities")

    if isinstance(entities, dict):
        # Rebuild dict
        clean_dict = {e["canonical_name"]: e for e in clean}
        data["entities"] = clean_dict
    else:
        data["entities"] = clean

    data["total_unique"] = len(clean)
    return data, clean


# ─────────────────────────────────────────────────────────
# FIX 5: Fix first_seen_doc provenance in registry
# ─────────────────────────────────────────────────────────

def fix_provenance(data: dict, manifest: dict) -> dict:
    print("\n" + "="*60)
    print("FIX 5: Fixing first_seen_doc Provenance")
    print("="*60)

    entities = data.get("entities", {})
    entity_list = list(entities.values()) if isinstance(entities, dict) else entities

    # Build chunk_id → doc_id mapping from chunks_export
    with open(CHUNKS_EXPORT_PATH, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)
    chunk_list = chunks_data.get("chunks", chunks_data) if isinstance(chunks_data, dict) else chunks_data
    chunk_to_doc = {c["chunk_id"]: c.get("document_id", "") for c in chunk_list if "chunk_id" in c}

    fixed = 0
    for e in entity_list:
        chunk_ids = e.get("chunk_ids", [])
        if chunk_ids:
            doc_id = chunk_to_doc.get(chunk_ids[0], "")
            if doc_id and doc_id != e.get("first_seen_doc", ""):
                e["first_seen_doc"] = doc_id
                # Also set source_documents list
                source_docs = set()
                for cid in chunk_ids:
                    d = chunk_to_doc.get(cid, "")
                    if d:
                        source_docs.add(d)
                e["source_documents"] = list(source_docs)
                fixed += 1

    print(f"  Fixed provenance for {fixed} entities")
    return data


# ─────────────────────────────────────────────────────────
# FIX 1: Populate Entity.type in Neo4j
# ─────────────────────────────────────────────────────────

def fix_entity_types_neo4j(driver, entity_list):
    print("\n" + "="*60)
    print("FIX 1: Populating Entity.type in Neo4j")
    print("="*60)

    batch_size = 500
    batches = [entity_list[i:i+batch_size] for i in range(0, len(entity_list), batch_size)]

    total_updated = 0
    with driver.session() as session:
        for i, batch in enumerate(batches):
            params = [
                {"name": e["canonical_name"], "etype": e.get("entity_type", "UNKNOWN")}
                for e in batch
            ]
            result = session.run(
                """
                UNWIND $params AS p
                MATCH (e:Entity {canonical_name: p.name})
                SET e.type = p.etype
                RETURN count(e) AS updated
                """,
                params=params
            )
            count = result.single()["updated"]
            total_updated += count
            print(f"  Batch {i+1}/{len(batches)}: updated {count} entities")

    print(f"[OK] Total Entity.type fields populated: {total_updated}")


# ─────────────────────────────────────────────────────────
# FIX 2: Create LegalDocument nodes in Neo4j
# ─────────────────────────────────────────────────────────

def fix_legal_document_nodes(driver, manifest: dict):
    print("\n" + "="*60)
    print("FIX 2: Creating LegalDocument Nodes in Neo4j")
    print("="*60)

    with driver.session() as session:
        # Create constraint
        session.run(
            "CREATE CONSTRAINT legal_doc_id IF NOT EXISTS "
            "FOR (d:LegalDocument) REQUIRE d.document_id IS UNIQUE"
        )

        created = 0
        linked = 0
        for doc_id, doc_info in manifest.items():
            # Create or merge the LegalDocument node
            result = session.run(
                """
                MERGE (d:LegalDocument {document_id: $doc_id})
                SET d.status = $status,
                    d.file_path = $path,
                    d.created_at = timestamp()
                RETURN d
                """,
                doc_id=doc_id,
                status=doc_info.get("status", "GOLD_STANDARD"),
                path=doc_info.get("phase_4_rules_path", "")
            )
            if result.single():
                created += 1

            # Link to existing Section nodes with HAS_SECTION
            link_result = session.run(
                """
                MATCH (d:LegalDocument {document_id: $doc_id})
                MATCH (s) WHERE (s:Section OR s:GenericNode)
                      AND s.document_id = $doc_id
                MERGE (d)-[:HAS_SECTION]->(s)
                RETURN count(s) AS sections_linked
                """,
                doc_id=doc_id
            )
            rec = link_result.single()
            sections = rec["sections_linked"] if rec else 0
            linked += sections
            print(f"  {doc_id}: created node, linked {sections} sections")

    print(f"[OK] LegalDocument nodes created: {created}")
    print(f"[OK] HAS_SECTION relationships created: {linked}")


# ─────────────────────────────────────────────────────────
# FIX 4: Re-run MENTIONS linking to fill 1,135 gap
# ─────────────────────────────────────────────────────────

def fix_mentions_gap(driver, entity_list):
    print("\n" + "="*60)
    print("FIX 4: Filling MENTIONS Relationship Gap")
    print("="*60)

    # Build all (chunk_id, canonical_name) pairs from entity registry
    pairs = []
    for e in entity_list:
        name = e.get("canonical_name", "")
        for cid in e.get("chunk_ids", []):
            pairs.append({"chunk_id": cid, "entity_name": name})

    print(f"  Total entity-chunk pairs to link: {len(pairs)}")

    batch_size = 500
    batches = [pairs[i:i+batch_size] for i in range(0, len(pairs), batch_size)]
    total_created = 0

    with driver.session() as session:
        for i, batch in enumerate(batches):
            result = session.run(
                """
                UNWIND $pairs AS p
                MATCH (c:Chunk {chunk_id: p.chunk_id})
                MATCH (e:Entity {canonical_name: p.entity_name})
                MERGE (c)-[:MENTIONS]->(e)
                RETURN count(*) AS created
                """,
                pairs=batch
            )
            count = result.single()["created"]
            total_created += count
            print(f"  Batch {i+1}/{len(batches)}: {count} relationships")

    print(f"[OK] Total MENTIONS after re-linking: {total_created}")


# ─────────────────────────────────────────────────────────
# FIX 6: Patch 9 empty-text FAISS chunks
# ─────────────────────────────────────────────────────────

def fix_empty_faiss_chunks():
    print("\n" + "="*60)
    print("FIX 6: Patching Empty-Text FAISS Chunks")
    print("="*60)

    with open(FAISS_DIR / "metadata.pkl", "rb") as f:
        meta = pickle.load(f)

    # Load chunks_export.json to find source text by chunk_id
    with open(CHUNKS_EXPORT_PATH, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)
    chunk_list = chunks_data.get("chunks", chunks_data) if isinstance(chunks_data, dict) else chunks_data
    chunk_text_map = {c["chunk_id"]: c.get("text", "") for c in chunk_list if "chunk_id" in c}

    patched = 0
    skipped = 0
    for m in meta:
        if not m.get("text", "").strip():
            cid = m.get("chunk_id", "")
            source_text = chunk_text_map.get(cid, "").strip()
            if source_text:
                m["text"] = source_text
                patched += 1
                print(f"  Patched: {cid} — {source_text[:60]}...")
            else:
                skipped += 1
                print(f"  SKIPPED (no source): {cid}")

    with open(FAISS_DIR / "metadata.pkl", "wb") as f:
        pickle.dump(meta, f)

    print(f"[OK] Patched: {patched}, Skipped: {skipped}")


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

def main():
    print("="*60)
    print("GREENLAWAI - AUDIT REMEDIATION")
    print("="*60)

    # Load manifest
    manifest = load_manifest()
    print(f"[OK] Loaded manifest: {len(manifest)} documents")

    # Load registry
    data = load_entity_registry()
    print(f"[OK] Loaded entity registry: {data.get('total_unique', 0)} entities")

    # FIX 3: Clean noise
    data, clean_entities = fix_entity_noise(data)

    # FIX 5: Fix provenance
    data = fix_provenance(data, manifest)

    # Save cleaned registry
    save_entity_registry(data)

    # FIX 6: Patch FAISS empty texts
    fix_empty_faiss_chunks()

    # Connect to Neo4j
    driver = connect_neo4j()

    # FIX 1: Populate Entity.type
    fix_entity_types_neo4j(driver, clean_entities)

    # FIX 2: Create LegalDocument nodes
    fix_legal_document_nodes(driver, manifest)

    # FIX 4: Fill MENTIONS gap
    fix_mentions_gap(driver, clean_entities)

    driver.close()

    print("\n" + "="*60)
    print("REMEDIATION COMPLETE")
    print("="*60)
    print("  FIX 1: Entity.type populated in Neo4j     ✅")
    print("  FIX 2: LegalDocument nodes created in Neo4j ✅")
    print("  FIX 3: Noisy entities cleaned from registry ✅")
    print("  FIX 4: MENTIONS relationships re-linked    ✅")
    print("  FIX 5: first_seen_doc provenance fixed     ✅")
    print("  FIX 6: Empty FAISS text chunks patched     ✅")
    print("\nNOTE - FIX 7 (APOC plugin) requires manual install:")
    print("  1. Go to https://github.com/neo4j-contrib/neo4j-apoc-procedures/releases")
    print("  2. Download apoc-X.X.X-core.jar matching your Neo4j version")
    print("  3. Place in C:/Users/<user>/.Neo4jDesktop/.../neo4jDatabases/.../installation/plugins/")
    print("  4. Restart Neo4j")


if __name__ == "__main__":
    main()
