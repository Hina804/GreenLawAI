import os
from pathlib import Path

brain_dir = Path(r"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\b4de0704-05e5-401f-80f1-fa083cd5a7a3")

print("Files in previous brain dir:")
if brain_dir.exists():
    for root, dirs, files in os.walk(brain_dir):
        for file in files:
            path = Path(root) / file
            rel = path.relative_to(brain_dir)
            size = path.stat().st_size
            print(f"- {rel} ({size} bytes)")
else:
    print("Brain dir does not exist")
