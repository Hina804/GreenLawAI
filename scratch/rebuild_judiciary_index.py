import os
import sys
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from data_pipeline.indexing.embedding_generator import EmbeddingGenerator
from data_pipeline.indexing.faiss_store import FAISSStore

def rebuild_index():
    index_path = "e:/GL_AI/faiss_index_cases"
    
    # 1. Initialize Components
    embedder = EmbeddingGenerator()
    store = FAISSStore(persist_directory=index_path, collection_name="court_cases")
    
    # 2. Define High-Quality Mock Data
    precedents = [
        {
            "case_id": "KPK-2024-012",
            "title": "Govt of KPK vs. ABC Logging Ltd",
            "citation": "2024 CLC 12",
            "court_level": "High Court",
            "court_name": "Peshawar High Court",
            "verdict": "Guilty",
            "penalty_amount_rs": 1500000,
            "imprisonment_months": 0,
            "is_night_violation": False,
            "trees_cut": 45,
            "offense_details": "Corporate trespassing into protected Scrub forest area for illegal timber extraction.",
            "text": "In the matter of Govt of KPK vs. ABC Logging Ltd (2024 CLC 12), the High Court found the company guilty of corporate trespassing in a protected forest. The offense involved the illegal extraction of timber, though not at night. A penalty of Rs 1.5 million was imposed."
        },
        {
            "case_id": "KPK-2022-088",
            "title": "Malik Safdar vs. Forest Dept",
            "citation": "2022 SCMR 88",
            "court_level": "Supreme Court",
            "court_name": "Supreme Court of Pakistan",
            "verdict": "Acquitted",
            "penalty_amount_rs": 0,
            "imprisonment_months": 0,
            "is_night_violation": False,
            "trees_cut": 2,
            "offense_details": "Vindication of subsistence firewood collection under section 4 rights for local tribes (Usage Rights > Statute).",
            "text": "In Malik Safdar vs. Forest Dept (2022 SCMR 88), the Supreme Court acquitted the petitioner. The court ruled that collection of firewood for subsistence by local tribes within their traditional usage rights does not constitute illegal logging under the Forest Act 1927."
        },
        {
            "case_id": "KPK-2023-001",
            "title": "State vs. Akram Khan (Timber Smuggling)",
            "citation": "2023 PLD 442",
            "court_level": "Supreme Court",
            "court_name": "Supreme Court of Pakistan",
            "verdict": "Guilty",
            "penalty_amount_rs": 250000,
            "imprisonment_months": 24,
            "is_night_violation": True,
            "trees_cut": 12,
            "offense_details": "Illegal harvesting of Deodar trees during night-shift trespassing in Kalam Forest.",
            "text": "In State vs. Akram Khan (2023 PLD 442), the Supreme Court upheld the conviction for timber smuggling. The accused was found guilty of illegal harvesting of Deodar trees during a night-shift trespassing operation in the reserved Kalam Forest. Sentenced to 24 months imprisonment and Rs 250,000 fine."
        }
    ]
    
    # 3. Encode and Add
    print(f"\nRebuilding index with {len(precedents)} precedents...")
    
    texts = [p["text"] for p in precedents]
    embeddings = embedder.encode(texts)
    
    # Add to store
    store.add_documents(embeddings, precedents)
    
    print(f"\n[OK] Index rebuilt at {index_path}")
    print(f"Total vectors: {store.index.ntotal}")

if __name__ == "__main__":
    rebuild_index()
