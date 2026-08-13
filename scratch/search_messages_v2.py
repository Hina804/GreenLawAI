import os
import json
from pathlib import Path

messages_dir = Path(r"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\b4de0704-05e5-401f-80f1-fa083cd5a7a3\.system_generated\messages")

if not messages_dir.exists():
    print(f"Error: {messages_dir} does not exist")
    exit(1)

for file in messages_dir.glob("*.json"):
    try:
        content = file.read_text(encoding="utf-8", errors="ignore")
        if "test_legal.py" in content:
            print(f"\n--- Found 'test_legal.py' in {file.name} (Size: {file.stat().st_size} bytes) ---")
            # Let's inspect the JSON structure
            data = json.loads(content)
            
            def scan(val, path=""):
                if isinstance(val, str):
                    if len(val) > 200 and ("import" in val or "def" in val or "class" in val or "TEST_QUERIES" in val):
                        print(f"  Found potential code block at {path} (Length: {len(val)})")
                        print(f"  Snippet: {val[:150]}...")
                        # If it looks like python code, let's save it
                        if "TEST_QUERIES" in val:
                            out_file = Path(rf"e:\GL_AI\scratch\extracted_{file.stem}_{len(val)}.py")
                            out_file.write_text(val, encoding="utf-8")
                            print(f"  Saved to {out_file}")
                elif isinstance(val, dict):
                    for k, v in val.items():
                        scan(v, f"{path}/{k}" if path else k)
                elif isinstance(val, list):
                    for i, item in enumerate(val):
                        scan(item, f"{path}[{i}]")
            
            scan(data)
    except Exception as e:
        print(f"Error processing {file.name}: {e}")
