import os
import sys
import numpy as np
import faiss

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from data_pipeline.indexing.embedding_generator import EmbeddingGenerator

def test_similarity():
    embedder = EmbeddingGenerator()
    
    text1 = "Illegal logging of Himalayan Deodar at night in a reserved forest area"
    text2 = "Illegal harvesting of Deodar trees during night-shift trespassing in Kalam Forest."
    
    v1 = embedder.encode_single(text1).reshape(1, -1).astype('float32')
    v2 = embedder.encode_single(text2).reshape(1, -1).astype('float32')
    
    print(f"V1 norm: {np.linalg.norm(v1)}")
    print(f"V2 norm: {np.linalg.norm(v2)}")
    
    faiss.normalize_L2(v1)
    faiss.normalize_L2(v2)
    
    print(f"V1 norm (after): {np.linalg.norm(v1)}")
    print(f"V2 norm (after): {np.linalg.norm(v2)}")
    
    # Cosine Similarity via Dot Product
    cos_sim = np.dot(v1, v2.T)[0][0]
    print(f"Cosine Similarity (Dot): {cos_sim}")
    
    # Distance from FAISS
    index = faiss.IndexFlatL2(384)
    index.add(v2)
    dist, idx = index.search(v1, 1)
    d = dist[0][0]
    print(f"FAISS L2 Squared Distance: {d}")
    
    # Formula check
    sim_from_dist = 1 - (d / 2)
    print(f"Similarity from Distance (1 - d/2): {sim_from_dist}")

if __name__ == "__main__":
    test_similarity()
