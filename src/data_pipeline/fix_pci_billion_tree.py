"""
fix_pci_billion_tree.py
Fixes the 2 missing braces in PC-I Billion Tree Project phase_6 JSON.
"""
import json
from pathlib import Path

PATH = Path("E:/GL_AI/data_processed/new_documents/PC-I Billion Tree Project in KPK Phase-II/phase_6/phase_6_6_graph_construction.json")

raw = PATH.read_text(encoding="utf-8")
lines = raw.splitlines(keepends=True)

print(f"Total lines: {len(lines)}")
print(f"Line 186: {repr(lines[185])}")
print(f"Line 187: {repr(lines[186])}")
print(f"Line 194: {repr(lines[193])}")
print(f"Line 195: {repr(lines[194])}")

# Fix 1: Line 186 (index 185)
# NURSERY_PRIVATE ends with `}}` — needs `}}}` (closes distribution, properties, element)
# Line 187 (index 186) is `      },` — needs to be `      ],` to close NurseryTarget array
old_186 = lines[185].rstrip('\r\n')
new_186 = old_186 + "}"   # add the missing closing brace for the array element
eol = "\r\n" if "\r\n" in lines[185] else "\n"

if old_186.rstrip().endswith("}}"):
    lines[185] = new_186 + eol
    print(f"Fixed line 186: added missing array-element closing brace")
else:
    print(f"WARNING: Line 186 did not end with '}}' as expected: {repr(old_186)}")

old_187 = lines[186].rstrip('\r\n')
if old_187.strip() == "},":
    lines[186] = old_187.replace("},", "],") + eol
    print(f"Fixed line 187: changed '}},' to '],' to close NurseryTarget array")
else:
    print(f"WARNING: Line 187 was not '}},' as expected: {repr(old_187)}")

# Fix 2: Line 194 (index 193)
# BENEFIT_ENVIRONMENTAL_FOREST_COVER ends with single `}` — needs `}}`
# (closes: properties dict + array element object)
old_194 = lines[193].rstrip('\r\n')
new_194 = old_194 + "}"
if old_194.rstrip().endswith("}") and not old_194.rstrip().endswith("}}"):
    lines[193] = new_194 + eol
    print(f"Fixed line 194: added missing element closing brace")
else:
    print(f"WARNING: Line 194 not as expected: {repr(old_194)}")

fixed_raw = "".join(lines)

try:
    json.loads(fixed_raw)
    PATH.write_text(fixed_raw, encoding="utf-8")
    print("\n[OK] PC-I Billion Tree Project: FIXED and saved.")
except json.JSONDecodeError as e:
    err_lines = fixed_raw.splitlines()
    print(f"\n[FAIL] Still broken at line {e.lineno}, col {e.colno}: {e.msg}")
    for i in range(max(0, e.lineno-3), min(len(err_lines), e.lineno+2)):
        print(f"  L{i+1}: {repr(err_lines[i])}")
