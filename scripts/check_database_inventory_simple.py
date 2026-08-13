
import chromadb
from collections import Counter

def check_db_inventory_simple():
    # Use absolute path for ChromaDB
    persist_dir = r"e:\GL_AI\chroma_db"
    
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_collection(name="legal_docs")
    
    # Get all metadatas
    results = collection.get(include=['metadatas'])
    metadatas = results['metadatas']
    
    print(f"TOTAL_CHUNKS: {len(metadatas)}")
    
    laws = Counter()
    for meta in metadatas:
        # Check different possible metadata keys
        law_title = meta.get('law_title') or meta.get('law') or 'Unknown'
        laws[law_title] += 1
        
    print("\nLAW_INVENTORY:")
    for law, count in laws.items():
        print(f"- {law}: {count} chunks")

if __name__ == "__main__":
    try:
        check_db_inventory_simple()
    except Exception as e:
        print(f"ERROR: {str(e)}")
