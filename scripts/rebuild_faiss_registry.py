import os
import sys
import json
import pickle
import logging
import dataclasses
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

# Define a compatible dataclass for IndexedChunk
from dataclasses import dataclass, field
@dataclass
class IndexedChunk:
    chunk_id: str
    faiss_index_id: int
    neo4j_node_id: str
    text: str
    metadata: dict
    embedding_hash: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def rebuild_registry(linking_json_path: Path, output_pkl_path: Path):
    if not linking_json_path.exists():
        logger.error(f"Linking file not found: {linking_json_path}")
        return

    logger.info(f"Loading linking info from {linking_json_path}")
    with open(linking_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # In neo4j_linking.json, the list is at 'chunk_mapping'
    chunk_mapping = data.get("chunk_mapping", [])
    if not chunk_mapping:
        # Try to see if it's nested or has different key
        logger.warning("No 'chunk_mapping' found in JSON. Checking all keys...")
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0 and "faiss_id" in value[0]:
                logger.info(f"Found mapping list in key: '{key}'")
                chunk_mapping = value
                break
    
    if not chunk_mapping:
        logger.error("Could not find chunk mapping in JSON.")
        return

    logger.info(f"Processing {len(chunk_mapping)} chunks...")
    
    chunk_registry = {}
    neo4j_mapping = {}
    
    for item in chunk_mapping:
        faiss_id = item.get("faiss_id")
        if faiss_id is None: continue
        
        # Convert faiss_id to int if it's a string
        faiss_id = int(faiss_id)
        
        chunk = IndexedChunk(
            chunk_id=item.get("chunk_id", f"chunk_{faiss_id}"),
            faiss_index_id=faiss_id,
            neo4j_node_id=item.get("neo4j_node_id", f"node_{faiss_id}"),
            text="[TEXT_RESTORED_FROM_LINKING_METADATA]", # We don't have full text
            metadata=item.get("metadata", {"restored": True}),
            embedding_hash=item.get("embedding_hash", "0000000000000000")
        )
        
        chunk_registry[faiss_id] = chunk
        
        # Build neo4j_mapping: neo4j_node_id -> List[faiss_ids]
        node_id = chunk.neo4j_node_id
        if node_id not in neo4j_mapping:
            neo4j_mapping[node_id] = []
        neo4j_mapping[node_id].append(faiss_id)

    # Convert to dicts for pickle (to avoid class mismatches during load)
    registry_dicts = {}
    for k, v in chunk_registry.items():
        if dataclasses.is_dataclass(v):
            registry_dicts[k] = dataclasses.asdict(v)
        else:
            registry_dicts[k] = v

    output_data = {
        "chunk_registry": registry_dicts,
        "neo4j_mapping": neo4j_mapping
    }

    logger.info(f"Saving registry with {len(chunk_registry)} chunks to {output_pkl_path}")
    with open(output_pkl_path, 'wb') as f:
        pickle.dump(output_data, f)
    
    logger.info("Rebuild complete!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Rebuild FAISS chunk registry from neo4j_linking.json")
    parser.add_argument("--linking-json", type=str, required=True, help="Path to neo4j_linking.json")
    parser.add_argument("--output-pkl", type=str, required=True, help="Path to output chunk_registry.pkl")
    
    args = parser.parse_args()
    rebuild_registry(Path(args.linking_json), Path(args.output_pkl))
