import os
import json

base_dir = r"E:\GL_AI\data_processed\new_documents"
docs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d != "graph_exports"]

summary_report = []

for doc in docs:
    doc_path = os.path.join(base_dir, doc)
    
    # Check for phases
    phases = {}
    for i in range(8):
        phase_dir = os.path.join(doc_path, f"phase_{i}")
        has_files = False
        if os.path.exists(phase_dir):
            files = os.listdir(phase_dir)
            if files:
                has_files = True
        phases[f"Phase {i}"] = has_files
    
    # Check for pipeline_summary.json
    summary_file = os.path.join(doc_path, "pipeline_summary.json")
    has_summary = os.path.exists(summary_file)
    summary_data = None
    if has_summary:
        try:
            with open(summary_file, 'r') as f:
                summary_data = json.load(f)
        except:
            pass
            
    summary_report.append({
        "document": doc,
        "phases": phases,
        "has_summary": has_summary,
        "success_in_summary": summary_data.get("success") if summary_data else None,
        "phases_in_summary": summary_data.get("phases_executed") if summary_data else []
    })

# Aggregate results
total_docs = len(summary_report)
fully_processed = [d for d in summary_report if all(d["phases"].values())]
partially_processed = [d for d in summary_report if any(d["phases"].values()) and not all(d["phases"].values())]
failed_processed = [d for d in summary_report if not any(d["phases"].values())]

print(f"Total Documents: {total_docs}")
print(f"Fully Processed (8/8 phases): {len(fully_processed)}")
print(f"Partially Processed: {len(partially_processed)}")
print(f"Failed (0 phases): {len(failed_processed)}")

# Check for systematic issues
phase_counts = {f"Phase {i}": 0 for i in range(8)}
for d in summary_report:
    for p, val in d["phases"].items():
        if val:
            phase_counts[p] += 1

print("\nPhase Coverage:")
for p, count in phase_counts.items():
    print(f"{p}: {count}/{total_docs}")

# List some examples of partial ones
if partially_processed:
    print("\nExamples of Partially Processed Documents:")
    for d in partially_processed[:5]:
        active_phases = [p for p, val in d["phases"].items() if val]
        print(f"- {d['document']}: {active_phases}")

with open(r"E:\GL_AI\scratch\full_verification_report.json", 'w') as f:
    json.dump(summary_report, f, indent=2)
