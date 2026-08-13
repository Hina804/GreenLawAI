import json
from pathlib import Path

prev_id = "b4de0704-05e5-401f-80f1-fa083cd5a7a3"
transcript_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{prev_id}\.system_generated\logs\transcript.jsonl")

if not transcript_path.exists():
    print(f"Error: {transcript_path} does not exist")
    exit(1)

with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
    for idx, line in enumerate(f, 1):
        if idx == 143:
            try:
                data = json.loads(line)
                content = data.get("content", "")
                print(f"Length of content: {len(content)}")
                print(f"Content snippet start: {content[:300]}")
                print(f"Content snippet end: {content[-300:]}")
            except Exception as e:
                print(f"Error parsing JSON: {e}")
