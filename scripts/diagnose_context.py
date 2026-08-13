
import sys
import os
import yaml
from pathlib import Path

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
sys.path.append(src_path)

from retrieval.graph_rag_retriever import GraphRAGRetriever
from indexing.embedding_generator import EmbeddingGenerator
from rag.prompts import build_full_prompt, DEFAULT_SYSTEM_PROMPT

def diagnose_context():
    print("\n🕵️ DIAGNOSING RAG CONTEXT...")
    
    # Initialize Config
    config_path = os.path.join(current_dir, "config", "rag_config.yaml")
    if not os.path.exists(config_path):
        config_path = os.path.join(current_dir, "src", "config", "rag_config.yaml")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Initialize Components
    # embed_service = EmbeddingGenerator() # Not needed for Retriever
    retriever = GraphRAGRetriever(
        neo4j_uri=config['neo4j']['uri'],
        neo4j_user=config['neo4j']['user'],
        neo4j_password=config['neo4j']['password'],
        chroma_persist_dir=config.get('chromadb', {}).get('persist_directory', "./chroma_db_v3")
    )
    
    # Query
    query = "What are the new fines for deforestation?"
    print(f"\n🔍 Query: '{query}'")
    
    # 1. Retrieve Chunks
    results = retriever.hybrid_search(query)
    print(f"\n📥 Retrieved {len(results)} chunks.")
    
    # 2. Check for EKO Content
    eko_found = False
    for i, res in enumerate(results):
        if "Schedule-III" in res['text'] and "2022 Amendment" in res['text']:
            print(f"\n✅ EKO CONTENT FOUND in Chunk {i+1}!")
            print("-" * 40)
            print(res['text'])
            print("-" * 40)
            eko_found = True
            
    if not eko_found:
        print("\n❌ EKO CONTENT MISSING from retrieved chunks!")

    # 3. Build Full Prompt
    full_prompt = build_full_prompt(results, query, system_prompt=DEFAULT_SYSTEM_PROMPT)
    
    print("\n📝 FULL PROMPT SENT TO LLM:")
    print("=" * 60)
    print(full_prompt)
    print("=" * 60)

    # 4. Check System Prompt for Synonym Protocol
    if "SYNONYM AWARE" in DEFAULT_SYSTEM_PROMPT:
        print("\n✅ System Prompt contains SYNONYM AWARE protocol.")
    else:
        print("\n❌ System Prompt MISSING SYNONYM AWARE protocol!")

if __name__ == "__main__":
    diagnose_context()
