"""
Demo GraphRAG
Interactive script to test hybrid retrieval.
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from retrieval.graph_rag_retriever import GraphRAGRetriever


def main():
    print("="*60)
    print("INITIALIZING GRAPHRAG...")
    print("="*60)
    
    retriever = GraphRAGRetriever(
        chroma_persist_dir="./chroma_db",
        collection_name="legal_docs"
    )
    
    print("\n✓ Ready! Type a query (or 'exit' to quit).")
    print("-" * 60)
    
    while True:
        query = input("\n🔍 Query: ").strip()
        if query.lower() in ['exit', 'quit']:
            break
        if not query:
            continue
            
        print("\nProcessing...")
        
        # 1. Show extracted entities
        entities = retriever.extract_entities_from_query(query)
        print(f"🏷️  Extracted Entities: {entities}")
        
        # 2. Run Hybrid Search
        results = retriever.hybrid_search(query, k=3)
        
        # 3. Display Results
        print(f"\n🏆 Top {len(results)} Results:")
        for i, res in enumerate(results, 1):
            print(f"\n--- Result {i} ---")
            print(retriever.format_explanation(res))


if __name__ == "__main__":
    main()
