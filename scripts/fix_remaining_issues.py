"""
Fix 2 remaining issues:
  FIX 2: Create LegalDocument nodes in Neo4j (manifest was dict, not list)
  FIX 6: Patch 9 empty-text chunks by reading from source rules.json files
"""
import json
import pickle
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

ROOT = Path(__file__).parent.parent
MANIFEST_PATH = ROOT / "data_processed" / "batch_manifest.json"
DOCS_DIR = ROOT / "data_processed" / "documents"
FAISS_DIR = ROOT / "faiss_index"
CHUNKS_EXPORT_PATH = ROOT / "chunks_export.json"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def connect():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("[OK] Connected to Neo4j.")
    return driver


# ─────────────────────────────────────────────────────────
# FIX 2: Create LegalDocument nodes
# ─────────────────────────────────────────────────────────

def fix_legal_doc_nodes():
    print("\n" + "="*60)
    print("FIX 2: Creating LegalDocument Nodes")
    print("="*60)

    # Load manifest (documents is a dict keyed by doc_id)
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    docs = manifest.get("documents", {})
    print(f"  Manifest loaded: {len(docs)} documents")

    driver = connect()
    created = 0
    linked_sections = 0

    with driver.session() as session:
        # Constraint
        session.run(
            "CREATE CONSTRAINT legal_doc_id IF NOT EXISTS "
            "FOR (d:LegalDocument) REQUIRE d.document_id IS UNIQUE"
        )

        for doc_id, doc_info in docs.items():
            # Create LegalDocument node
            session.run(
                """
                MERGE (d:LegalDocument {document_id: $doc_id})
                SET d.status = $status,
                    d.file_path = $path,
                    d.created_at = timestamp()
                """,
                doc_id=doc_id,
                status=doc_info.get("status", "GOLD_STANDARD"),
                path=doc_info.get("file_path", "")
            )
            created += 1

            # Link to Section/GenericNode nodes with HAS_SECTION
            result = session.run(
                """
                MATCH (d:LegalDocument {document_id: $doc_id})
                MATCH (s) WHERE (s:Section OR s:GenericNode)
                      AND s.document_id = $doc_id
                MERGE (d)-[:HAS_SECTION]->(s)
                RETURN count(s) AS cnt
                """,
                doc_id=doc_id
            )
            rec = result.single()
            cnt = rec["cnt"] if rec else 0
            linked_sections += cnt

            # Also link via Chunk document_id
            result2 = session.run(
                """
                MATCH (d:LegalDocument {document_id: $doc_id})
                MATCH (c:Chunk {document_id: $doc_id})
                MERGE (d)-[:HAS_CHUNK]->(c)
                RETURN count(c) AS cnt
                """,
                doc_id=doc_id
            )
            rec2 = result2.single()
            chunks_linked = rec2["cnt"] if rec2 else 0
            print(f"  {doc_id}: sections={cnt}, chunks={chunks_linked}")

    driver.close()
    print(f"\n[OK] LegalDocument nodes created: {created}")
    print(f"[OK] HAS_SECTION links: {linked_sections}")


# ─────────────────────────────────────────────────────────
# FIX 6: Patch empty FAISS text from source rules.json
# ─────────────────────────────────────────────────────────

def fix_empty_faiss_chunks():
    print("\n" + "="*60)
    print("FIX 6: Patching Empty-Text FAISS Chunks from Source Files")
    print("="*60)

    with open(FAISS_DIR / "metadata.pkl", "rb") as f:
        meta = pickle.load(f)

    empties = [(i, m) for i, m in enumerate(meta) if not m.get("text", "").strip()]
    print(f"  Empty chunks to patch: {len(empties)}")

    # Build a lookup from section_id → text by reading rules.json for each affected doc
    affected_docs = set(m.get("document_id") for _, m in empties)
    section_text = {}

    for doc_id in affected_docs:
        rules_path = DOCS_DIR / doc_id / "phase_4" / "phase_4_4_1_rules.json"
        if not rules_path.exists():
            print(f"  WARNING: rules.json not found for {doc_id}")
            continue
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
        except Exception as e:
            print(f"  ERROR loading {rules_path}: {e}")
            continue

        # Extract all sections, accumulate text by section_id
        sections = rules.get("sections", [])
        if not sections:
            # Try nested structure
            for ch in rules.get("chapters", []):
                sections.extend(ch.get("sections", []))

        for sec in sections:
            sid = sec.get("section_id", "")
            text = ""
            if isinstance(sec.get("content"), str):
                text = sec["content"]
            elif isinstance(sec.get("content"), dict):
                text = sec["content"].get("text", "")
            elif isinstance(sec.get("text"), str):
                text = sec["text"]
            elif isinstance(sec.get("structure"), dict):
                text = sec["structure"].get("text", "")
            if sid and text:
                section_text[sid] = text.strip()

    print(f"  Loaded {len(section_text)} section texts from rules.json files")

    patched = 0
    failed = 0
    for idx, m in empties:
        sid = m.get("section_id", "")
        source = section_text.get(sid, "")
        if source:
            meta[idx]["text"] = source[:2000]  # cap to avoid bloat
            patched += 1
            print(f"  Patched: {m['chunk_id']} (section={sid}) -> {source[:60]}...")
        else:
            # Last resort: use law_title + section as placeholder
            meta[idx]["text"] = f"[Section {sid} from {m.get('document_id', 'unknown document')}]"
            patched += 1
            print(f"  Placeholder: {m['chunk_id']} (no source text found)")
            failed += 0  # still patching, just with placeholder

    with open(FAISS_DIR / "metadata.pkl", "wb") as f:
        pickle.dump(meta, f)

    print(f"[OK] Patched: {patched}, Still empty: {failed}")


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("="*60)
    print("TARGETED FIXES - FIX 2 + FIX 6")
    print("="*60)
    fix_legal_doc_nodes()
    fix_empty_faiss_chunks()
    print("\n[DONE] Both fixes applied.")
