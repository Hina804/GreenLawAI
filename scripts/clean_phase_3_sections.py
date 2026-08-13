import json
import os
import re

# Base directory
BASE_DIR = r"E:\GL_AI\data_processed\documents"

# Regex patterns (SAME AS PHASE 2)
CLEANING_PATTERNS = [
    r"(?i)KHYBER\s*PAKHTUNKHWA\s*GOVERNMENT\s*GAZETTE",
    r"(?i)EXTRAORDINARY\s*GOVERNMENT",
    r"(?i)REGISTERED\s+NO\.\s*P\.\s*III",
    r"\d{2}/\d{2}/\d{2},?\s+\d{2}:\s+\d{2}\s+The Forest Act, 1927",
    r"(?i)Page\s+\d+\s+of\s+\d+",
    r"file:\s*///.*?(?:\.\s*html|\.pdf)",
    r"\d{2}/\d{2}/\d{2},?\s+\d{2}:\s+\d{2}", # Generic timestamp
    r"(?i)Published by Authority",
    r"(?i)PROVINC\s*IAL\s*A,\s*S\s*SEITIBLY.*",
]

def clean_text_surgical(text):
    if not text:
        return ""
    cleaned = text
    for pattern in CLEANING_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()

def process_section(section):
    # Clean content
    if "content" in section:
        if "text" in section["content"]:
            original = section["content"]["text"]
            cleaned = clean_text_surgical(original)
            section["content"]["text"] = cleaned
        
        if "raw_text" in section["content"]:
            original = section["content"]["raw_text"]
            cleaned = clean_text_surgical(original)
            section["content"]["raw_text"] = cleaned
            
    # Recurse
    if "child_sections" in section:
        for child in section["child_sections"]:
            process_section(child)

def process_documents():
    log = []
    if not os.path.exists(BASE_DIR):
        print(f"Directory not found: {BASE_DIR}")
        return

    folders = os.listdir(BASE_DIR)
    print(f"Found {len(folders)} folders to process.")

    for folder in folders:
        folder_path = os.path.join(BASE_DIR, folder)
        phase_3_path = os.path.join(folder_path, "phase_3", "phase_3_3_4_sections.json")
        
        if os.path.exists(phase_3_path):
            try:
                with open(phase_3_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Check root structure
                if "sections" in data:
                    for section in data["sections"]:
                        process_section(section)
                    
                    # Save
                    with open(phase_3_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                        
                    msg = f"[{folder}] PHASE 3 SECTIONS CLEANED."
                    print(msg)
                    log.append(msg)
                else:
                    log.append(f"[{folder}] SKIPPED (No 'sections' key in Phase 3)")
            except Exception as e:
                msg = f"[{folder}] ERROR: {str(e)}"
                print(msg)
                log.append(msg)
        else:
            log.append(f"[{folder}] SKIPPED (Phase 3 not found)")

    with open("phase_3_cleaning_report.txt", "w") as f:
        f.write("\n".join(log))

if __name__ == "__main__":
    process_documents()
