"""
fix_corrupted_phase6_jsons.py
Repairs 4 corrupted phase_6_6_graph_construction.json files.
"""
import json
import re
from pathlib import Path

BASE = Path("E:/GL_AI/data_processed/new_documents")


def verify_and_save(path: Path, raw: str, label: str):
    try:
        json.loads(raw)
        path.write_text(raw, encoding="utf-8")
        print(f"  [OK] {label}: FIXED and saved.")
        return True
    except json.JSONDecodeError as e:
        print(f"  [FAIL] {label}: STILL BROKEN at line {e.lineno}, col {e.colno}: {e.msg}")
        return False


# ── FILE 1: hazara_forest_act_1936 ───────────────────────────────────────────
# Bug: line 79 has bare text `6 on second conviction` inside a JSON value
print("\n[1] Fixing hazara_forest_act_1936 ...")
p1 = BASE / "hazara_forest_act_1936/phase_6/phase_6_6_graph_construction.json"
raw1 = p1.read_text(encoding="utf-8")
# The bad token is unquoted text after a number
raw1 = raw1.replace(
    '"max_imprisonment_months": 6 on second conviction',
    '"max_imprisonment_months": 6, "note": "on second conviction"'
)
verify_and_save(p1, raw1, "hazara_forest_act_1936")


# ── FILE 2: hazara_tree_species_master ───────────────────────────────────────
# Bug: two complete JSON objects concatenated with a newline between them
print("\n[2] Fixing hazara_tree_species_master ...")
p2 = BASE / "hazara_tree_species_master/phase_6/phase_6_6_graph_construction.json"
raw2 = p2.read_text(encoding="utf-8")

# Split at the point where object 1 ends and object 2 starts: }\n{
# The file may have many concatenated objects — split them all
# Strategy: find all top-level JSON objects by scanning for boundaries
def extract_all_json_objects(text):
    """Extract all concatenated top-level JSON objects from a string."""
    objects = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                chunk = text[start:i+1]
                try:
                    obj = json.loads(chunk)
                    objects.append(obj)
                except:
                    pass
                start = None
    return objects

objects = extract_all_json_objects(raw2)
print(f"  Found {len(objects)} concatenated JSON objects to merge.")
if len(objects) >= 2:
    base_obj = objects[0]
    d1 = base_obj.setdefault("data", {})
    d1.setdefault("nodes_by_type", {})
    d1.setdefault("relationships_by_type", {})

    for obj in objects[1:]:
        d2 = obj.get("data", {})
        for ntype, nodes in d2.get("nodes_by_type", {}).items():
            if ntype in d1["nodes_by_type"]:
                d1["nodes_by_type"][ntype].extend(nodes)
            else:
                d1["nodes_by_type"][ntype] = nodes
        for rtype, rels in d2.get("relationships_by_type", {}).items():
            if rtype in d1["relationships_by_type"]:
                d1["relationships_by_type"][rtype].extend(rels)
            else:
                d1["relationships_by_type"][rtype] = rels

    n_total = sum(len(v) for v in d1["nodes_by_type"].values())
    r_total = sum(len(v) for v in d1["relationships_by_type"].values())
    if "build_summary" in d1:
        d1["build_summary"]["nodes_count"] = n_total
        d1["build_summary"]["relationships_count"] = r_total

    merged = json.dumps(base_obj, ensure_ascii=False, indent=2)
    if verify_and_save(p2, merged, "hazara_tree_species_master"):
        print(f"     Merged {len(objects)} objects: {n_total} nodes, {r_total} relationships")
else:
    try:
        json.loads(raw2)
        print("  [OK] hazara_tree_species_master: ALREADY VALID JSON.")
    except Exception as e:
        print(f"  [FAIL] Could not extract multiple JSON objects and not valid JSON: {e}")


# ── FILE 3: PC-I Billion Tree Project in KPK Phase-II ───────────────────────
# Bug A (line 186): NURSERY_PRIVATE node object closed with `}}` needs `}}}` 
#   (closes: distribution{} + properties{} + array_element{})
#   AND the NurseryTarget array is closed with `},` not `],`
# Bug B (line 194): BENEFIT_ENVIRONMENTAL_FOREST_COVER closed with `}` needs `}}`
print("\n[3] Fixing PC-I Billion Tree Project in KPK Phase-II ...")
p3 = BASE / "PC-I Billion Tree Project in KPK Phase-II/phase_6/phase_6_6_graph_construction.json"
raw3 = p3.read_text(encoding="utf-8")

# Fix A: missing closing brace on NURSERY_PRIVATE array element,
#         and NurseryTarget array needs ] not }
raw3 = raw3.replace(
    '"Progressive Nursery Growers": "40%"}}}\n      },\n      "BenefitAnalysis"',
    '"Progressive Nursery Growers": "40%"}}}\n      ],\n      "BenefitAnalysis"'
)
# The line ends with `}}` — add the missing `}` for the array element itself
raw3 = raw3.replace(
    '"Progressive Nursery Growers": "40%"}}',
    '"Progressive Nursery Growers": "40%"}}}'
)
# Fix B: BENEFIT_ENVIRONMENTAL_FOREST_COVER missing closing brace
raw3 = raw3.replace(
    '"target_percent": 2, "target_ha_annual": 30000}\n      ],',
    '"target_percent": 2, "target_ha_annual": 30000}}\n      ],'
)
verify_and_save(p3, raw3, "PC-I Billion Tree Project")


# ── FILE 4: Restoration of Scientific Management in KP ───────────────────────
# Bug (line 32): FOREST_TYPE_DRY_TEMPERATE node object closed with `}` needs `}}`
#   (closes: properties{} + array_element{})
print("\n[4] Fixing Restoration of Scientific Management in KP ...")
p4 = BASE / "Restoration of Scientific Management in KP/phase_6/phase_6_6_graph_construction.json"
raw4 = p4.read_text(encoding="utf-8")
raw4 = raw4.replace(
    '"fire_cause": "dry standing and wind fallen trees"}\n      ],',
    '"fire_cause": "dry standing and wind fallen trees"}}\n      ],'
)
verify_and_save(p4, raw4, "Restoration of Scientific Management in KP")


# ── FINAL VALIDATION ─────────────────────────────────────────────────────────
print("\n== Final Validation of All 4 Files ==")
files = [
    BASE / "hazara_forest_act_1936/phase_6/phase_6_6_graph_construction.json",
    BASE / "hazara_tree_species_master/phase_6/phase_6_6_graph_construction.json",
    BASE / "PC-I Billion Tree Project in KPK Phase-II/phase_6/phase_6_6_graph_construction.json",
    BASE / "Restoration of Scientific Management in KP/phase_6/phase_6_6_graph_construction.json",
]
all_ok = True
for f in files:
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        nbt = data.get("data", {}).get("nodes_by_type", {})
        rbt = data.get("data", {}).get("relationships_by_type", {})
        n = sum(len(v) for v in nbt.values())
        r = sum(len(v) for v in rbt.values())
        print(f"  [OK] {f.parent.parent.name:<55} nodes={n:>4}  rels={r:>4}")
    except json.JSONDecodeError as e:
        print(f"  [FAIL] {f.parent.parent.name}: {e}")
        all_ok = False

if all_ok:
    print("\nAll 4 files are valid JSON. [ALL PASSED]")
else:
    print("\nSome files still have errors. [CHECK ABOVE]")
