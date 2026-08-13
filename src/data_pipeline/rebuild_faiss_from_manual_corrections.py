"""
rebuild_faiss_from_manual_corrections.py
Regenerates vector embeddings from manually optimized raw text and section alignments.
"""

import os
import sys
import json
import numpy as np
import logging
from pathlib import Path
import importlib.util

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RebuildFAISS")

# Add src to Python path
sys.path.append(str(Path(__file__).parent.parent))

NEW_DOCS_DIR = Path("E:/GL_AI/data_processed/new_documents")
OUTPUT_DIR = Path("E:/GL_AI/data_processed/faiss_index_new")

# ============================================================
# FIX: Import modules with numeric names using importlib
# ============================================================
def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

base_path = Path("E:/GL_AI/src/data_pipeline/preprocessing_pipeline/phase_6_graph_construction")

legal_chunker_mod = import_from_path("legal_chunker", base_path / "6.4_legal_chunker.py")
embedding_gen_mod = import_from_path("embedding_generator", base_path / "6.5_embedding_generator.py")
faiss_indexer_mod = import_from_path("faiss_indexer", base_path / "6.6_faiss_indexer.py")

LegalChunker = legal_chunker_mod.LegalChunker
KPKEmbeddingGenerator = embedding_gen_mod.KPKEmbeddingGenerator
create_kpk_faiss_indexer = faiss_indexer_mod.create_kpk_faiss_indexer
# ============================================================

def main():
    logger.info("Initializing Legal Chunker & Embedding Generator...")
    chunker = LegalChunker(chunk_size=1000, overlap=100)
    embedder = KPKEmbeddingGenerator(model_name="paraphrase-multilingual-MiniLM-L12-v2")
    
    all_chunks = []
    
    # 1. Scan document directories
    doc_dirs = [d for d in NEW_DOCS_DIR.iterdir() if d.is_dir() and not d.name.startswith((".", "graph_exports"))]
    logger.info(f"Found {len(doc_dirs)} document directories to process.")
    
    for doc_dir in doc_dirs:
        doc_id = doc_dir.name
        phase_3_path = doc_dir / "phase_3" / "phase_3_3_linguistic_alignment.json"
        phase_1_path = doc_dir / "phase_1" / "phase_1_1_extraction.json"
        
        logger.info(f"Processing: {doc_id}")
        
        # Load manually optimized sections if available
        doc_chunks = []
        if phase_3_path.exists():
            logger.info(f"  -> Loading manually aligned sections from phase_3...")
            with open(phase_3_path, "r", encoding="utf-8") as f:
                p3_data = json.load(f)
            
            sections_data = p3_data.get("data", {}).get("sections", {})
            if isinstance(sections_data, dict):
                sections = sections_data.get("sections", [])
            else:
                sections = sections_data
                
            doc_chunks = chunker.create_chunks_from_sections(sections)
            logger.info(f"  -> Generated {len(doc_chunks)} chunks from aligned sections.")
            
        if not doc_chunks and phase_1_path.exists():
            if phase_3_path.exists():
                logger.warning(f"  -> Phase 3 produced 0 chunks! Falling back to raw text from phase_1...")
            else:
                logger.warning(f"  -> Phase 3 missing! Falling back to raw text from phase_1...")
            with open(phase_1_path, "r", encoding="utf-8") as f:
                p1_data = json.load(f)
            
            raw_text = p1_data.get("data", {}).get("raw_text", "")
            doc_metadata = {"document_id": doc_id, "document_type": "Law"}
            doc_chunks = chunker.chunk(raw_text, doc_metadata)
            logger.info(f"  -> Generated {len(doc_chunks)} chunks from raw text.")
            
        if not doc_chunks:
            logger.error(f"  -> Skipping {doc_id}: No chunks generated from phase_1 or phase_3!")
            continue
            
        for chunk in doc_chunks:
            if "metadata" not in chunk:
                chunk["metadata"] = {}
            chunk["metadata"]["document_id"] = doc_id
            chunk["metadata"]["is_kpk_document"] = True
            
        all_chunks.extend(doc_chunks)
        
    if not all_chunks:
        logger.error("No chunks generated! Aborting.")
        return
        
    logger.info(f"Total chunks across all documents: {len(all_chunks)}")
    
    # 2. Generate embeddings
    logger.info("Generating dense embeddings (this may take a few minutes)...")
    embedding_batch = embedder.generate_chunk_embeddings(all_chunks, batch_size=32)
    
    vectors = np.array([e.embedding for e in embedding_batch.embeddings]).astype("float32")
    logger.info(f"Generated embedding matrix shape: {vectors.shape}")
    
    # 3. Index in FAISS
    logger.info("Indexing vectors into KPK FAISS indexer...")
    indexer = create_kpk_faiss_indexer(index_type="FLAT", dimension=384)
    
    indexer_chunks = [{"chunk_id": c["chunk_id"], "text": c["chunk_text"], "metadata": c["metadata"]} for c in all_chunks]
    
    report = indexer.create_and_index(indexer_chunks, vectors)
    
    # 4. Save to disk
    logger.info(f"Saving newly compiled index to {OUTPUT_DIR}...")
    indexer.save(OUTPUT_DIR)
    
    logger.info("Step 1 Complete! ✓")
    logger.info(f"Successfully indexed {report['indexing_summary']['successful']} chunks.")

if __name__ == "__main__":
    main()