import sys
import os
import numpy as np
import json
import shutil

# Must be run from e:\GL_AI\src\ as working directory
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # e:\GL_AI\src
BASE_DIR = os.path.dirname(SRC_ROOT)                                      # e:\GL_AI
DATA_PIPELINE_INDEX = os.path.join(SRC_ROOT, "data_pipeline", "indexing")

# SRC_ROOT first so 'data.court_schema' and 'data.case_generator' resolve
sys.path.insert(0, DATA_PIPELINE_INDEX)
sys.path.insert(0, SRC_ROOT)

from data.case_generator import generate_mock_cases
from data.case_ingestor import CaseIngestor
from faiss_store import FAISSStore
from embedding_generator import EmbeddingGenerator


def main():
    print("=" * 55)
    print("STEP 1: Generating 30 diverse court cases...")
    print("=" * 55)

    cases = generate_mock_cases(30)

    offense_dist = {}
    verdict_dist = {}
    sentence_count = 0
    for c in cases:
        offense_dist[c.offense_category] = offense_dist.get(c.offense_category, 0) + 1
        verdict_dist[c.verdict] = verdict_dist.get(c.verdict, 0) + 1
        if c.imprisonment_months > 0:
            sentence_count += 1

    print(f"\nGenerated {len(cases)} cases:")
    print(f"  Offense Distribution : {offense_dist}")
    print(f"  Verdict Distribution : {verdict_dist}")
    print(f"  Cases with Sentence  : {sentence_count}")

    output_dir = os.path.join(SRC_ROOT, "data", "court_cases", "processed")
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, "mock_cases.json")
    with open(out_file, "w") as f:
        json.dump([c.model_dump() for c in cases], f, indent=2)
    print(f"\nSaved to {out_file}")

    print("\n" + "=" * 55)
    print("STEP 2: Preparing FAISS vector chunks...")
    print("=" * 55)
    ingestor = CaseIngestor(data_dir=output_dir)
    ingestor.cases = cases
    chunks = ingestor.process_for_vector_db()
    print(f"Prepared {len(chunks)} chunks")

    print("\n" + "=" * 55)
    print("STEP 3: Ingesting into FAISS vector store...")
    print("=" * 55)
    faiss_path = os.path.join(BASE_DIR, "faiss_index_cases")
    print(f"FAISS path: {faiss_path}")

    embedder = EmbeddingGenerator()

    if os.path.exists(faiss_path):
        shutil.rmtree(faiss_path)
        print("Cleared old FAISS index.")

    store = FAISSStore(persist_directory=faiss_path, collection_name="court_cases")

    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    ids = [c["id"] for c in chunks]

    print(f"Encoding {len(texts)} texts...")
    vectors = embedder.encode(texts, show_progress=True)
    store.add_documents(vectors, metadatas, ids)

    print(f"\nSuccessfully ingested {len(chunks)} cases into FAISS!")
    print(f"Total vectors now: {store.index.ntotal}")


if __name__ == "__main__":
    main()
