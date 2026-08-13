import os
import sys
import pickle

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

def inspect_faiss():
    index_path = "e:/GL_AI/faiss_index_cases"
    metadata_path = os.path.join(index_path, "metadata.pkl")
    
    if not os.path.exists(metadata_path):
        print(f"Metadata file not found at {metadata_path}")
        return

    try:
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)
        
        print(f"FAISS Index Metadata ({len(metadata)} items):")
        for i, item in enumerate(metadata):
            print(f"- [{i}] Case ID: {item.get('case_id', 'N/A')}, Title: {item.get('title', 'N/A')}")
            
    except Exception as e:
        print(f"Error reading metadata: {e}")

if __name__ == "__main__":
    inspect_faiss()
