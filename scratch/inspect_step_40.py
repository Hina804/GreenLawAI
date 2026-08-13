import json
from pathlib import Path

prev_id = "b4de0704-05e5-401f-80f1-fa083cd5a7a3"
transcript_path = Path(rf"C:\Users\QURESHI COMP\.gemini\antigravity-ide\brain\{prev_id}\.system_generated\logs\transcript.jsonl")

with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
    for idx, line in enumerate(f, 1):
        if idx == 40:
            data = json.loads(line)
            tool_calls = data.get("tool_calls", [])
            for tc in tool_calls:
                args = tc.get("args", {})
                code = args.get("CodeContent", "")
                print(f"CodeContent Length: {len(code)}")
                print(f"Is truncated in log? {'truncated' in code.lower()}")
                # Write code to a test file to inspect
                Path(r"e:\GL_AI\scratch\step_40_code.py").write_text(code, encoding="utf-8")
                print("Code written to e:\\GL_AI\\scratch\\step_40_code.py")
