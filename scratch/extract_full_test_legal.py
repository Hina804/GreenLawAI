import json
import re
from pathlib import Path

prev_id = "b4de0704-05e5-401f-80f1-fa083cd5a7a3"
transcript_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{prev_id}\.system_generated\logs\transcript.jsonl")
target_file = Path(r"e:\GL_AI\test_legal.py")

# Try line 143 first (228 lines full read)
with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
    for idx, line in enumerate(f, 1):
        if idx == 143:
            data = json.loads(line)
            content = data.get("content", "")

# Parse numbered lines from the view_file output
extracted = []
for line in content.split("\n"):
    m = re.match(r"^(\d+):\s?(.*)", line)
    if m:
        ln = int(m.group(1))
        txt = m.group(2)
        # Remove trailing \r if present
        txt = txt.replace("\r", "")
        extracted.append((ln, txt))

extracted.sort(key=lambda x: x[0])
print(f"Parsed {len(extracted)} lines from transcript")

# The content is truncated! Let's check what we got
if extracted:
    print(f"First line: {extracted[0]}")
    print(f"Last line: {extracted[-1]}")
    
file_content = "\n".join(txt for _, txt in extracted)
print(f"\nFile content length: {len(file_content)} chars")

# Write it
target_file.write_text(file_content, encoding="utf-8")
print(f"Written to {target_file}")
