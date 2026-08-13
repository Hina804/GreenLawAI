import json
from pathlib import Path

prev_id = "b4de0704-05e5-401f-80f1-fa083cd5a7a3"
transcript_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{prev_id}\.system_generated\logs\transcript.jsonl")

if not transcript_path.exists():
    print(f"Error: {transcript_path} does not exist")
    exit(1)

print(f"Reading {transcript_path}...")
with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
    for line_no, line in enumerate(f, 1):
        if "test_legal.py" in line:
            print(f"Line {line_no} matches. Checking for file content...")
            try:
                data = json.loads(line)
                content = data.get("content", "")
                if "Showing lines 1 to" in content or "def " in content or "import " in content:
                    print(f"--- MATCH AT LINE {line_no} ({data.get('type')}) ---")
                    print(content[:1000])
                    print("-------------------------------------------\n")
            except Exception as e:
                pass
