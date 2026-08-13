
import json
import os
import shutil
from datetime import datetime

MANIFEST_PATH = r"e:\GL_AI\data_processed\batch_manifest.json"
DOCS_DIR = r"e:\GL_AI\data_processed\documents"

def clean_workspace():
    with open(MANIFEST_PATH, 'r') as f:
        manifest = json.load(f)

    # Group by file_path
    docs_by_path = {}
    for doc_id, meta in manifest['documents'].items():
        path = meta['file_path']
        if path not in docs_by_path:
            docs_by_path[path] = []
        docs_by_path[path].append((doc_id, meta['timestamp']))

    # Select winners (latest timestamp)
    keep_ids = set()
    print(f"Total unique file paths: {len(docs_by_path)}")
    
    for path, entries in docs_by_path.items():
        entries.sort(key=lambda x: x[1], reverse=True)
        winner_id = entries[0][0]
        keep_ids.add(winner_id)

    print(f"Total documents to keep: {len(keep_ids)}")

    # Scan directory
    all_folders = [d for d in os.listdir(DOCS_DIR) if os.path.isdir(os.path.join(DOCS_DIR, d))]
    
    trash_folders = []
    for folder in all_folders:
        if folder not in keep_ids:
            trash_folders.append(folder)
            print(f"TRASH_FOLDER: {folder}")
            
    # Update manifest
    new_manifest = manifest.copy()
    new_manifest['documents'] = {k: v for k, v in manifest['documents'].items() if k in keep_ids}
    new_manifest['processed_documents'] = len(keep_ids)
    new_manifest['successful_documents'] = len(keep_ids)
    new_manifest['skipped_documents'] = 0
    
    with open(MANIFEST_PATH, 'w') as f:
        json.dump(new_manifest, f, indent=2)
    print("Manifest updated.")

if __name__ == "__main__":
    clean_workspace()
