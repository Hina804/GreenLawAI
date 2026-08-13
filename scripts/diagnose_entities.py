
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from indexing.entity_extractor import EntityExtractor

def test_extraction():
    text = "The divisional forest officer shall be responsible for the management of the reserved forest in Peshawar."
    print(f"Testing text: {text}")
    
    extractor = EntityExtractor()
    mentions, types = extractor.extract_entities(text)
    
    print("\nRaw Mentions:")
    for m, t in zip(mentions, types):
        print(f"  {m} ({t})")
    
    if not mentions:
        print("\n[!] No entities extracted!")
    else:
        print(f"\n[OK] Extracted {len(mentions)} entities.")

if __name__ == "__main__":
    test_extraction()
