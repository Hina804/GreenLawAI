import os
from pathlib import Path

lost_found_dir = Path(r"e:\GL_AI\.git\lost-found\other")

if not lost_found_dir.exists():
    print(f"Error: {lost_found_dir} does not exist")
    exit(1)

longest_code = ""
longest_file = ""

for file in lost_found_dir.glob("*"):
    try:
        content = file.read_text(encoding="utf-8", errors="ignore")
        if "Terminal test for legal pipeline" in content:
            print(f"Found match in dangling blob: {file.name} (Size: {file.stat().st_size} bytes)")
            if len(content) > len(longest_code):
                longest_code = content
                longest_file = file.name
    except Exception as e:
        pass

if longest_code:
    print(f"\nLongest recovered code from {longest_file} (length: {len(longest_code)} characters)")
    # Write to test_legal.py
    target = Path(r"e:\GL_AI\test_legal.py")
    target.write_text(longest_code, encoding="utf-8")
    print(f"Successfully restored complete file content to {target}!")
else:
    print("No matching dangling blobs found.")
