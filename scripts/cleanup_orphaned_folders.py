import os
import json
import shutil
from pathlib import Path

def cleanup_orphaned_folders():
    base_dir = Path("E:/GL_AI/data_processed/documents") # User mentioned new_documents but manifest points to documents usually
    manifest_path = Path("E:/GL_AI/data_processed/batch_manifest_new.json")
    deferred_manifest_path = Path("E:/GL_AI/data_processed/deferred_batch_manifest.json")
    
    successful_names = set()
    
    # Load primary manifest
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            # Assuming manifest is a list of dicts with 'document_name' or similar
            if isinstance(manifest, list):
                for item in manifest:
                    if isinstance(item, dict):
                        name = item.get("document_id") or item.get("name") or item.get("document_name")
                        if name: successful_names.add(name)
            elif isinstance(manifest, dict):
                 # Maybe it's a dict of results
                 for name in manifest.keys():
                     successful_names.add(name)

    # Load deferred manifest
    if deferred_manifest_path.exists():
        with open(deferred_manifest_path, 'r') as f:
            manifest = json.load(f)
            if isinstance(manifest, list):
                for item in manifest:
                    if isinstance(item, dict):
                        name = item.get("document_id") or item.get("name") or item.get("document_name")
                        if name: successful_names.add(name)
            elif isinstance(manifest, dict):
                 for name in manifest.keys():
                     successful_names.add(name)

    print(f"Loaded {len(successful_names)} successful document names from manifests.")
    
    # Scan directory
    if not base_dir.exists():
        print(f"Directory {base_dir} does not exist.")
        return

    orphaned = []
    for folder in base_dir.iterdir():
        if folder.is_dir() and folder.name not in successful_names:
            # Special case: ignore 'graph_exports' or other system folders
            if folder.name in ['graph_exports', 'faiss_index_new', 'logs']:
                continue
            orphaned.append(folder)

    print(f"Found {len(orphaned)} orphaned folders.")
    for folder in orphaned:
        print(f"Deleting orphaned folder: {folder.name}")
        try:
            shutil.rmtree(folder)
        except Exception as e:
            print(f"Failed to delete {folder.name}: {e}")
        
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup_orphaned_folders()
