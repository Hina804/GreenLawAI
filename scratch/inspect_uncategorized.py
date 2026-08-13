import pickle
import sys

metadata_path = r"e:\GL_AI\data_processed\faiss_index_unified\metadata.pkl"

with open(metadata_path, "rb") as f:
    metadata = pickle.load(f)

sys.path.insert(0, "e:/GL_AI")
from patch_index import assign_category, CATEGORY_RULES

uncategorized_chunks = []
for i, meta in enumerate(metadata):
    cat = meta.get("document_category")
    if cat in (None, "uncategorized"):
        uncategorized_chunks.append(meta)

print(f"Total uncategorized/None chunks: {len(uncategorized_chunks)}")

# Print 10 examples
print("\nFirst 10 uncategorized chunks:")
for meta in uncategorized_chunks[:10]:
    law_title = meta.get("law_title")
    doc_id = meta.get("document_id")
    chunk_id = meta.get("chunk_id")
    assigned = assign_category(meta)
    print(f"  law_title: {law_title} | doc_id: {doc_id} | chunk_id: {chunk_id} | re-assigned: {assigned}")
