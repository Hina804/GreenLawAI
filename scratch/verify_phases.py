import os
import json

base_dir = r"E:\GL_AI\data_processed\new_documents"
docs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and not d.startswith("graph_exports")]

# List of expected artifacts
expected_phases = {
    "Phase 0": "phase_0_profile.json",
    "Phase 1": "phase_1/phase_1_1_extraction.json", # Adjusted based on my check
    "Phase 2": "phase_2/phase_2_1_restoration.json", # guessing the names
    "Phase 3": "phase_3/phase_3_1_alignment.json",
    "Phase 4": "phase_4/phase_4_1_entities.json",
    "Phase 5": "phase_5/phase_5_1_authority.json",
    "Phase 6": "phase_6/phase_6_1_graph_mapping.json",
    "Phase 7": "phase_7/phase_7_1_orchestration.json"
}

# Actually, let's just check for the existence of any files in those phase directories
results = []
for doc in docs:
    doc_path = os.path.join(base_dir, doc)
    phases_found = {}
    for i in range(8):
        phase_dir = os.path.join(doc_path, f"phase_{i}")
        if os.path.exists(phase_dir) and os.listdir(phase_dir):
            phases_found[f"Phase {i}"] = True
        else:
            phases_found[f"Phase {i}"] = False
    
    # Check for phase_0 directly in the folder? Or maybe it's in a phase_0 subfolder?
    # Based on my previous list_dir, phase_1 was a folder.
    
    results.append({
        "document": doc,
        "phases": phases_found,
        "complete": all(phases_found.values())
    })

print(json.dumps(results, indent=2))
