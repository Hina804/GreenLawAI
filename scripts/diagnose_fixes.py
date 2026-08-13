"""
Diagnostic: Check the 9 empty FAISS chunks against chunks_export.json
and also check manifest structure for LegalDocument fix.
"""
import json
import pickle
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Load FAISS metadata
with open(ROOT / "faiss_index" / "metadata.pkl", "rb") as f:
    meta = pickle.load(f)

empties = [m for m in meta if not m.get("text", "").strip()]
print(f"Empty chunks in FAISS: {len(empties)}")
empty_ids = set()
for e in empties:
    cid = e.get("chunk_id")
    doc = e.get("document_id")
    sec = e.get("section_id")
    src = e.get("source_file")
    print(f"  chunk_id={cid}  doc={doc}  section={sec}  src={src}")
    empty_ids.add(cid)

# Check chunks_export
with open(ROOT / "chunks_export.json", "r", encoding="utf-8") as f:
    cd = json.load(f)

chunk_list = cd.get("chunks", cd) if isinstance(cd, dict) else cd
export_ids = {c.get("chunk_id") for c in chunk_list}

print("\nAre empty chunk IDs in chunks_export?")
for cid in empty_ids:
    print(f"  {cid}: {'YES' if cid in export_ids else 'NO'}")

# Check manifest structure
with open(ROOT / "data_processed" / "batch_manifest.json", "r", encoding="utf-8") as f:
    m = json.load(f)

docs = m.get("documents", {})
print(f"\nManifest documents type: {type(docs)}")
print(f"Manifest documents count: {len(docs)}")
if isinstance(docs, dict):
    sample_key = list(docs.keys())[0]
    sample_val = docs[sample_key]
    print(f"Sample doc key: {sample_key}")
    print(f"Sample doc val keys: {list(sample_val.keys())}")
