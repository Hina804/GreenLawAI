
import os
import sys
import yaml
from pathlib import Path

# CRITICAL: Set environment variables
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# Add src to path
current_dir = os.getcwd()
src_path = os.path.join(current_dir, 'src')
sys.path.insert(0, src_path)

from rag.llm_manager import LLMManager
from rag.prompts import build_full_prompt

def test_colab_direct():
    print("\n🧪 TESTING COLAB PROMPT PARSING...")
    
    # Load config
    config_path = os.path.join(current_dir, "config", "rag_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Initialize LLM Manager
    llm = LLMManager.from_config(config)
    
    # Mock Chunks (mimicking EKO)
    mock_chunks = [{
        "chunk_id": "eko_fines",
        "text": "The 2022 Amendment establishes a fine of Rs. 206,000 for cutting Deodar trees.",
        "metadata": {"law_title": "KPK Forest Act 2022", "section": "Schedule-III"},
        "final_score": 1.0
    }]
    
    question = "What are the new fines for deforestation?"
    
    # Build the full prompt (This uses the new markers)
    full_prompt = build_full_prompt(mock_chunks, question)
    
    # Print the prompt we're sending to llm.generate
    print("\n[DEBUG] FULL PROMPT SENT TO LLM MANAGER:")
    print("-" * 40)
    print(full_prompt)
    print("-" * 40)
    
    # Test generation
    print("\n[STEP] Testing LLM.generate...")
    try:
        response = ""
        for token in llm.generate(full_prompt, stream=True):
            print(token, end='', flush=True)
            response += token
        
        print("\n\n✅ GENERATION COMPLETE")
        
    except Exception as e:
        print(f"\n❌ Error during generation: {e}")

if __name__ == "__main__":
    test_colab_direct()
