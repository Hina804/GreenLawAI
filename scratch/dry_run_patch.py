import pickle
import sys

metadata_path = r"e:\GL_AI\data_processed\faiss_index_unified\metadata.pkl"

with open(metadata_path, "rb") as f:
    metadata = pickle.load(f)

sys.path.insert(0, "e:/GL_AI")
from patch_index import assign_category

print(f"Total chunks in metadata: {len(metadata)}")

categorized = 0
category_counts = {}

for meta in metadata:
    existing = meta.get("document_category", "")
    # If we force re-categorization of None or uncategorized:
    if not existing or existing == "uncategorized":
        cat = assign_category(meta)
    else:
        cat = existing
    category_counts[cat] = category_counts.get(cat, 0) + 1

print("\nCategory breakdown after dry run assign_category:")
for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
    print(f"  {cat:<25}: {count}")
