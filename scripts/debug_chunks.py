import json
from pathlib import Path

def analyze_chunks(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chunks = data.get('chunks', [])
    null_chunks = [c for c in chunks if c.get('chunk_id') is None]
    
    print(f"Total chunks: {len(chunks)}")
    print(f"Null chunk_id count: {len(null_chunks)}")
    
    if null_chunks:
        print("\nSample null chunks:")
        for i, c in enumerate(null_chunks[:3]):
            print(f"\nNull Chunk {i+1}:")
            # Print only keys that are NOT null or empty
            sanitized = {k: v for k, v in c.items() if v is not None}
            print(json.dumps(sanitized, indent=2))

if __name__ == "__main__":
    analyze_chunks("e:/GL_AI/chunks_export.json")
