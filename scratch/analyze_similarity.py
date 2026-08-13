import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path

def analyze_similarity():
    corpus_path = Path("e:/GL_AI/scratch/extracted_corpus.json")
    if not corpus_path.exists():
        print("Corpus not found!")
        return

    with open(corpus_path, "r", encoding="utf-8") as f:
        corpus = json.load(f)

    if not corpus:
        print("Corpus is empty!")
        return

    print(f"Analyzing similarity for {len(corpus)} documents...")

    # Extract texts and names
    texts = [doc["text"] for doc in corpus]
    names = [doc["name"] for doc in corpus]
    paths = [doc["path"] for doc in corpus]

    # Vectorize
    vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(texts)

    # Calculate Cosine Similarity
    sim_matrix = cosine_similarity(tfidf_matrix)

    # Threshold for reporting
    THRESHOLD = 0.85
    EXTREME_THRESHOLD = 0.999

    clusters = []
    visited = set()

    for i in range(len(sim_matrix)):
        if i in visited:
            continue
            
        # Find all documents similar to this one
        similar_indices = np.where(sim_matrix[i] > THRESHOLD)[0]
        
        if len(similar_indices) > 1:
            cluster = []
            for idx in similar_indices:
                cluster.append({
                    "name": names[idx],
                    "path": paths[idx],
                    "similarity": float(sim_matrix[i][idx])
                })
                visited.add(idx)
            clusters.append(cluster)

    # Generate Report
    report = {
        "summary": {
            "total_documents_analyzed": len(corpus),
            "clusters_found": len(clusters)
        },
        "clusters": clusters
    }

    output_path = Path("e:/GL_AI/scratch/similarity_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"Analysis complete. Found {len(clusters)} clusters.")
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    analyze_similarity()
