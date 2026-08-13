import os
import json
from pathlib import Path

def get_mapping():
    base = Path('E:/GL_AI/data_processed/documents')
    results = {}
    
    if not base.exists():
        print(f"Directory {base} not found.")
        return

    for doc_dir in base.iterdir():
        if not doc_dir.is_dir():
            continue
            
        doc_id = doc_dir.name
        source_path = "UNKNOWN"
        
        # Try multiple JSON sources
        options = [
            doc_dir / "phase_1" / "phase_1_extraction_summary.json",
            doc_dir / "phase_1" / "phase_1_1_1_pdf_parse.json",
            doc_dir / "metadata.json"
        ]
        
        for p in options:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "layout_structure" in data:
                            source_path = data["layout_structure"].get("document_path", "UNKNOWN")
                        elif "metadata" in data:
                            source_path = data["metadata"].get("source_path", "UNKNOWN")
                        
                        if source_path != "UNKNOWN":
                            break
                except Exception as e:
                    print(f"Error reading {p}: {e}")
        
        results[doc_id] = source_path
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    get_mapping()
