import json
from pathlib import Path

file_path = Path("E:/GL_AI/data_processed/new_documents/hazara_tree_species_master/phase_3/phase_3_3_linguistic_alignment.json")

# Read the file content
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Parse multiple JSON objects from the concatenated file
decoder = json.JSONDecoder()
pos = 0
objs = []

while pos < len(content):
    # Skip whitespace
    while pos < len(content) and content[pos].isspace():
        pos += 1
    if pos >= len(content):
        break
    try:
        obj, new_pos = decoder.raw_decode(content, pos)
        objs.append(obj)
        pos = new_pos
    except json.JSONDecodeError as e:
        print(f"Decode error at pos {pos}: {e}")
        break

print(f"Successfully parsed {len(objs)} JSON objects.")

# Let's inspect the parsed objects.
# We expect each object to have "data" -> "sections" (which is a list of section dictionaries).
# Let's merge all the sections list into a single JSON object.
merged_sections = []
for i, obj in enumerate(objs):
    sections_data = obj.get("data", {}).get("sections", {})
    if isinstance(sections_data, dict):
        sections_list = sections_data.get("sections", [])
    else:
        sections_list = sections_data
    
    print(f"Object {i} has {len(sections_list)} sections.")
    merged_sections.extend(sections_list)

print(f"Total merged sections: {len(merged_sections)}")

# Construct a single merged JSON object
first_obj = objs[0]
if "sections" in first_obj.get("data", {}):
    # Structure is data -> sections as list or dict
    first_obj["data"]["sections"] = merged_sections
else:
    # Structure is data -> sections -> sections
    first_obj["data"]["sections"] = {
        "sections": merged_sections
    }

# Save back to file
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(first_obj, f, indent=2, ensure_ascii=False)

print("Merged file saved successfully as a single valid JSON!")
