import os
import json
from pathlib import Path
import re

messages_dir = Path(r"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\b4de0704-05e5-401f-80f1-fa083cd5a7a3\.system_generated\messages")

longest_code = ""
source_file = ""

if messages_dir.exists():
    for file in messages_dir.glob("*.json"):
        try:
            content = file.read_text(encoding="utf-8", errors="ignore")
            # We look for a Python code block or file content of test_legal.py
            # Let's search for "Terminal test for legal pipeline" in the file
            if "Terminal test for legal pipeline" in content:
                print(f"Found match in message file: {file.name}")
                # Load JSON and find the code content
                data = json.loads(content)
                # Recursively search the JSON data for strings
                def find_strings(val):
                    global longest_code, source_file
                    if isinstance(val, str):
                        # Find python code containing import statements and main function
                        if "Terminal test for legal pipeline" in val and "async def" in val:
                            if len(val) > len(longest_code):
                                longest_code = val
                                source_file = file.name
                    elif isinstance(val, dict):
                        for k, v in val.items():
                            find_strings(v)
                    elif isinstance(val, list):
                        for item in val:
                            find_strings(item)
                
                find_strings(data)
        except Exception as e:
            print(f"Error checking {file.name}: {e}")
            
if longest_code:
    print(f"\nFound longest code block in {source_file} (length: {len(longest_code)} characters)")
    # Let's see if it looks like a complete Python file.
    # Clean up the markdown block if it's enclosed in ```python ... ```
    match = re.search(r"```python\n(.*?)```", longest_code, re.DOTALL)
    if match:
        clean_code = match.group(1)
    else:
        clean_code = longest_code
        
    # Write it to e:\GL_AI\scratch\extracted_from_message.py
    out_path = Path(r"e:\GL_AI\scratch\extracted_from_message.py")
    out_path.write_text(clean_code, encoding="utf-8")
    print(f"Extracted code written to {out_path}")
else:
    print("\nNo code block found in messages.")
