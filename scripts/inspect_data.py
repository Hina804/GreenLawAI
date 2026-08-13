import json
import pickle
from pathlib import Path

ROOT = Path(__file__).parent.parent

# --- Entity Registry ---
print("=== ENTITY REGISTRY ===")
with open(ROOT / "entity_registry.json", "r", encoding="utf-8") as f:
    data = json.load(f)

top_keys = list(data.keys()) if isinstance(data, dict) else "list"
print(f"Top-level keys: {top_keys}")

entities = data.get("entities", data) if isinstance(data, dict) else data
if isinstance(entities, dict):
    sample = list(entities.values())[:2]
elif isinstance(entities, list):
    sample = entities[:2]
else:
    sample = []

print(f"Total entities: {len(entities)}")
if sample:
    print(f"Keys: {list(sample[0].keys())}")
    print(f"Sample 0: {json.dumps(sample[0], indent=2, ensure_ascii=False)}")

# Noise analysis
noisy = []
good = []
for e in (entities.values() if isinstance(entities, dict) else entities):
    name = e.get("canonical_name", "")
    stripped = name.replace("_", "").replace(" ", "")
    if stripped.isnumeric() or len(stripped) <= 2:
        noisy.append(name)
    else:
        good.append(name)
print(f"\nNoisy entities: {len(noisy)}")
print(f"Clean entities: {len(good)}")
print(f"Sample noisy: {noisy[:10]}")

# --- FAISS Metadata ---
print("\n=== FAISS METADATA ===")
with open(ROOT / "faiss_index" / "metadata.pkl", "rb") as f:
    meta = pickle.load(f)

print(f"Total: {len(meta)}")
empties = [m for m in meta if not m.get("text", "").strip()]
print(f"Empty text chunks: {len(empties)}")
if empties:
    for e in empties[:3]:
        print(f"  - chunk_id: {e.get('chunk_id')}, doc: {e.get('document_id')}, section: {e.get('section_id')}, source: {e.get('source_file')}")
