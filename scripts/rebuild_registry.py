import json
from pathlib import Path
from datetime import datetime

def rebuild_registry(chunks_path, output_path):
    print(f"Rebuilding registry from {chunks_path}...")
    with open(chunks_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chunks = data.get('chunks', [])
    registry = {
        "entities": [],
        "metadata": {
            "total_entities": 0,
            "total_mentions": 0,
            "generated_at": datetime.now().isoformat()
        }
    }
    
    entity_map = {} # canonical_name -> info
    
    total_mentions = 0
    
    for chunk in chunks:
        mentions = chunk.get('entity_mentions_canonical', [])
        types = chunk.get('entity_types_canonical', [])
        
        # Ensure they are lists
        if isinstance(mentions, str): 
            try: mentions = json.loads(mentions)
            except: mentions = []
        if isinstance(types, str):
            try: types = json.loads(types)
            except: types = []
            
        for i, name in enumerate(mentions):
            if not name: continue
            
            total_mentions += 1
            etype = types[i] if i < len(types) else "UNKNOWN"
            
            if name not in entity_map:
                entity_map[name] = {
                    "canonical_name": name,
                    "entity_type": etype,
                    "frequency": 0,
                    "chunk_count": 0,
                    "chunk_ids": [],
                    "first_seen_doc": chunk.get('law_title', 'unknown'),
                    "last_seen_doc": chunk.get('law_title', 'unknown'),
                    "aliases": [] # We don't have aliases easily available here, but we can live without them for now or add them if they are in meta
                }
            
            entity_map[name]["frequency"] += 1
            if chunk.get('chunk_id') and chunk.get('chunk_id') not in entity_map[name]["chunk_ids"]:
                entity_map[name]["chunk_count"] += 1
                entity_map[name]["chunk_ids"].append(chunk.get('chunk_id'))
            
            entity_map[name]["last_seen_doc"] = chunk.get('law_title', 'unknown')

    # Convert map to list and remove chunk_ids (internal use only)
    for name, info in entity_map.items():
        del info["chunk_ids"]
        registry["entities"].append(info)
        
    registry["metadata"]["total_entities"] = len(registry["entities"])
    registry["metadata"]["total_mentions"] = total_mentions
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] Rebuilt registry with {len(registry['entities'])} entities and {total_mentions} total mentions.")

if __name__ == "__main__":
    rebuild_registry("e:/GL_AI/chunks_export.json", "e:/GL_AI/entity_registry.json")
