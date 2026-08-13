import json
import os

path = r"E:\GL_AI\data_processed\documents\DOC_20260213_230426_ffba3818\phase_1\phase_1_extraction_summary.json"

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

raw_text = data.get("raw_text", "")
print(f"Type: {type(raw_text)}")
print(f"Length: {len(raw_text)}")
print(f"Count of '\\n' (code 10): {raw_text.count('\n')}")
print(f"Count of '\\\\n' (literal): {raw_text.count('\\n')}")
print(f"First 500 chars repr: {repr(raw_text[:500])}")
