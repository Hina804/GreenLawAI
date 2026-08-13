import pickle
import os

metadata_path = "e:/GL_AI/faiss_index_cases/metadata.pkl"
if os.path.exists(metadata_path):
    with open(metadata_path, 'rb') as f:
        metadata = pickle.load(f)
    print(f"Total entries: {len(metadata)}")
    if metadata:
        print("Sample metadata keys:", metadata[0].keys())
        print("Sample metadata:", metadata[0])
else:
    print("Metadata file not found.")
