
import os
import json
import re
from collections import Counter

BASE_DIR = "E:\\GL_AI\\data_processed\\documents"
OUTPUT_FILE = "corpus_perfection_baseline.txt"

STOP_WORDS = {"is", "at", "the", "of", "in", "and", "or", "to", "for", "with", "by", "on", "as", "an", "a", "it", "this", "that"}

def audit_corpus():
    folders = [f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))]
    report = []
    
    print(f"Auditing {len(folders)} documents...")
    
    for folder in folders:
        folder_path = os.path.join(BASE_DIR, folder)
        stats = {"id": folder, "chunks": 0, "entities": 0, "noise_hits": 0, "top_entities": []}
        
        # 1. Chunks Audit
        chunks_file = os.path.join(folder_path, "phase_6", "phase_6_6_4_chunks.json")
        if os.path.exists(chunks_file):
            try:
                with open(chunks_file, "r") as f:
                    chunks = json.load(f)
                    stats["chunks"] = len(chunks)
                    for chunk in chunks:
                        text = chunk.get("chunk_text", "")
                        if "[Page" in text or "file:///" in text:
                            stats["noise_hits"] += 1
            except: pass
            
        # 2. Entities Audit
        entities_file = os.path.join(folder_path, "phase_4", "phase_4_4_2_entities.json")
        if os.path.exists(entities_file):
            try:
                with open(entities_file, "r") as f:
                    data = json.load(f)
                    entities = data.get("validated_entities", [])
                    stats["entities"] = len(entities)
                    
                    # Count stop-word entities
                    stop_hits = 0
                    entity_names = []
                    for e in entities:
                        name = e.get("value", "").lower()
                        entity_names.append(name)
                        if name in STOP_WORDS:
                            stop_hits += 1
                    
                    stats["stop_entity_hits"] = stop_hits
                    stats["top_entities"] = [e[0] for e in Counter(entity_names).most_common(5)]
            except: pass
            
        line = f"[{folder}] Chunks: {stats['chunks']}, Entities: {stats['entities']}, Noise: {stats.get('noise_hits', 0)}, Stop-Entities: {stats.get('stop_entity_hits', 0)}, Top: {stats['top_entities']}"
        print(line)
        report.append(line)
        
    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(report))

if __name__ == "__main__":
    audit_corpus()
