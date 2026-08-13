
import os
import sys
from pathlib import Path

# Add src to path
src_path = Path('e:/GL_AI/src')
sys.path.insert(0, str(src_path))

from indexing.vector_indexer import VectorIndexer

def diagnose_chroma():
    indexer = VectorIndexer(
        chroma_persist_dir='e:/GL_AI/chroma_db',
        collection_name='legal_docs'
    )
    
    # 1. Check count
    count = indexer.collection.count()
    print(f"Total chunks in Chroma: {count}")
    
    # 2. Search for 'Chir'
    print("\nSearching for 'Chir'...")
    results = indexer.query("Chir", n_results=5)
    for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
        print(f"{i+1}. Metadata: {metadata}")
        print(f"   Snippet: {doc[:100]}...")

    # 3. Search for 'Schedule'
    print("\nSearching for 'Schedule'...")
    results = indexer.query("Schedule", n_results=5)
    for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
        print(f"{i+1}. Metadata: {metadata}")
        print(f"   Snippet: {doc[:100]}...")

if __name__ == "__main__":
    diagnose_chroma()
