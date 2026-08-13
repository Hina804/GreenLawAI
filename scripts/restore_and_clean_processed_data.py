import json
import os
import re

# Base directory
BASE_DIR = r"E:\GL_AI\data_processed\documents"

# Regex patterns for surgical removal (re.sub)
# These must be specific enough not to kill valid text
CLEANING_PATTERNS = [
    # Gazette Headers - match the whole block if possible
    r"(?i)KHYBER\s*PAKHTUNKHWA\s*GOVERNMENT\s*GAZETTE.*?(?:EXTRAORDINARY)?.*?(?:\d{4})?", 
    # The above might be too aggressive if '.*?' matches too much.
    # Better:
    r"(?i)KHYBER\s*PAKHTUNKHWA\s*GOVERNMENT\s*GAZETTE",
    r"(?i)EXTRAORDINARY\s*GOVERNMENT",
    r"(?i)REGISTERED\s+NO\.\s*P\.\s*III", # Typical pattern
    
    # Specific Forest Act Header Block
    # 05/04/24, 14: 43 The Forest Act, 1927 Page 1 of 33 file: ... . html
    r"\d{2}/\d{2}/\d{2},?\s+\d{2}:\s+\d{2}\s+The Forest Act, 1927",
    r"(?i)Page\s+\d+\s+of\s+\d+",
    r"file:\s*///.*?(?:\.\s*html|\.pdf)", # Non-greedy match until . html or .pdf
    
    # General Header Noise
    r"(?i)Published by Authority",
    r"(?i)PROVINC\s*IAL\s*A,\s*S\s*SEITIBLY.*",
]

def clean_text_surgical(text):
    if not text:
        return ""
    
    cleaned = text
    for pattern in CLEANING_PATTERNS:
        # replace with single space to prevent merging words
        cleaned = re.sub(pattern, " ", cleaned)
    
    # Normalize whitespace (but preserve newlines? No, if we want to clean up large gaps)
    # The user wants "corrected" data. Large gaps are ugly.
    cleaned = re.sub(r"[ \t]+", " ", cleaned) # Collapse spaces
    # cleaned = re.sub(r"\n\s*\n", "\n", cleaned) # Collapse multiple newlines (optional)
    
    return cleaned.strip()

def process_documents():
    log = []
    
    if not os.path.exists(BASE_DIR):
        print(f"Directory not found: {BASE_DIR}")
        return

    folders = os.listdir(BASE_DIR)
    print(f"Found {len(folders)} folders to process.")

    for folder in folders:
        folder_path = os.path.join(BASE_DIR, folder)
        phase_1_path = os.path.join(folder_path, "phase_1", "phase_1_extraction_summary.json")
        phase_2_path = os.path.join(folder_path, "phase_2", "phase_2_restoration_summary.json")
        
        if os.path.exists(phase_1_path):
            try:
                with open(phase_1_path, "r", encoding="utf-8") as f:
                    p1_data = json.load(f)
                
                raw_text = p1_data.get("raw_text", "")
                
                if raw_text:
                    # Apply SURGICAL cleaning
                    cleaned_text = clean_text_surgical(raw_text)
                    
                    p2_data = {}
                    if os.path.exists(phase_2_path):
                        try:
                            with open(phase_2_path, "r", encoding="utf-8") as f:
                                p2_data = json.load(f)
                        except:
                            pass
                    
                    p2_data["clean_text"] = cleaned_text
                    p2_data["segments_count"] = 1
                    p2_data["scrubbing_performed"] = True
                    p2_data["restoration_method"] = "manual_surgical_regex"
                    
                    if not os.path.exists(os.path.dirname(phase_2_path)):
                        os.makedirs(os.path.dirname(phase_2_path))
                        
                    with open(phase_2_path, "w", encoding="utf-8") as f:
                        json.dump(p2_data, f, indent=2)
                        
                    msg = f"[{folder}] SURGICAL CLEAN. Size: {len(cleaned_text)} chars (Original: {len(raw_text)})"
                    print(msg)
                    log.append(msg)
                else:
                    log.append(f"[{folder}] SKIPPED (No raw_text)")
            except Exception as e:
                msg = f"[{folder}] ERROR: {str(e)}"
                print(msg)
                log.append(msg)
        else:
            log.append(f"[{folder}] SKIPPED (Phase 1 missing)")

    with open("restoration_report_v2.txt", "w") as f:
        f.write("\n".join(log))

if __name__ == "__main__":
    process_documents()
