import os
import json
from pathlib import Path
import pdfplumber

def extract_previews():
    analysis_path = Path("e:/GL_AI/scratch/file_inventory_analysis.json")
    if not analysis_path.exists():
        print(f"Error: {analysis_path} not found.")
        return

    with open(analysis_path, "r") as f:
        analysis = json.load(f)

    # Focus on unprocessed source files that might need renaming
    source_files = analysis.get("unprocessed_source", [])
    
    # Heuristic for "ambiguous" names: short names, camscanner, generic patterns
    ambiguous_keywords = ["a.pdf", "camscanner", "manzil", "FILE", "scan", "Project_progress", "KPK Specialization"]
    
    previews = []
    
    for f in source_files:
        path = Path(f["path"])
        if not path.exists():
            continue
            
        is_ambiguous = any(kw.lower() in f["name"].lower() for kw in ambiguous_keywords) or len(f["name"]) < 10
        
        if is_ambiguous:
            print(f"Extracting preview for: {f['name']}")
            try:
                with pdfplumber.open(path) as pdf:
                    # Get first 2 pages of text
                    text = ""
                    for i in range(min(2, len(pdf.pages))):
                        page_text = pdf.pages[i].extract_text()
                        if page_text:
                            text += page_text + "\n"
                    
                    previews.append({
                        "original_path": f["path"],
                        "original_name": f["name"],
                        "preview_text": text[:2000] # First 2000 chars
                    })
            except Exception as e:
                print(f"  [ERROR] Failed to extract from {f['name']}: {e}")
                previews.append({
                    "original_path": f["path"],
                    "original_name": f["name"],
                    "preview_text": f"[ERROR] Could not extract text: {e}"
                })

    output_path = Path("e:/GL_AI/scratch/ambiguous_previews.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(previews, f, indent=2, ensure_ascii=False)
    
    print(f"\nExtracted {len(previews)} previews to {output_path}")

if __name__ == "__main__":
    extract_previews()
