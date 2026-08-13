
import sys
import os
import yaml
from pathlib import Path

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
sys.path.append(src_path)

from rag.rag_pipeline import RAGPipeline

def test_full_pipeline():
    print("\n🚀 Pillar 4: End-to-End Pipeline Test")
    print("="*60)
    
    # Initialize
    config_path = os.path.join(current_dir, "config", "rag_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
        
    # Override for testing
    os.environ["NEO4J_PASSWORD"] = "bypass_auth"
    
    # We use chroma_db_v3 explicitly
    config['chroma'] = {'persist_dir': 'e:/GL_AI/chroma_db_v3'}
    
    try:
        rag = RAGPipeline.from_config(config)
    except Exception as e:
        print(f"❌ Pipeline Init Failed: {e}")
        return

    questions = [
        "What are the penalties under Section 26 of the Forest Act?",
        "What are the fines for cutting a Deodar tree?", # Should trigger EKO + Vector/Graph
        "How is context determined for climate policy?" # Policy-heavy
    ]

    for q in questions:
        print(f"\n❓ Question: {q}")
        print("-" * 20)
        
        # We use a custom query loop to see the chunks and scores
        chunks = rag.retriever.hybrid_search(q, k=config.get('retrieval', {}).get('top_k', 5))
        
        print(f"🔍 Retrieved {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks, 1):
            scores = chunk.get('scores', {})
            print(f"   {i}. [{chunk['metadata']['law_title']} - {chunk['metadata']['section']}]")
            print(f"      Score: {chunk['final_score']:.3f} (V: {scores.get('vector', 0):.3f}, G: {scores.get('graph', 0):.3f}, O: {scores.get('overlap', 0):.3f})")
        
        # PROMPT DEBUGGING
        from rag.prompts import build_full_prompt
        full_prompt = build_full_prompt(chunks, q)
        print("\n--- DEBUG: RAW PROMPT START ---")
        print(full_prompt)
        print("--- DEBUG: RAW PROMPT END ---\n")

        print("\n🤖 LLM Answer:")
        try:
            for token in rag.query(q, stream=True):
                print(token, end='', flush=True)
            print()
        except Exception as e:
            print(f"\n❌ LLM Error: {e}")

if __name__ == "__main__":
    test_full_pipeline()
