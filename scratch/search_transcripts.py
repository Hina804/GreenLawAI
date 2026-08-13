import os
import json
from pathlib import Path

app_data = Path(r"C:\Users\QURESHI COMP\.gemini\antigravity-ide")
brain_dir = app_data / "brain"

found = []

if brain_dir.exists():
    for conv_dir in brain_dir.iterdir():
        if conv_dir.is_dir():
            transcript_path = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
            if transcript_path.exists():
                print(f"Searching {conv_dir.name}...")
                with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, 1):
                        if "test_legal.py" in line:
                            print(f"Found in {conv_dir.name} line {line_no}")
                            try:
                                data = json.loads(line)
                                found.append({
                                    "conv": conv_dir.name,
                                    "line": line_no,
                                    "type": data.get("type"),
                                    "content": data.get("content", "")[:200]
                                })
                            except Exception as e:
                                found.append({
                                    "conv": conv_dir.name,
                                    "line": line_no,
                                    "type": "error",
                                    "content": line[:200]
                                })

print("\nSummary of matches:")
for f in found:
    print(f)
