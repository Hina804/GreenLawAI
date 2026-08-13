
import os
import sys
import asyncio
import json
import logging
from pathlib import Path

# Add src to path
sys.path.append(str(Path("e:/GL_AI/src/data_pipeline")))

from preprocessing_pipeline.phase_7_orchestration.batch_processor_v2 import KPKPipelineOrchestrator, PipelineContext
from preprocessing_pipeline.common.config import PipelineConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Reindexer")

async def reindex():
    config = PipelineConfig()
    # Ensure it uses the new index path
    config.faiss_index_path = "E:/GL_AI/data_processed/faiss_index_new"
    
    orchestrator = KPKPipelineOrchestrator(config)
    
    # Load the bottleneck manifest
    manifest_path = Path("e:/GL_AI/data_processed/new_documents/deferred_batch_manifest.json")
    if not manifest_path.exists():
        logger.error("Manifest not found")
        return
        
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    files = manifest.get("files", [])
    logger.info(f"Re-indexing {len(files)} files...")
    
    for file_path in files:
        logger.info(f"Re-indexing: {file_path}")
        try:
            # We use use_dag=True so it loads checkpoints for Phase 1-4
            # It will now correctly load raw_text thanks to our fixes
            # And it will run Phase 6 because we haven't saved Phase 6 success checkpoints yet?
            # Actually, previous run DID save Phase 6 checkpoints but they were empty.
            # I should DELETE Phase 6 checkpoints for these docs first.
            
            doc_id = Path(file_path).stem
            p6_checkpoint = Path("e:/GL_AI/data_preprocessed/checkpoints") / doc_id / f"{doc_id}_6_graph_mapping.json"
            if p6_checkpoint.exists():
                os.remove(p6_checkpoint)
                logger.info(f"Removed empty Phase 6 checkpoint for {doc_id}")
                
            await orchestrator.process_document(file_path, use_dag=True)
        except Exception as e:
            logger.error(f"Failed to re-index {file_path}: {e}")

if __name__ == "__main__":
    asyncio.run(reindex())
