import os
import json
from pathlib import Path

def cleanup_duplicates():
    analysis_path = Path("e:/GL_AI/scratch/file_inventory_analysis.json")
    if not analysis_path.exists():
        print(f"Error: {analysis_path} not found.")
        return

    with open(analysis_path, "r") as f:
        analysis = json.load(f)

    duplicates = analysis.get("duplicates", {})
    to_delete = []

    for file_hash, occurrences in duplicates.items():
        # Policy: 
        # 1. If one occurs in DATA_RAW, delete all others in DOWNLOADS/DESKTOP.
        # 2. If all are in DOWNLOADS/DESKTOP, keep the one with the "shortest" name or no "(1)" (the original).
        
        has_primary = any(o["label"] == "DATA_RAW" for o in occurrences)
        
        if has_primary:
            for o in occurrences:
                if o["label"] in ["DOWNLOADS", "DESKTOP"]:
                    to_delete.append(o["path"])
        else:
            # All in source folders. Sort by name length and presence of "( )"
            occurrences.sort(key=lambda x: (len(x["name"]), "(" in x["name"]))
            # Keep the first one, delete the rest
            for o in occurrences[1:]:
                to_delete.append(o["path"])

    # Deduplicate to_delete list
    to_delete = list(set(to_delete))

    deleted_count = 0
    errors = []

    print(f"Plan to delete {len(to_delete)} duplicate files...")
    
    for path in to_delete:
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
                deleted_count += 1
                print(f"  [OK] Deleted: {path}")
            else:
                print(f"  [INFO] Already gone: {path}")
        except Exception as e:
            errors.append(f"Failed to delete {path}: {str(e)}")
            print(f"  [FAIL] Error: {str(e)}")

    print(f"\nSummary: Deleted {deleted_count} files. Errors: {len(errors)}")
    
    # Save a log
    with open("e:/GL_AI/scratch/cleanup_log.json", "w") as f:
        json.dump({"deleted": to_delete, "errors": errors}, f, indent=2)

if __name__ == "__main__":
    cleanup_duplicates()
