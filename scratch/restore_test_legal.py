import json
from pathlib import Path
import re

prev_id = "b4de0704-05e5-401f-80f1-fa083cd5a7a3"
transcript_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{prev_id}\.system_generated\logs\transcript.jsonl")
target_file = Path(r"e:\GL_AI\test_legal.py")

if not transcript_path.exists():
    print(f"Error: {transcript_path} does not exist")
    exit(1)

print(f"Reading transcript to find test_legal.py content...")
found_content = None

with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
    for idx, line in enumerate(f, 1):
        try:
            data = json.loads(line)
            content = data.get("content", "")
            if "Showing lines 1 to 228" in content and "test_legal.py" in content:
                print(f"Found match at line {idx} in transcript!")
                # Extract content
                found_content = content
                break
        except Exception as e:
            pass

if not found_content:
    # Let's search for any occurrence of test_legal.py in VIEW_FILE or write_to_file or CODE_ACTION
    print("Exact line match not found, searching generally...")
    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, 1):
            try:
                data = json.loads(line)
                content = data.get("content", "")
                if "test_legal.py" in content and ("Showing lines" in content or "def " in content):
                    print(f"Found potential match at line {idx}...")
                    found_content = content
                    # We can keep looking for the best/longest one
            except Exception as e:
                pass

if not found_content:
    print("Could not find content in transcript.")
    exit(1)

# Now parse the showing lines content
# The content is formatted like:
# "Showing lines 1 to 228\nThe following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>...\n1: [line 1]\n2: [line 2]..."
lines = found_content.split("\n")
extracted_lines = []

# Find where the line number formatting starts
start_parsing = False
for line in lines:
    if "The following code has been modified" in line or "original_line" in line:
        start_parsing = True
        continue
    if start_parsing:
        # Match "1: content" or "123: content"
        match = re.match(r"^\s*(\d+):\s(.*)$", line)
        if match:
            line_no = int(match.group(1))
            line_content = match.group(2)
            extracted_lines.append((line_no, line_content))
        elif line.strip() == "" and len(extracted_lines) > 0:
            # Maybe an empty line at the end, but let's be careful
            pass

# Sort by line number
extracted_lines.sort(key=lambda x: x[0])

# Rebuild the file
file_content = "\n".join([content for _, content in extracted_lines])

# If empty, let's look at raw lines
if not file_content:
    print("Regex parsing failed to extract lines. Raw content preview:")
    print(found_content[:1000])
    exit(1)

# Write to target file
target_file.write_text(file_content, encoding="utf-8")
print(f"Successfully restored {len(extracted_lines)} lines to {target_file}")
