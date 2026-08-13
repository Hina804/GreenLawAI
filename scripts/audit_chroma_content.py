
import os
import sys
import yaml
import chromadb
from pathlib import Path

# CRITICAL: Set environment variables
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

def audit_chroma():
    print("\n🔍 AUDITING CHROMA DB V3...")
    
    # Paths
    current_dir = os.getcwd()
    persist_dir = os.path.join(current_dir, "chroma_db_v3")
    
    if not os.path.exists(persist_dir):
        print(f"❌ DB directory not found: {persist_dir}")
        return

    # Initialize Chroma
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_collection("legal_docs")
    
    # 1. Get all metadata
    results = collection.get(
        include=["metadatas", "documents"]
    )
    
    metadatas = results['metadatas']
    documents = results['documents']
    ids = results['ids']
    
    print(f"📊 Total chunks in database: {len(ids)}")
    
    # 2. Search for "Section 64"
    print("\n🔎 Searching for 'Section 64' (Arrest Powers)...")
    found_count = 0
    for i, meta in enumerate(metadatas):
        section = str(meta.get('section', ''))
        law = meta.get('law_title', 'Unknown')
        
        if "64" in section:
            found_count += 1
            print(f"✅ Found: {law} - Section {section}")
            print(f"   Snippet: {documents[i][:150]}...")
            print("-" * 40)

    if found_count == 0:
        print("❌ No Section 64 found in the database!")
        
        # Check for other sections around it to see if partitioning failed
        print("\n🔎 Checking for nearby sections (60-70)...")
        for i, meta in enumerate(metadatas):
            section = str(meta.get('section', ''))
            if any(s in section for s in ["60", "61", "62", "63", "65"]):
                print(f"   Near: {meta.get('law_title')} - Section {section}")

if __name__ == "__main__":
    audit_chroma()
