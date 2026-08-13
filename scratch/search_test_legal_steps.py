import json
from pathlib import Path

prev_id = "b4de0704-05e5-401f-80f1-fa083cd5a7a3"
transcript_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{prev_id}\.system_generated\logs\transcript.jsonl")

if not transcript_path.exists():
    print(f"Error: {transcript_path} does not exist")
    exit(1)

with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
    for idx, line in enumerate(f, 1):
        try:
            data = json.loads(line)
            content = data.get("content", "")
            tool_calls = data.get("tool_calls", [])
            
            # Check if test_legal.py is mentioned in content or tool calls
            has_test_legal = "test_legal.py" in str(line)
            if has_test_legal:
                print(f"Line {idx}: Step Index={data.get('step_index')}, Source={data.get('source')}, Type={data.get('type')}, Status={data.get('status')}")
                if data.get("type") in ["RUN_COMMAND", "CODE_ACTION", "WRITE_TO_FILE", "REPLACE_FILE_CONTENT", "MULTI_REPLACE_FILE_CONTENT"]:
                    print(f"  Snippet: {str(content)[:300]}...")
                for tc in tool_calls:
                    print(f"  Tool Call Name: {tc.get('name')}")
                    args = tc.get("args", {})
                    # If it has code contents or something, print the keys
                    print(f"  Args: {list(args.keys())}")
                    if "CodeContent" in args:
                        print("  Contains CodeContent!")
                    if "ReplacementContent" in args:
                        print("  Contains ReplacementContent!")
        except Exception as e:
            pass
