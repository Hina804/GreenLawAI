import os
import json
import shutil
import sys
from pathlib import Path

# Ensure stdout uses UTF-8 if possible, but for simplicity we'll just handle prints safely
def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))

def execute_organization():
    map_path = Path("e:/GL_AI/scratch/renaming_map_proposal.json")
    if not map_path.exists():
        safe_print("Renaming map not found!")
        return

    with open(map_path, "r", encoding="utf-8") as f:
        renaming_map = json.load(f)

    project_root = Path("e:/GL_AI")
    
    execution_log = []
    success_count = 0
    error_count = 0

    safe_print(f"Executing organization for {len(renaming_map)} project files...")

    for item in renaming_map:
        # Sanitize proposed name (remove emojis as a precaution for file systems, though NTFS handles them)
        # Actually the issue was just 'printing' them.
        
        source_path = Path(item["current_path"])
        target_dir = project_root / item["target_directory"]
        target_path = target_dir / item["proposed_name"]

        if not source_path.exists():
            # Might have been moved already or is missing
            # safe_print(f"  [SKIP] Source missing: {item['current_name']}")
            continue

        try:
            # Create target directory
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Handle name collision at target
            if target_path.exists():
                safe_print(f"  [INFO] Collision at target: {item['proposed_name']}")
                base = target_path.stem
                ext = target_path.suffix
                target_path = target_dir / f"{base}_copy_{abs(hash(str(source_path))) % 1000}{ext}"

            # MOVE FILE
            if source_path.drive != target_path.drive:
                shutil.copy2(source_path, target_path)
                source_path.unlink()
            else:
                shutil.move(source_path, target_path)

            safe_print(f"  [OK] Moved: {item['current_name']} -> {target_path.relative_to(project_root)}")
            success_count += 1
            execution_log.append({
                "source": str(source_path),
                "target": str(target_path),
                "status": "SUCCESS"
            })
        except Exception as e:
            safe_print(f"  [FAIL] Error moving {item['current_name']}: {str(e)}")
            error_count += 1
            execution_log.append({
                "source": str(source_path),
                "status": "ERROR",
                "error": str(e)
            })

    # Save final manifest/log (Append if exists)
    audit_path = project_root / "data_raw" / "organization_audit_log.json"
    existing_log = []
    if audit_path.exists():
        try:
            with open(audit_path, "r", encoding="utf-8") as f:
                existing_log = json.load(f)
        except:
            pass
            
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(existing_log + execution_log, f, indent=2, ensure_ascii=False)
    
    safe_print(f"\nSummary: Successfully moved {success_count} files. Errors: {error_count}")

if __name__ == "__main__":
    execute_organization()
