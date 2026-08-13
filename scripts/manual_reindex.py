
import os
import sys
import json
import logging
from pathlib import Path
import numpy as np

# Add src to path
sys.path.append(str(Path("e:/GL_AI/src/data_pipeline")))

# Use the package exports
from preprocessing_pipeline.phase_6_graph_construction import FAISSIndexer, LegalChunker, EmbeddingGenerator, FAISSConfig
from preprocessing_pipeline.common.config import PipelineConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ManualReindexer")

def manual_reindex():
    # Use FAISSConfig for the indexer
    faiss_config = FAISSConfig()
    faiss_config.index_type = "FLAT"  # Avoid training requirement for small dataset
    indexer = FAISSIndexer(faiss_config)
    indexer.create_index(384) 
    
    # Corrected: EmbeddingGenerator takes model_name as first arg, not config
    embedder = EmbeddingGenerator()
    
    checkpoint_root = Path("e:/GL_AI/data_preprocessed/checkpoints")
    
    # Load manifest
    manifest_path = Path("e:/GL_AI/data_processed/new_documents/deferred_batch_manifest.json")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    results = manifest.get("results", [])
    logger.info(f"Manually indexing {len(results)} files...")
    
    total_chunks = 0
    
    for item in results:
        file_path = item.get("file")
        if not file_path: continue
        
        doc_id = Path(file_path).stem
        logger.info(f"Processing {doc_id}...")
        
        # Load OCR checkpoint for raw text
        ocr_path = checkpoint_root / doc_id / f"{doc_id}_1_ocr.json"
        if not ocr_path.exists():
            logger.warning(f"No OCR checkpoint for {doc_id}")
            continue
            
        with open(ocr_path, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
            # Handle the nested structure
            inner_data = ocr_data.get('data', {})
            raw_text = inner_data.get('data', {}).get('raw_text', "")
            
        if not raw_text:
            logger.warning(f"No raw text found for {doc_id}")
            continue
            
        # Chunk the text
        chunker = LegalChunker(chunk_size=1000, overlap=100)
        chunks = chunker.chunk(raw_text, doc_metadata={"file_name": doc_id, "document_id": doc_id})
        
        if not chunks:
            logger.warning(f"No chunks created for {doc_id}")
            continue
            
        # Generate embeddings
        texts = [c["chunk_text"] for c in chunks]
        embeddings_list = embedder.generate(texts)
        embeddings = np.array(embeddings_list).astype('float32')
        
        # Index
        indexer.add_vectors(embeddings, chunks)
        total_chunks += len(chunks)
        logger.info(f"Indexed {len(chunks)} chunks for {doc_id}")
        
    # Save index
    save_path = "E:/GL_AI/data_processed/faiss_index_new"
    print(f"DEBUG: chunk_registry size before save = {len(indexer.chunk_registry)}")
    indexer.save_index(save_path)
    logger.info(f"Re-indexing complete. Total chunks indexed: {total_chunks}")

if __name__ == "__main__":
    manual_reindex()
