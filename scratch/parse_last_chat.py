import json
from pathlib import Path

prev_id = "0cf0ec4e-ae1a-4f8c-91c3-70ea87eddc07"
curr_id = "6960805a-8204-4a45-b25d-2f8301555fcc"
transcript_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{prev_id}\.system_generated\logs\transcript.jsonl")
output_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{curr_id}\last_chat_transcript.md")

if not transcript_path.exists():
    print(f"Error: {transcript_path} does not exist")
    exit(1)

md_lines = [
    f"# Last Chat Transcript (Session: `{prev_id}`)\n",
    "This document contains the chronological record of your previous chat session.\n",
    "---"
]

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        t = data.get("type")
        if t == "USER_INPUT":
            content = data.get("content", "").strip()
            md_lines.append(f"\n### 👤 User\n\n{content}\n")
            md_lines.append("---")
        elif t == "PLANNER_RESPONSE":
            content = data.get("content", "").strip()
            md_lines.append(f"\n### 🤖 Assistant\n\n{content}\n")
            md_lines.append("---")

# Make sure directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"Successfully generated markdown transcript at: {output_path}")
