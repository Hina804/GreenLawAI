import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(src_path))
print(f"DEBUG: src_path = {src_path}")

from intent.classifier import IntentClassifier

def test_classifier():
    classifier = IntentClassifier()
    
    test_queries = [
        "What is the penalty for cutting Deodar trees under Section 33?",
        "Tell me about carbon sequestration in Chir pine forests.",
        "Show me recent illegal logging patterns in Hazara district.",
        "How do I apply for a timber permit?",
        "Hello, can you help me?"
    ]
    
    for query in test_queries:
        result = classifier.classify(query)
        print(f"Query: {query}")
        print(f"Primary Intent: {result['primary_intent']} (Conf: {result['confidence']})")
        print(f"Possible: {result['possible_intents']}")
        print(f"Entities: {result['entities']}")
        print("-" * 30)

if __name__ == "__main__":
    test_classifier()
