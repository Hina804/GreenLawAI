
import sys
import os
import yaml
from pathlib import Path

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
sys.path.append(src_path)

from rag.rag_pipeline import RAGPipeline
from rag.prompts import build_full_prompt

def isolate_hallucination():
    print("\n🔍 Isolating Forest Act 1978 Hallucination")
    
    config_path = os.path.join(current_dir, "config", "rag_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
        
    os.environ["NEO4J_PASSWORD"] = "bypass_auth"
    config['chroma'] = {'persist_dir': 'e:/GL_AI/chroma_db_v3'}
    
    rag = RAGPipeline.from_config(config)
    q = "What are the penalties under Section 26 of the Forest Act?"
    
    chunks = rag.retriever.hybrid_search(q, k=5)
    full_prompt = build_full_prompt(chunks, q)
    
    # Save prompt to file for full inspection
    with open("e:/GL_AI/debug_hallucination_prompt.txt", "w", encoding="utf-8") as f:
        f.write(full_prompt)
    print(f"\n[OK] Saved raw prompt to e:/GL_AI/debug_hallucination_prompt.txt")
    
    print("\n🤖 Querying LLM...")
    for token in rag.query(q, stream=True):
        print(token, end='', flush=True)
    print()

if __name__ == "__main__":
    isolate_hallucination()
