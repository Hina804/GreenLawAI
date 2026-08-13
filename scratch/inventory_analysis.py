import os
import hashlib
import json
from pathlib import Path

def get_hash(file_path):
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        return f"Error: {e}"

def inventory_files():
    # Paths
    project_root = Path("e:/GL_AI")
    data_raw_dir = project_root / "data_raw"
    downloads_dir = Path("C:/Users/QURESHI COMP/Downloads")
    desktop_dir = Path("C:/Users/QURESHI COMP/Desktop")
    
    # Manifest
    manifest_path = project_root / "data_processed" / "batch_manifest.json"
    processed_files = {}
    if manifest_path.exists():
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            for doc_id, info in manifest.get("documents", {}).items():
                full_path = project_root / info["file_path"]
                processed_files[str(full_path).lower()] = doc_id

    all_files = []
    
    # Scan directories
    for label, dir_path in [("DATA_RAW", data_raw_dir), ("DOWNLOADS", downloads_dir), ("DESKTOP", desktop_dir)]:
        if not dir_path.exists():
            continue
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(".pdf"):
                    full_path = Path(root) / file
                    file_hash = get_hash(full_path)
                    all_files.append({
                        "label": label,
                        "path": str(full_path),
                        "name": file,
                        "size": full_path.stat().st_size,
                        "hash": file_hash,
                        "is_processed": str(full_path).lower() in processed_files
                    })
    
    # Group by hash to find duplicates
    hash_map = {}
    for f in all_files:
        h = f["hash"]
        if h not in hash_map:
            hash_map[h] = []
        hash_map[h].append(f)
        
    # Analysis
    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    unprocessed_source = [f for f in all_files if f["label"] in ["DOWNLOADS", "DESKTOP"] and not f["is_processed"]]
    
    results = {
        "summary": {
            "total_files": len(all_files),
            "duplicates_count": len(duplicates),
            "unprocessed_source_count": len(unprocessed_source)
        },
        "unprocessed_source": unprocessed_source,
        "duplicates": duplicates
    }
    
    output_path = project_root / "scratch" / "file_inventory_analysis.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Analysis complete. Results saved to {output_path}")

if __name__ == "__main__":
    inventory_files()
