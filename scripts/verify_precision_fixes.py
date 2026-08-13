
import sys
import asyncio
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from retrieval.graph_rag_retriever import GraphRAGRetriever

async def verify_fixes():
    retriever = GraphRAGRetriever()
    
    print("--- 📚 TEST 1: Grazing Penalties ---")
    results = await retriever.hybrid_search("What is the penalty for illegal grazing in a reserved forest?")
    found_grazing = any("grazing" in r['text'].lower() and "Rs. 5,000" in r['text'] for r in results)
    if found_grazing:
        print("✅ PASS: Grazing penalties found in expert knowledge.")
    else:
        print("❌ FAIL: Grazing penalties missing.")

    print("\n--- ⚖️ TEST 2: Historical Comparison (1927 vs 2022) ---")
    results = await retriever.hybrid_search("Compare Deodar fines between 1927 Act and 2022 Amendment")
    found_hist = any("1927" in r['text'] and "2022" in r['text'] and "Rs. 500" in r['text'] for r in results)
    if found_hist:
        print("✅ PASS: Historical comparison data found.")
    else:
        print("❌ FAIL: Historical data missing.")

    print("\n--- 🎯 TEST 3: Section Boosting (Section 2) ---")
    # This might fail if the index doesn't have Section 2, but the EKO has Section 2 for Timber
    results = await retriever.hybrid_search("What is the definition of timber under Section 2?")
    top_result = results[0]
    is_sec_2 = str(top_result.get('metadata', {}).get('section', '')) == '2'
    if is_sec_2:
        print(f"✅ PASS: Top result is Section 2. Title: {top_result['metadata'].get('law_title')}")
    else:
        print(f"❌ FAIL: Top result is NOT Section 2. Found Section {top_result.get('metadata', {}).get('section')}")

if __name__ == "__main__":
    asyncio.run(verify_fixes())
