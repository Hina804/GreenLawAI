
import os
import sys
from pathlib import Path
from collections import Counter

# Add src to path
src_path = Path('e:/GL_AI/src')
sys.path.insert(0, str(src_path))

from indexing.vector_indexer import VectorIndexer

def check_db_inventory():
    indexer = VectorIndexer(
        chroma_persist_dir='e:/GL_AI/chroma_db',
        collection_name='legal_docs'
    )
    
    collection = indexer.chroma_store.collection
    results = collection.get(include=['metadatas'])
    
    metadatas = results['metadatas']
    print(f"Total chunks in Chroma: {len(metadatas)}")
    
    laws = Counter()
    for meta in metadatas:
        law_title = meta.get('law_title') or meta.get('law') or 'Unknown'
        laws[law_title] += 1
        
    print("\nLaws and chunk counts:")
    for law, count in laws.items():
        print(f"- {law}: {count} chunks")

if __name__ == "__main__":
    check_db_inventory()
