
import json
import os
import shutil

MANIFEST_PATH = r"e:\GL_AI\data_processed\batch_manifest.json"
DOCS_DIR = r"e:\GL_AI\data_processed\documents"

def clean_workspace():
    with open(MANIFEST_PATH, 'r') as f:
        manifest = json.load(f)

    # 1. Group by file_path
    docs_by_path = {}
    for doc_id, meta in manifest['documents'].items():
        path = meta['file_path']
        if path not in docs_by_path:
            docs_by_path[path] = []
        docs_by_path[path].append((doc_id, meta['timestamp']))

    # 2. Determine Survivors
    final_keep_ids = set()
    
    for path, entries in docs_by_path.items():
        # Sort by timestamp desc (Newest first)
        entries.sort(key=lambda x: x[1], reverse=True)
        
        # Find the best candidate that actually exists
        winner_id = None
        for doc_id, ts in entries:
            doc_path = os.path.join(DOCS_DIR, doc_id)
            if os.path.exists(doc_path):
                winner_id = doc_id
                # print(f"Found existing version for {os.path.basename(path)}: {winner_id}")
                break
            else:
                pass
                # print(f"Newest version missing: {doc_id}")
        
        if winner_id:
            final_keep_ids.add(winner_id)
        else:
            print(f"WARNING: No version found on disk for {path}")

    print(f"Total documents to keep (that exist on disk): {len(final_keep_ids)}")

    # 3. Cleanup
    all_folders = [d for d in os.listdir(DOCS_DIR) if os.path.isdir(os.path.join(DOCS_DIR, d))]
    
    trash_count = 0
    for folder in all_folders:
        if folder not in final_keep_ids:
            trash_count += 1
            target = os.path.join(DOCS_DIR, folder)
            print(f"Deleting extraction spam: {target}")
            try:
                shutil.rmtree(target, ignore_errors=True)
            except Exception as e:
                print(f"Failed to delete {target}: {e}")
            
    print(f"Deleted {trash_count} folders.")
    
    # 4. Update Manifest (Reflecting REALITY)
    new_manifest = manifest.copy()
    new_manifest['documents'] = {
        k: v for k, v in manifest['documents'].items() 
        if k in final_keep_ids
    }
    
    # Updates counts
    new_manifest['processed_documents'] = len(final_keep_ids)
    new_manifest['successful_documents'] = len(final_keep_ids) 
    
    with open(MANIFEST_PATH, 'w') as f:
        json.dump(new_manifest, f, indent=2)
    print("Manifest updated to match disk reality.")

if __name__ == "__main__":
    clean_workspace()
