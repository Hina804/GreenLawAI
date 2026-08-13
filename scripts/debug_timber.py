
import sys
import os
import yaml
from pathlib import Path

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
sys.path.append(src_path)

from retrieval.graph_rag_retriever import GraphRAGRetriever

def debug_timber_scores():
    print("\n[DEBUG] Debugging 'Timber' Definition Query")
    
    config_path = os.path.join(current_dir, "config", "rag_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    os.environ["NEO4J_PASSWORD"] = "bypass_auth"
    config['chroma'] = {'persist_dir': 'e:/GL_AI/chroma_db_v3'}
    
    retriever = GraphRAGRetriever(
        chroma_persist_dir=config['chroma']['persist_dir'],
        neo4j_uri=config['neo4j']['uri'],
        neo4j_user=config['neo4j']['user'],
        neo4j_password=config['neo4j']['password']
    )
    
    query = "what is meant by timber?"
    print(f"\nQuery: '{query}'")
    
    # 1. Check raw vector search first (no boost)
    print("\n--- Raw Vector Search (Top 5) ---")
    raw_vector = retriever.vector_search(query, k=5)
    for i, res in enumerate(raw_vector):
        meta = res.get('metadata', {})
        print(f"{i+1}. [Score: {res['vector_score']:.3f}] {meta.get('law_title')} - Sec {meta.get('section')}")
        print(f"   Role: {meta.get('semantic_role')} | ID: {res['chunk_id']}")
    
    # 2. Check component detection logic
    # Reproduction of logic in hybrid_search
    is_definition_query = any(k in query.lower() for k in ["define", "meaning", "meant by", "what is"])
    print(f"\n[DEBUG] Definition Intent Detected: {is_definition_query}")
    
    # 3. Check final hybrid ranking
    print("\n--- Final Hybrid Search (Top 5) ---")
    results = retriever.hybrid_search(query, k=5)
    for i, res in enumerate(results):
        meta = res.get('metadata', {})
        section = str(meta.get('section', '')).strip()
        sem_role = meta.get('semantic_role', '').lower() if meta.get('semantic_role') else ''
        
        # Check if boost condition met
        should_boost = (sem_role == 'definition' or section == '2')
        
        print(f"{i+1}. [Final: {res['final_score']:.3f}] {meta.get('law_title')} - Sec {section}")
        print(f"   V: {res['scores']['vector']:.3f} | G: {res['scores']['graph']:.3f}")
        print(f"   Role: '{sem_role}' | Section: '{section}' | Should Boost: {should_boost}")

if __name__ == "__main__":
    debug_timber_scores()
