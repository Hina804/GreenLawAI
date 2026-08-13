import json
from pathlib import Path

def generate_renaming_map():
    inventory_path = Path("e:/GL_AI/scratch/file_inventory_analysis.json")
    preview_path = Path("e:/GL_AI/scratch/ambiguous_previews.json")
    
    if not inventory_path.exists():
        print("Inventory not found!")
        return
    
    with open(inventory_path, "r", encoding="utf-8") as f:
        inventory = json.load(f)
    
    previews = {}
    if preview_path.exists():
        with open(preview_path, "r", encoding="utf-8") as f:
            preview_data = json.load(f)
            for p in preview_data:
                previews[p["original_path"]] = p["preview_text"]

    renaming_map = []
    
    # Process only unprocessed source files
    source_files = inventory.get("unprocessed_source", [])
    
    # PERSONAL FILE PATTERNS (TO SKIP)
    personal_keywords = ["manzil", "surah", "psychology", "cryptography", "encryption", "digital signature", "hina ali", "eman irfan", "information security", "security design", "rescue challenge", "defense in depth", "hash function", "public key"]

    for f in source_files:
        path = f["path"]
        name = f["name"]
        
        # 0. Check for Personal Files (SKIP)
        is_personal = any(kw in name.lower() for kw in personal_keywords)
        if is_personal:
            # We don't add personal files to the move map
            print(f"Skipping personal file: {name}")
            continue

        # Categorization logic
        target_dir = "data_raw/uncategorized"
        proposed_name = name
        
        # 1. Rules/Laws
        if any(kw in name.lower() for kw in ["act", "ordinance", "rules", "law", "policy"]):
            target_dir = "data_raw/forestry/kpk/laws" if "kpk" in name.lower() else "data_raw/forestry/federal/laws"
        
        # 2. Manuals
        elif "manual" in name.lower():
            target_dir = "data_raw/forestry/manuals"
            
        # 3. Market Rates
        elif any(kw in name.lower() for kw in ["mrs", "market rate", "notification"]):
            target_dir = "data_raw/rates"
            
        # 4. Progress/Docs
        elif any(kw in name.lower() for kw in ["progress", "blueprint", "presentation", "registry", "checklist"]):
            target_dir = "docs"
            
        # 5. Non-revealing / Special handling
        if name == "a.pdf" or "CamScanner" in name:
            target_dir = "data_raw/pending"
            proposed_name = f"pending_ocr_{abs(hash(path)) % 10000}.pdf"
            
        # 6. Specific overrides based on previews
        if path in previews:
            text = previews[path].lower()
            if "blueprint" in text:
                target_dir = "docs"
                proposed_name = "greenlawai_specialization_blueprint_v2.pdf"
            elif "progress report" in text:
                target_dir = "docs"
                proposed_name = f"greenlawai_progress_report_{abs(hash(path)) % 10000}.pdf"

        renaming_map.append({
            "current_path": path,
            "current_name": name,
            "proposed_name": proposed_name,
            "target_directory": target_dir,
            "reason": "Categorized by filename pattern or content preview"
        })

    with open("e:/GL_AI/scratch/renaming_map_proposal.json", "w", encoding="utf-8") as f:
        json.dump(renaming_map, f, indent=2, ensure_ascii=False)
    print("Renaming map generated to e:/GL_AI/scratch/renaming_map_proposal.json")

if __name__ == "__main__":
    generate_renaming_map()
