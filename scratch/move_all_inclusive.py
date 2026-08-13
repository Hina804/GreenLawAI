import os
import shutil
from pathlib import Path

def move_all_project_files():
    src_dir = Path("C:/Users/QURESHI COMP/Downloads")
    dst_dir = Path("E:/GL_AI/data_raw/incoming_unfiltered")
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    # Extensions to include
    exts = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.png', '.txt'}
    
    # Strictly personal keywords to skip (as previously agreed)
    skip_keywords = ['manzil', 'surah', 'psychology', 'cryptography', 'encryption', 'digital signature', 'hina ali', 'eman irfan', 'info sec', 'security design', 'rescue', 'defense', 'hash', 'public key']
    
    success_count = 0
    skip_count = 0
    lock_count = 0
    
    files = [f for f in os.listdir(src_dir) if os.path.isfile(src_dir / f)]
    
    print(f"Scanning {len(files)} files in Downloads...")
    
    for f in files:
        f_lower = f.lower()
        if any(f_lower.endswith(e) for e in exts):
            # Check if personal
            if any(k in f_lower for k in skip_keywords):
                print(f"  [SKIP] Personal: {f}")
                skip_count += 1
                continue
            
            # Move project-related file (including duplicates with (1))
            try:
                src_path = src_dir / f
                dst_path = dst_dir / f
                
                # Handle potential duplicate name in target
                if dst_path.exists():
                    dst_path = dst_dir / f"{src_path.stem}_{success_count}{src_path.suffix}"
                
                shutil.move(str(src_path), str(dst_path))
                print(f"  [OK] Moved: {f}")
                success_count += 1
            except Exception as e:
                print(f"  [LOCK] Could not move {f} (likely open): {e}")
                lock_count += 1
        else:
            # Not a document extension
            pass

    print(f"\nSummary:")
    print(f"  Total Moved: {success_count}")
    print(f"  Skipped (Personal): {skip_count}")
    print(f"  Skipped (Locked/Error): {lock_count}")

if __name__ == "__main__":
    move_all_project_files()
