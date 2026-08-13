import json
import sys
from pathlib import Path

prev_id = "b4de0704-05e5-401f-80f1-fa083cd5a7a3"
transcript_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{prev_id}\.system_generated\logs\transcript.jsonl")
output_path = Path(r"e:\GL_AI\scratch\step_145_content.txt")

with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
    for idx, line in enumerate(f, 1):
        if idx == 143:
            data = json.loads(line)
            content = data.get("content", "")
            output_path.write_text(content, encoding="utf-8")
            print(f"Written content of length {len(content)} to {output_path}")
            
            # Print if '<truncated' is in content
            if "truncated" in content.lower():
                print("Warning: Content contains the word 'truncated'!")
            else:
                print("No 'truncated' found in content.")
